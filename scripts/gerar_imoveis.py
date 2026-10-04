import csv
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import IMOVEIS_CSV

BAIRROS = [
    ("Moema", "sul", 14500, "metrô Moema e Parque Ibirapuera"),
    ("Vila Mariana", "sul", 12500, "metrô Ana Rosa"),
    ("Brooklin", "sul", 13000, "Av. Berrini e estação Brooklin"),
    ("Saúde", "sul", 10500, "metrô Praça da Árvore"),
    ("Campo Belo", "sul", 12000, "metrô Campo Belo"),
    ("Pinheiros", "oeste", 15500, "metrô Faria Lima"),
    ("Perdizes", "oeste", 12000, "PUC e Allianz Parque"),
    ("Vila Madalena", "oeste", 14000, "metrô Vila Madalena"),
    ("Lapa", "oeste", 9500, "estação Lapa da CPTM"),
    ("Santana", "norte", 9000, "metrô Santana"),
    ("Tucuruvi", "norte", 7800, "metrô Tucuruvi"),
    ("Tatuapé", "leste", 9800, "metrô Tatuapé e Shopping Anália Franco"),
    ("Mooca", "leste", 9200, "Juventus e metrô Bresser-Mooca"),
    ("Bela Vista", "centro", 10500, "Av. Paulista"),
    ("Consolação", "centro", 11500, "metrô Mackenzie-Higienópolis"),
    ("República", "centro", 8500, "metrô República"),
]

DIFERENCIAIS = [
    "varanda gourmet",
    "lazer completo com piscina e academia",
    "aceita pet",
    "andar alto com vista livre",
    "reformado recentemente",
    "cozinha planejada",
    "portaria 24 horas",
    "sol da manhã",
    "condomínio com coworking",
    "rua arborizada e silenciosa",
    "armários embutidos",
    "próximo a escolas e mercados",
]

TIPOS_RESIDENCIAIS = [
    ("apartamento", [1, 2, 2, 3, 3, 4], (38, 70, 95, 140)),
    ("studio", [1], (24, 30, 38, 45)),
    ("casa", [2, 3, 3, 4], (90, 130, 180, 260)),
]

TIPOS_COMERCIAIS = [("sala_comercial", (30, 45, 70, 110)), ("loja", (40, 80, 120, 200))]


def area_por_quartos(quartos: int, faixas: tuple) -> int:
    indice = min(quartos - 1, len(faixas) - 1)
    return random.randint(int(faixas[indice] * 0.85), int(faixas[indice] * 1.15))


def arredondar(valor: float, passo: int) -> int:
    return int(round(valor / passo) * passo)


def descricao(tipo: str, bairro: str, referencia: str, quartos: int, area: int, diferenciais: list[str]) -> str:
    nomes = {"apartamento": "Apartamento", "studio": "Studio", "casa": "Casa", "sala_comercial": "Sala comercial", "loja": "Loja"}
    base = f"{nomes[tipo]} de {area} m² em {bairro}, perto de {referencia}"
    if tipo in ("apartamento", "casa"):
        base = f"{nomes[tipo]} de {quartos} quarto{'s' if quartos > 1 else ''} e {area} m² em {bairro}, perto de {referencia}"
    return f"{base}. Destaques: {', '.join(diferenciais)}."


def gerar() -> list[dict]:
    random.seed(42)
    imoveis = []
    contador = {"venda": 0, "aluguel": 0}

    def registrar(finalidade, tipo, bairro, zona, m2, referencia, quartos, area, vagas, comercial=False):
        contador[finalidade] += 1
        prefixo = "V" if finalidade == "venda" else "A"
        codigo = f"{prefixo}{contador[finalidade]:03d}"
        valor_venda = area * m2 * random.uniform(0.9, 1.12) * (0.85 if tipo == "casa" else 1)
        aluguel_mensal = valor_venda * random.uniform(0.0042, 0.0058) * (1.15 if comercial else 1)
        diferenciais = random.sample(DIFERENCIAIS, 2 if tipo != "studio" else 1)
        if tipo == "studio":
            diferenciais.append("ideal para investidor ou primeiro imóvel")
        if comercial:
            diferenciais = random.sample(["alto fluxo de pedestres", "pé-direito duplo", "prédio corporativo AAA", "fachada ampla", "recepção e segurança"], 2)
        preco = arredondar(valor_venda, 5000) if finalidade == "venda" else arredondar(aluguel_mensal, 50)
        condominio = 0 if tipo == "casa" else arredondar(area * random.uniform(9, 16), 10)
        imoveis.append({
            "codigo": codigo,
            "finalidade": finalidade,
            "tipo": tipo,
            "bairro": bairro,
            "zona": zona,
            "cidade": "São Paulo",
            "quartos": quartos,
            "vagas": vagas,
            "area_m2": area,
            "preco": preco,
            "condominio": condominio,
            "aluguel_estimado": arredondar(aluguel_mensal, 50) if finalidade == "venda" else "",
            "rentabilidade_mensal": round(aluguel_mensal / valor_venda * 100, 2) if finalidade == "venda" else "",
            "descricao": descricao(tipo, bairro, referencia, quartos, area, diferenciais),
        })

    for bairro, zona, m2, referencia in BAIRROS:
        for finalidade in ("venda",) * 4 + ("aluguel",) * 3:
            tipo, quartos_possiveis, faixas = random.choices(TIPOS_RESIDENCIAIS, weights=[7, 2, 1])[0]
            if zona == "centro" and tipo == "casa":
                tipo, quartos_possiveis, faixas = TIPOS_RESIDENCIAIS[0]
            quartos = random.choice(quartos_possiveis)
            area = area_por_quartos(quartos, faixas)
            vagas = 0 if tipo == "studio" else min(quartos, random.choice([1, 1, 2, 2, 3]))
            registrar(finalidade, tipo, bairro, zona, m2, referencia, quartos, area, vagas)
        if zona in ("sul", "oeste", "centro"):
            tipo, faixas = random.choice(TIPOS_COMERCIAIS)
            area = random.randint(faixas[0], faixas[-1])
            registrar("venda", tipo, bairro, zona, m2 * 0.95, referencia, 0, area, random.choice([0, 1, 2]), comercial=True)

    return imoveis


def main():
    imoveis = gerar()
    IMOVEIS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(IMOVEIS_CSV, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=list(imoveis[0]))
        escritor.writeheader()
        escritor.writerows(imoveis)
    print(f"{len(imoveis)} imóveis gravados em {IMOVEIS_CSV}")


if __name__ == "__main__":
    main()
