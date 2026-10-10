import csv
import hashlib
import json
import logging
import math
import re
import unicodedata
from functools import lru_cache

from src.config import CACHE_EMBEDDINGS, EMBEDDING_MODEL, IMOVEIS_CSV, busca_semantica_disponivel
from src.llm import client

logger = logging.getLogger(__name__)

ZONAS = ("sul", "norte", "leste", "oeste", "centro")
TIPOS_COMERCIAIS = ("sala_comercial", "loja")
NOMES_TIPO = {"apartamento": "Apartamento", "studio": "Studio", "casa": "Casa", "sala_comercial": "Sala comercial", "loja": "Loja"}
TOLERANCIA_PRECO = 1.10


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


@lru_cache
def carregar() -> tuple[dict, ...]:
    with open(IMOVEIS_CSV, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    imoveis = []
    for linha in linhas:
        imovel = dict(linha)
        for campo in ("quartos", "vagas", "area_m2", "preco", "condominio"):
            imovel[campo] = int(imovel[campo])
        imovel["aluguel_estimado"] = int(imovel["aluguel_estimado"]) if imovel["aluguel_estimado"] else None
        imovel["rentabilidade_mensal"] = float(imovel["rentabilidade_mensal"]) if imovel["rentabilidade_mensal"] else None
        imoveis.append(imovel)
    return tuple(imoveis)


def obter(codigo: str) -> dict | None:
    codigo = (codigo or "").strip().upper()
    return next((i for i in carregar() if i["codigo"] == codigo), None)


def _menciona_zona(alvo: str, zona: str) -> bool:
    if zona == "centro":
        return bool(re.search(r"\bcentro\b|paulista", alvo))
    return bool(re.search(rf"\bzona {zona}\b", alvo))


def regiao_reconhecida(regiao: str | None) -> bool:
    alvo = normalizar(regiao or "")
    return any(_menciona_zona(alvo, z) for z in ZONAS) or any(normalizar(i["bairro"]) in alvo for i in carregar())


def corresponde_regiao(imovel: dict, regiao: str) -> bool:
    alvo = normalizar(regiao)
    return normalizar(imovel["bairro"]) in alvo or _menciona_zona(alvo, imovel["zona"])


def _hash_base() -> str:
    conteudo = "|".join(f"{i['codigo']}:{i['descricao']}" for i in carregar())
    return hashlib.sha256(f"{EMBEDDING_MODEL}|{conteudo}".encode()).hexdigest()


@lru_cache
def _vetores_imoveis() -> dict[str, list[float]]:
    assinatura = _hash_base()
    if CACHE_EMBEDDINGS.exists():
        cache = json.loads(CACHE_EMBEDDINGS.read_text(encoding="utf-8"))
        if cache.get("assinatura") == assinatura:
            return cache["vetores"]
    imoveis = carregar()
    vetores = client.embed([texto_indexacao(i) for i in imoveis])
    resultado = {i["codigo"]: v for i, v in zip(imoveis, vetores)}
    CACHE_EMBEDDINGS.parent.mkdir(parents=True, exist_ok=True)
    CACHE_EMBEDDINGS.write_text(json.dumps({"assinatura": assinatura, "vetores": resultado}), encoding="utf-8")
    return resultado


def texto_indexacao(imovel: dict) -> str:
    return f"{NOMES_TIPO[imovel['tipo']]} em {imovel['bairro']}, zona {imovel['zona']} de São Paulo. {imovel['descricao']}"


def _cosseno(a: list[float], b: list[float]) -> float:
    produto = sum(x * y for x, y in zip(a, b))
    normas = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return produto / normas if normas else 0.0


def _similaridade_lexica(consulta: str, imovel: dict) -> float:
    termos = {t for t in re.findall(r"\w{4,}", normalizar(consulta))}
    if not termos:
        return 0.0
    texto = normalizar(texto_indexacao(imovel))
    return sum(1 for t in termos if t in texto) / len(termos)


def similaridades(consulta: str, imoveis: list[dict]) -> dict[str, float]:
    if not consulta.strip():
        return {i["codigo"]: 0.0 for i in imoveis}
    if busca_semantica_disponivel():
        try:
            vetores = _vetores_imoveis()
            vetor_consulta = client.embed([consulta])[0]
            return {i["codigo"]: _cosseno(vetor_consulta, vetores[i["codigo"]]) for i in imoveis}
        except Exception:
            logger.exception("Falha na busca semântica; usando similaridade léxica")
    return {i["codigo"]: _similaridade_lexica(consulta, i) for i in imoveis}


def _aderencia_preco(preco: float, limite: float | None) -> float:
    if not limite:
        return 0.5
    return max(0.0, 1 - abs(limite - preco) / limite)


def _filtrar_tipo(imovel: dict, tipo: str | None) -> bool:
    if not tipo:
        return imovel["tipo"] not in TIPOS_COMERCIAIS
    if tipo == "comercial":
        return imovel["tipo"] in TIPOS_COMERCIAIS
    if tipo == "apartamento":
        return imovel["tipo"] in ("apartamento", "studio")
    return imovel["tipo"] == tipo


def buscar(lead: dict, limite: int = 3) -> list[dict]:
    intencao = lead.get("intencao")
    if intencao == "investimento":
        return buscar_investimento(lead, limite)
    finalidade = "aluguel" if intencao == "aluguel" else "venda"
    candidatos = [i for i in carregar() if i["finalidade"] == finalidade and _filtrar_tipo(i, lead.get("tipo_imovel"))]
    if lead.get("quartos"):
        candidatos = [i for i in candidatos if i["quartos"] >= lead["quartos"]]
    acima_do_orcamento = False
    if lead.get("preco_max"):
        dentro = [i for i in candidatos if i["preco"] <= lead["preco_max"] * TOLERANCIA_PRECO]
        acima_do_orcamento = bool(candidatos) and not dentro
        candidatos = dentro or candidatos
    regiao = lead.get("regiao") or ""
    fora_da_regiao = False
    pool = candidatos
    if regiao_reconhecida(regiao):
        na_regiao = [i for i in candidatos if corresponde_regiao(i, regiao)]
        fora_da_regiao = bool(candidatos) and not na_regiao
        pool = na_regiao or candidatos
    usar_semantica = bool(lead.get("preferencias")) or (bool(regiao) and not regiao_reconhecida(regiao))
    consulta = " ".join(filter(None, [lead.get("preferencias"), lead.get("tipo_imovel"), regiao]))
    if acima_do_orcamento:
        ordenados = sorted(pool, key=lambda i: i["preco"])
    else:
        sims = similaridades(consulta, pool) if usar_semantica else {i["codigo"]: 0.0 for i in pool}
        ordenados = sorted(
            pool,
            key=lambda i: (0.6 * sims[i["codigo"]] + 0.4 * _aderencia_preco(i["preco"], lead.get("preco_max")), -abs(i["quartos"] - (lead.get("quartos") or i["quartos"]))),
            reverse=True,
        )
    return [{**i, "fora_da_regiao": fora_da_regiao, "acima_do_orcamento": acima_do_orcamento} for i in ordenados[:limite]]


def buscar_investimento(lead: dict, limite: int = 3) -> list[dict]:
    perfil = normalizar(lead.get("perfil_investidor") or "")
    candidatos = [i for i in carregar() if i["finalidade"] == "venda" and i["rentabilidade_mensal"]]
    if "comerci" in perfil:
        candidatos = [i for i in candidatos if i["tipo"] in TIPOS_COMERCIAIS]
    elif "residencia" in perfil:
        candidatos = [i for i in candidatos if i["tipo"] not in TIPOS_COMERCIAIS]
    acima_do_orcamento = False
    if lead.get("ticket"):
        dentro = [i for i in candidatos if i["preco"] <= lead["ticket"] * 1.05]
        acima_do_orcamento = bool(candidatos) and not dentro
        candidatos = dentro or candidatos
    if regiao_reconhecida(lead.get("regiao")):
        na_regiao = [i for i in candidatos if corresponde_regiao(i, lead["regiao"])]
        candidatos = na_regiao or candidatos
    if acima_do_orcamento:
        ordenados = sorted(candidatos, key=lambda i: i["preco"])
    else:
        ordenados = sorted(candidatos, key=lambda i: (i["rentabilidade_mensal"], i["preco"]), reverse=True)
    return [{**i, "fora_da_regiao": False, "acima_do_orcamento": acima_do_orcamento} for i in ordenados[:limite]]


def formatar_preco(valor: float) -> str:
    return f"R$ {valor:,.0f}".replace(",", ".")


def resumo_imovel(imovel: dict) -> str:
    preco = formatar_preco(imovel["preco"]) + ("/mês" if imovel["finalidade"] == "aluguel" else "")
    detalhes = [f"{imovel['area_m2']} m²"]
    if imovel["quartos"]:
        detalhes.insert(0, f"{imovel['quartos']} quarto{'s' if imovel['quartos'] > 1 else ''}")
    if imovel["vagas"]:
        detalhes.append(f"{imovel['vagas']} vaga{'s' if imovel['vagas'] > 1 else ''}")
    linha = f"{imovel['codigo']} | {NOMES_TIPO[imovel['tipo']]} em {imovel['bairro']} (zona {imovel['zona']}) | {', '.join(detalhes)} | {preco}"
    if imovel["condominio"]:
        linha += f" + cond. {formatar_preco(imovel['condominio'])}"
    if imovel.get("rentabilidade_mensal") and imovel["finalidade"] == "venda":
        taxa = f"{imovel['rentabilidade_mensal']:.2f}".replace(".", ",")
        linha += f" | aluguel estimado {formatar_preco(imovel['aluguel_estimado'])}/mês ({taxa}% a.m. bruto)"
    return f"{linha} | {imovel['descricao']}"
