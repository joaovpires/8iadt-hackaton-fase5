from langgraph.graph import END, START, StateGraph

from src.graph.nodes import (
    agente_agendamento,
    agente_encerramento,
    agente_followup,
    agente_investimento,
    agente_qualificador,
    analisar_mensagem,
    buscar_imoveis,
    consolidar,
    decidir_agente,
    decidir_apos_seguranca,
    decidir_entrada,
    qualificar,
    verificar_seguranca,
)
from src.graph.state import SDRState

AGENTES_CONVERSA = ("agente_qualificador", "agente_investimento", "agente_agendamento", "agente_encerramento")


def montar_grafo():
    grafo = StateGraph(SDRState)

    grafo.add_node("verificar_seguranca", verificar_seguranca)
    grafo.add_node("analisar_mensagem", analisar_mensagem)
    grafo.add_node("qualificar", qualificar)
    grafo.add_node("buscar_imoveis", buscar_imoveis)
    grafo.add_node("agente_qualificador", agente_qualificador)
    grafo.add_node("agente_investimento", agente_investimento)
    grafo.add_node("agente_agendamento", agente_agendamento)
    grafo.add_node("agente_encerramento", agente_encerramento)
    grafo.add_node("agente_followup", agente_followup)
    grafo.add_node("consolidar", consolidar)

    grafo.add_conditional_edges(START, decidir_entrada, {"mensagem": "verificar_seguranca", "followup": "agente_followup"})
    grafo.add_conditional_edges("verificar_seguranca", decidir_apos_seguranca, {"seguir": "analisar_mensagem", "bloqueado": END})
    grafo.add_edge("analisar_mensagem", "qualificar")
    grafo.add_conditional_edges("qualificar", decidir_agente, ["agente_qualificador", "agente_investimento", "buscar_imoveis", "agente_encerramento"])
    grafo.add_edge("buscar_imoveis", "agente_agendamento")
    for agente in AGENTES_CONVERSA:
        grafo.add_edge(agente, "consolidar")
    grafo.add_edge("consolidar", END)
    grafo.add_edge("agente_followup", END)

    return grafo.compile()


sdr_app = montar_grafo()
