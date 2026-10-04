from dataclasses import dataclass, field

from src.graph.state import campos_requeridos

PONTOS_URGENCIA = {"alta": 25, "media": 12, "baixa": 3}
ROTULO_URGENCIA = {"alta": "alta", "media": "média", "baixa": "baixa"}
LIMIAR_QUENTE = 70
LIMIAR_MORNO = 40


@dataclass
class Score:
    valor: int
    temperatura: str
    motivos: list[str] = field(default_factory=list)


def classificar(valor: int) -> str:
    if valor >= LIMIAR_QUENTE:
        return "quente"
    if valor >= LIMIAR_MORNO:
        return "morno"
    return "frio"


def calcular_score(lead: dict, etapa: str, mensagens_lead: int) -> Score:
    if etapa == "perdido":
        return Score(0, "frio", ["Lead sem interesse ou sem resposta após os follow-ups"])

    pontos = 0
    motivos = []
    intencao = lead.get("intencao")
    if intencao:
        pontos += 10
        motivos.append(f"Intenção identificada: {intencao} (+10)")

    requeridos = campos_requeridos(lead)
    if requeridos:
        preenchidos = sum(1 for c in requeridos if lead.get(c) is not None)
        ganho = round(35 * preenchidos / len(requeridos))
        pontos += ganho
        motivos.append(f"{preenchidos} de {len(requeridos)} dados de qualificação (+{ganho})")

    urgencia = lead.get("urgencia")
    if urgencia in PONTOS_URGENCIA:
        pontos += PONTOS_URGENCIA[urgencia]
        motivos.append(f"Urgência {ROTULO_URGENCIA[urgencia]} (+{PONTOS_URGENCIA[urgencia]})")

    if intencao == "investimento" and (lead.get("ticket") or 0) >= 1_000_000:
        pontos += 10
        motivos.append("Ticket de investimento acima de R$ 1 milhão (+10)")

    if lead.get("forma_pagamento"):
        pontos += 5
        motivos.append(f"Forma de pagamento definida: {lead['forma_pagamento']} (+5)")

    if lead.get("nome") or lead.get("contato"):
        pontos += 5
        motivos.append("Cliente se identificou (+5)")

    engajamento = min(mensagens_lead, 5) * 2
    if engajamento:
        pontos += engajamento
        motivos.append(f"{mensagens_lead} mensagem(ns) do cliente (+{engajamento})")

    if etapa == "agendado":
        pontos += 20
        motivos.append("Visita/reunião agendada (+20)")
    elif etapa == "qualificado":
        pontos += 10
        motivos.append("Qualificação completa (+10)")

    valor = min(pontos, 100)
    return Score(valor, classificar(valor), motivos)
