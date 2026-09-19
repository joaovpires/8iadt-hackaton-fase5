import streamlit as st
from src.graph.sdr_graph import sdr_app

st.set_page_config(page_title="Agente SDR Imobiliário", layout="wide")

if "historico" not in st.session_state:
    st.session_state.historico = []

st.title("Agente SDR Imobiliário")

for msg in st.session_state.historico:
    with st.chat_message(msg["papel"]):
        st.write(msg["conteudo"])

mensagem = st.chat_input("Digite sua mensagem...")

if mensagem:
    st.session_state.historico.append({"papel": "user", "conteudo": mensagem})
    with st.chat_message("user"):
        st.write(mensagem)

    estado_inicial = {
        "lead_id": "teste-001",
        "mensagem_atual": mensagem,
        "historico": st.session_state.historico,
    }

    resultado = sdr_app.invoke(estado_inicial)
    resposta = resultado.get("resposta_final", "Desculpe, não consegui responder.")

    st.session_state.historico.append({"papel": "assistant", "conteudo": resposta})
    with st.chat_message("assistant"):
        st.write(resposta)