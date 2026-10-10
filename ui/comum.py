from datetime import datetime

import streamlit as st

from src.graph.nodes import formatar_valor
from src.graph.state import ROTULOS, ROTULOS_ETAPA
from src.memory.repositorio import Repositorio, get_repositorio
from src.tools import agenda

ICONES_TEMPERATURA = {"quente": "🔥", "morno": "🌤️", "frio": "❄️"}
CORES_TEMPERATURA = {"quente": "red", "morno": "orange", "frio": "blue"}
ICONES_ETAPA = {"novo": "🆕", "em_qualificacao": "💬", "qualificado": "✅", "agendado": "📅", "perdido": "⛔"}
CORES_ETAPA = {"novo": "gray", "em_qualificacao": "blue", "qualificado": "green", "agendado": "violet", "perdido": "gray"}
ORDEM_ETAPAS = ["novo", "em_qualificacao", "qualificado", "agendado", "perdido"]
NOMES_AGENTE = {
    "qualificador": "Qualificador",
    "investimento": "Especialista em investimento",
    "agendamento": "Agendamento",
    "encerramento": "Encerramento",
    "followup": "Follow-up",
    "seguranca": "Guardrail de segurança",
}


def repositorio() -> Repositorio:
    return get_repositorio()


def texto_temperatura(temperatura: str) -> str:
    return f"{ICONES_TEMPERATURA.get(temperatura, '')} {temperatura.capitalize()}"


def texto_etapa(etapa: str) -> str:
    return f"{ICONES_ETAPA.get(etapa, '')} {ROTULOS_ETAPA.get(etapa, etapa)}"


def selos_lead(lead: dict) -> None:
    st.badge(texto_etapa(lead["etapa"]), color=CORES_ETAPA.get(lead["etapa"], "gray"))
    st.badge(f"{texto_temperatura(lead['temperatura'])} · {lead['score']}/100", color=CORES_TEMPERATURA.get(lead["temperatura"], "gray"))


def dados_lead_markdown(dados: dict) -> str:
    linhas = [f"- **{ROTULOS[c].split(' (')[0].capitalize()}:** {formatar_valor(c, v)}" for c, v in dados.items() if v not in (None, "") and c in ROTULOS]
    return "\n".join(linhas) or "_Nenhum dado coletado ainda._"


def texto_reuniao(reuniao: dict) -> str:
    imovel = f" · imóvel {reuniao['imovel_codigo']}" if reuniao.get("imovel_codigo") else ""
    return f"{reuniao['tipo'].capitalize()} {agenda.formatar_horario(reuniao['inicio'])} com {reuniao['corretor']}{imovel}"


def tempo_relativo(momento_iso: str | None) -> str:
    if not momento_iso:
        return "—"
    minutos = int((datetime.now() - datetime.fromisoformat(momento_iso)).total_seconds() // 60)
    if minutos < 1:
        return "agora"
    if minutos < 60:
        return f"há {minutos} min"
    if minutos < 60 * 24:
        return f"há {minutos // 60} h"
    return f"há {minutos // (60 * 24)} d"


def nome_lead(lead: dict) -> str:
    nome = lead.get("nome") or (lead.get("dados") or {}).get("nome")
    return f"{nome} ({lead['id']})" if nome else lead["id"]
