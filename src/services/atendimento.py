import hashlib
import logging
from dataclasses import dataclass
from time import perf_counter
from uuid import uuid4

from src.config import HISTORICO_MAX_MENSAGENS
from src.graph.nodes import gerar_resumo
from src.graph.sdr_graph import sdr_app
from src.memory.repositorio import Repositorio, get_repositorio
from src.security.guardrails import sanitizar

logger = logging.getLogger(__name__)


@dataclass
class ResultadoAtendimento:
    lead_id: str
    resposta: str
    agente: str
    etapa: str
    score: int
    temperatura: str
    latencia_ms: int
    reuniao: dict | None


def novo_lead_id(canal: str = "web") -> str:
    return f"{canal}-{uuid4().hex[:8]}"


def config_execucao(repo: Repositorio, lead_id: str, canal: str, evento: str) -> dict:
    lead_hash = hashlib.sha256(lead_id.encode()).hexdigest()[:12]
    return {
        "configurable": {"repo": repo},
        "run_name": f"sdr-{evento}",
        "tags": [f"canal:{canal}", f"evento:{evento}"],
        "metadata": {"lead": lead_hash, "canal": canal},
    }


def estado_do_lead(repo: Repositorio, lead: dict) -> dict:
    return {
        "lead_id": lead["id"],
        "canal": lead["canal"],
        "historico": [
            {"papel": m["papel"], "conteudo": m["conteudo"]}
            for m in repo.historico(lead["id"], HISTORICO_MAX_MENSAGENS)
            if m["agente"] != "bloqueado"
        ],
        "mensagens_lead": repo.contar_mensagens_lead(lead["id"]),
        "lead": lead["dados"],
        "etapa": lead["etapa"],
        "score": lead["score"],
        "temperatura": lead["temperatura"],
        "motivos_score": lead["motivos_score"],
        "imoveis_sugeridos": lead["imoveis_sugeridos"],
        "horarios_ofertados": lead["horarios_ofertados"],
        "reuniao": repo.reuniao_do_lead(lead["id"]),
        "tentativas_followup": lead["tentativas_followup"],
    }


def processar_mensagem(lead_id: str, texto: str, canal: str = "web", repo: Repositorio | None = None) -> ResultadoAtendimento:
    repo = repo or get_repositorio()
    lead = repo.obter_ou_criar_lead(lead_id, canal)
    estado = {**estado_do_lead(repo, lead), "evento": "mensagem", "mensagem_atual": sanitizar(texto)}

    inicio = perf_counter()
    resultado = sdr_app.invoke(estado, config=config_execucao(repo, lead_id, canal, "mensagem"))
    latencia_ms = round((perf_counter() - inicio) * 1000)

    bloqueado = bool(resultado.get("bloqueado"))
    repo.salvar_mensagem(lead_id, "user", estado["mensagem_atual"], agente="bloqueado" if bloqueado else None)
    repo.salvar_mensagem(lead_id, "assistant", resultado["resposta_final"], agente=resultado.get("agente"), latencia_ms=latencia_ms)

    if bloqueado:
        repo.registrar_evento(lead_id, "seguranca_bloqueio", "prompt injection")
    else:
        persistir_resultado(repo, lead, resultado)

    atualizado = repo.obter_lead(lead_id)
    logger.info("lead=%s agente=%s etapa=%s latencia_ms=%s", lead_id, resultado.get("agente"), atualizado["etapa"], latencia_ms)
    return ResultadoAtendimento(
        lead_id=lead_id,
        resposta=resultado["resposta_final"],
        agente=resultado.get("agente", ""),
        etapa=atualizado["etapa"],
        score=atualizado["score"],
        temperatura=atualizado["temperatura"],
        latencia_ms=latencia_ms,
        reuniao=resultado.get("reuniao"),
    )


def persistir_resultado(repo: Repositorio, lead_anterior: dict, resultado: dict) -> None:
    campos = {
        "dados": resultado["lead"],
        "etapa": resultado["etapa"],
        "score": resultado["score"],
        "temperatura": resultado["temperatura"],
        "motivos_score": resultado["motivos_score"],
        "imoveis_sugeridos": resultado.get("imoveis_sugeridos") or [],
        "horarios_ofertados": resultado.get("horarios_ofertados") or [],
    }
    if resultado.get("resumo_corretor"):
        campos["resumo"] = resultado["resumo_corretor"]
    repo.atualizar_lead(lead_anterior["id"], **campos)
    if resultado["etapa"] != lead_anterior["etapa"]:
        repo.registrar_evento(lead_anterior["id"], "etapa_alterada", f"{lead_anterior['etapa']} -> {resultado['etapa']}")


def atualizar_resumo(lead_id: str, repo: Repositorio | None = None) -> str:
    repo = repo or get_repositorio()
    lead = repo.obter_lead(lead_id)
    resumo = gerar_resumo(estado_do_lead(repo, lead))
    repo.atualizar_lead(lead_id, resumo=resumo)
    repo.registrar_evento(lead_id, "resumo_gerado")
    return resumo
