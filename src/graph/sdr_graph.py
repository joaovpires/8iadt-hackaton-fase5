from langgraph.graph import StateGraph, END
from src.graph.state import SDRState
from src.graph.nodes import (
    rotear_intencao, decidir_agente,
    agente_qualificador, agente_investimento,
    gerar_resumo,
)

def montar_grafo():
    grafo = StateGraph(SDRState)

    grafo.add_node("roteador", rotear_intencao)
    grafo.add_node("agente_qualificador", agente_qualificador)
    grafo.add_node("agente_investimento", agente_investimento)
    grafo.add_node("resumo", gerar_resumo)

    grafo.set_entry_point("roteador")
    grafo.add_conditional_edges("roteador", decidir_agente, {
        "agente_qualificador": "agente_qualificador",
        "agente_investimento": "agente_investimento",
    })
    grafo.add_edge("agente_qualificador", END)
    grafo.add_edge("agente_investimento", END)
    # "resumo" é chamado à parte, quando o corretor quiser ver o resumo

    return grafo.compile()

sdr_app = montar_grafo()