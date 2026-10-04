from pathlib import Path

import streamlit as st

from src.config import EMPRESA_NOME
from src.observabilidade import configurar_logs

configurar_logs()

ASSETS = Path(__file__).resolve().parent / "ui" / "assets"

st.set_page_config(page_title=f"{EMPRESA_NOME} · Agente SDR", page_icon=str(ASSETS / "icone.svg"), layout="wide")
st.logo(str(ASSETS / "logo.svg"), size="large")

pagina = st.navigation(
    [
        st.Page("ui/atendimento.py", title="Fale com a Lia", icon=":material/chat:", default=True),
        st.Page("ui/dashboard.py", title="Painel do corretor", icon=":material/monitoring:"),
    ],
    position="top",
)
pagina.run()
