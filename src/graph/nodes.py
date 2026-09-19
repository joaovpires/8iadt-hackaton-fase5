from src.graph.state import SDRState
from src.llm.client import get_llm

llm = get_llm()

# ---------- ROTEADOR ----------
def rotear_intencao(state: SDRState) -> SDRState:
    """Identifica se é compra/aluguel ou investimento e decide o próximo nó."""
    prompt = f"""
    Classifique a intenção do lead como "compra_aluguel" ou "investimento",
    considerando o contexto completo da conversa, não apenas a última mensagem.
    
    Histórico da conversa: {state['historico']}
    Última mensagem do lead: "{state['mensagem_atual']}"

    Responda apenas com uma das duas palavras.
    """
    resposta = llm.invoke(prompt).content.strip().lower()
    state["intencao"] = "investimento" if "investimento" in resposta else "compra"
    print(f"[DEBUG] mensagem: '{state['mensagem_atual']}' → intenção classificada: {state['intencao']}")
    return state

def decidir_agente(state: SDRState) -> str:
    return "agente_investimento" if state["intencao"] == "investimento" else "agente_qualificador"

# ---------- AGENTE QUALIFICADOR (compra/aluguel) ----------
def agente_qualificador(state: SDRState) -> SDRState:
    prompt = f"""
    Você é um SDR imobiliário humanizado e simpático. Converse naturalmente
    com o lead para descobrir: região de interesse, faixa de preço, número
    de quartos e urgência. Histórico: {state['historico']}
    Mensagem atual do lead: "{state['mensagem_atual']}"
    Responda de forma natural, uma pergunta por vez.
    """
    resposta = llm.invoke(prompt).content
    state["resposta_final"] = resposta
    return state

# ---------- AGENTE ESPECIALISTA EM INVESTIMENTO ----------
def agente_investimento(state: SDRState) -> SDRState:
    prompt = f"""
    Você é um especialista em investimento imobiliário, humanizado e direto.
    Converse naturalmente com o lead para descobrir: ticket de investimento,
    expectativa de retorno e perfil (residencial/comercial, experiência prévia).

    IMPORTANTE: faça apenas UMA pergunta por vez, em tom de conversa (não
    liste várias perguntas de uma vez, não use bullet points ou negrito).
    Considere o que já foi respondido no histórico antes de perguntar de novo.

    Histórico: {state['historico']}
    Mensagem atual do lead: "{state['mensagem_atual']}"
    """
    resposta = llm.invoke(prompt).content
    state["resposta_final"] = resposta
    return state

# ---------- NÓ DE RESUMO ----------
def gerar_resumo(state: SDRState) -> SDRState:
    prompt = f"""
    Gere um resumo objetivo para o corretor com base nesta conversa:
    {state['historico']}
    Inclua: intenção, região, orçamento, quartos/perfil, urgência e próximos passos.
    """
    state["resumo_corretor"] = llm.invoke(prompt).content
    return state