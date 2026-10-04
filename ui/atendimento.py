from datetime import datetime
from html import escape

import streamlit as st

from src.config import ASSISTENTE_NOME, EMPRESA_NOME, llm_configurado, transcricao_disponivel, voz_disponivel
from src.graph.nodes import formatar_valor
from src.graph.state import CAMPOS_POR_INTENCAO, ROTULOS_ETAPA, campos_requeridos
from src.llm import client
from src.services.atendimento import novo_lead_id, processar_mensagem
from src.tools import agenda
from ui import estilo
from ui.comum import ICONES_TEMPERATURA, repositorio

SUGESTOES = [
    ("🏙️", "Estou procurando apartamento na zona sul."),
    ("📈", "Quero investir em imóveis para renda."),
    ("🔑", "Preciso alugar um studio perto da Paulista, pra já."),
]
ROTULOS_CURTOS = {
    "intencao": "Objetivo", "nome": "Nome", "contato": "Contato", "tipo_imovel": "Tipo", "regiao": "Região",
    "preco_max": "Valor máximo", "quartos": "Quartos", "urgencia": "Prazo", "preferencias": "Desejos",
    "forma_pagamento": "Pagamento", "ticket": "Para investir", "retorno_esperado": "Retorno esperado",
    "perfil_investidor": "Perfil", "imovel_interesse": "Favorito",
}
CAMPOS_LARGOS = {"preferencias", "retorno_esperado", "perfil_investidor"}
VALORES_INTENCAO = {"compra": "Comprar", "aluguel": "Alugar", "investimento": "Investir"}
URGENCIA_CURTA = {"alta": "Até 1 mês", "media": "De 1 a 6 meses", "baixa": "Sem pressa"}
CORES_TEMPERATURA = {"quente": "vermelho", "morno": "laranja", "frio": "azul"}
CORES_ETAPA = {"em_qualificacao": "azul", "qualificado": "verde", "agendado": "verde"}
SAUDACAO = f"Oi! Eu sou a {ASSISTENTE_NOME}, assistente virtual da {EMPRESA_NOME} 😊 Me conta: você está procurando um imóvel para comprar, alugar ou investir?"

estilo.aplicar_estilo()
repo = repositorio()

if "lead_id" not in st.session_state:
    st.session_state.lead_id = novo_lead_id("web")
lead_id = st.session_state.lead_id
lead = repo.obter_lead(lead_id)
historico = repo.historico(lead_id)
reuniao = repo.reuniao_do_lead(lead_id) if lead else None


def trocar_lead():
    st.session_state.lead_id = st.session_state.seletor_lead


def nova_conversa():
    st.session_state.lead_id = novo_lead_id("web")


def enviar(texto: str):
    st.session_state.mensagem_pendente = texto


def valor_exibido(campo: str, valor) -> str:
    if campo == "intencao":
        return VALORES_INTENCAO.get(valor, valor)
    if campo == "urgencia":
        return URGENCIA_CURTA.get(valor, valor)
    if campo == "quartos":
        return f"{valor} ou mais"
    if campo == "tipo_imovel":
        return str(valor).capitalize()
    if campo == "preco_max" and (lead or {}).get("dados", {}).get("intencao") == "aluguel":
        return formatar_valor(campo, valor) + "/mês"
    return formatar_valor(campo, valor)


def rotulo_conversa(lead_web: dict) -> str:
    nome = lead_web.get("nome") or lead_web["dados"].get("nome")
    inicio = datetime.fromisoformat(lead_web["criado_em"]).strftime("%d/%m às %H:%M")
    return f"{nome} · {inicio}" if nome else f"Conversa de {inicio}"


def hora(momento_iso: str) -> str:
    return datetime.fromisoformat(momento_iso).strftime("%H:%M")


def meta_mensagem(mensagem: dict) -> str:
    if mensagem["papel"] == "user":
        return hora(mensagem["criado_em"])
    rotulos = {"followup": "Follow-up automático", "seguranca": "Proteção de segurança"}
    return f"{rotulos.get(mensagem['agente'], ASSISTENTE_NOME)} · {hora(mensagem['criado_em'])}"


def painel_atendimento() -> str:
    if not lead or not historico:
        return (
            '<div class="painel-titulo">Seu atendimento</div>'
            + estilo.barra_progresso("Perfil para recomendação", 0, 5)
            + '<div class="vazio" style="padding:1rem .5rem">Comece a conversa: conforme você responde, '
            "a Lia monta seu perfil aqui e separa imóveis que combinam com você.</div>"
        )
    dados = lead["dados"]
    intencao = dados.get("intencao")
    requisitos = ["intencao"] + (campos_requeridos(dados) if intencao else CAMPOS_POR_INTENCAO["compra"])
    preenchidos = sum(1 for c in requisitos if dados.get(c) is not None)
    pilulas = [
        estilo.pilula(ROTULOS_ETAPA.get(lead["etapa"], lead["etapa"]), CORES_ETAPA.get(lead["etapa"], "")),
        estilo.pilula(f"{ICONES_TEMPERATURA.get(lead['temperatura'], '')} {lead['temperatura'].capitalize()} · {lead['score']}", CORES_TEMPERATURA.get(lead["temperatura"], "")),
    ]
    campos = sorted((c for c in ROTULOS_CURTOS if dados.get(c) not in (None, "")), key=lambda c: c in CAMPOS_LARGOS)
    blocos = "".join(
        f'<div class="dado{" largo" if c in CAMPOS_LARGOS else ""}"><small>{ROTULOS_CURTOS[c]}</small><b>{escape(valor_exibido(c, dados[c]))}</b></div>'
        for c in campos
    )
    titulo = f"Atendimento de {escape(dados['nome'])}" if dados.get("nome") else "Seu atendimento"
    return (
        f'<div class="painel-titulo">{titulo}</div><div class="pilulas">{"".join(pilulas)}</div>'
        + estilo.barra_progresso("Perfil para recomendação", preenchidos, len(requisitos))
        + (f'<div class="dados">{blocos}</div>' if blocos else "")
    )


if historico:
    st.html(
        f'<div class="hero-compacto"><div><b>Conversa com a {ASSISTENTE_NOME}</b><br>'
        "<span>Atendimento 24h · compra, aluguel e investimento em São Paulo</span></div>"
        f'<span class="pilula azul">● Online</span></div>'
    )
else:
    st.html(
        f"""<div class="hero">
  <div class="hero-texto">
    <span class="selo">✦ Atendimento 24h com inteligência artificial</span>
    <h1>Encontre seu próximo <span>lar</span> conversando com a {ASSISTENTE_NOME}</h1>
    <p>Compra, aluguel ou investimento em São Paulo. A {ASSISTENTE_NOME} entende o que você procura,
    mostra imóveis que combinam com você e já agenda a visita com um corretor.</p>
  </div>
  <div class="hero-foto" style="background-image:url('{estilo.url_foto(estilo.FOTO_HERO, 900, 620)}')"></div>
</div>"""
    )

if not llm_configurado():
    st.error("Configure a chave do modelo (`OPENAI_API_KEY` ou `LLM_API_KEY`) no arquivo `.env` e reinicie o app. Veja o README para usar o Gemini gratuito.", icon="🔑")
    st.stop()

col_chat, col_painel = st.columns([1.6, 1], gap="large")

with col_chat:
    seletor, botao = st.columns([3, 1.2], vertical_alignment="bottom")
    leads_web = [l for l in repo.listar_leads() if l["canal"] == "web"]
    opcoes = [lead_id] + [l["id"] for l in leads_web if l["id"] != lead_id]
    nomes = {l["id"]: rotulo_conversa(l) for l in leads_web}
    st.session_state.seletor_lead = lead_id
    seletor.selectbox(
        "Conversa", opcoes, key="seletor_lead", on_change=trocar_lead, label_visibility="collapsed",
        format_func=lambda i: f"💬 {nomes[i]}" if i in nomes else "💬 Conversa atual",
        help="A memória é persistente: escolha uma conversa para continuar de onde parou.",
    )
    botao.button("Nova conversa", icon=":material/add:", on_click=nova_conversa, width="stretch")

    caixa = st.container(height=380 if historico else 190, border=True, autoscroll=True, key="janela-chat" if historico else "janela-chat-vazia")
    with caixa:
        if historico:
            st.html('<div class="chat">' + "".join(estilo.bolha(m["papel"], m["conteudo"], meta_mensagem(m)) for m in historico) + "</div>")
        else:
            st.html('<div class="chat">' + estilo.bolha("assistant", SAUDACAO, ASSISTENTE_NOME) + "</div>")

    if not historico:
        st.caption("Sugestões para começar")
        for icone, sugestao in SUGESTOES:
            st.button(f"{icone}  {sugestao}", on_click=enviar, args=(sugestao,), width="stretch", type="secondary")
    elif lead and lead["horarios_ofertados"] and not reuniao:
        st.caption("Escolha um horário para a visita")
        colunas = st.columns(len(lead["horarios_ofertados"]))
        for n, (coluna, horario) in enumerate(zip(colunas, lead["horarios_ofertados"]), 1):
            quando = agenda.formatar_horario(horario["inicio"])
            curto = quando.replace("-feira", "").capitalize()
            coluna.button(curto, key=f"horario-{n}", on_click=enviar, args=(f"Pode ser a opção {n}: {quando}",), width="stretch", icon=":material/event:")

    aceita_audio = transcricao_disponivel()
    entrada = st.chat_input("Escreva ou grave um áudio…" if aceita_audio else "Escreva sua mensagem…", accept_audio=aceita_audio)

    if lead and lead["imoveis_sugeridos"]:
        investidor = lead["dados"].get("intencao") == "investimento"
        titulo = "Oportunidades para você" if investidor else "Selecionados para você"
        st.html(
            f'<div class="secao">{titulo}</div>'
            + estilo.cards_imoveis(lead["imoveis_sugeridos"], grade=True, favorito=lead["dados"].get("imovel_interesse"), investimento=investidor)
        )

with col_painel:
    with st.container(border=True):
        st.html(painel_atendimento())
        if reuniao:
            st.html(estilo.card_visita(reuniao))
    if voz_disponivel():
        st.toggle("🔊 Ouvir as respostas da Lia", key="responder_em_audio")

if audio := st.session_state.pop("audio_resposta", None):
    st.audio(audio, format="audio/mp3", autoplay=True)

texto = st.session_state.pop("mensagem_pendente", None)
if entrada:
    texto = entrada.text if aceita_audio else entrada
    if aceita_audio and entrada.audio:
        with col_chat, st.spinner("Transcrevendo áudio…"):
            texto = client.transcrever(entrada.audio.getvalue(), "audio.wav")

if texto:
    with caixa:
        st.html('<div class="chat">' + estilo.bolha("user", texto, "agora") + "</div>")
        digitando = st.empty()
        digitando.html(estilo.bolha_digitando())
    try:
        resultado = processar_mensagem(lead_id, texto, canal="web", repo=repo)
    except Exception as erro:
        digitando.empty()
        with col_chat:
            if client.limite_atingido(erro):
                st.warning("O limite de uso do plano gratuito do modelo foi atingido. Espere cerca de 1 minuto e envie a mensagem de novo.", icon="⏳")
            else:
                st.error(f"Não consegui responder agora ({type(erro).__name__}). Tente de novo em instantes.", icon="⚠️")
        st.stop()
    if st.session_state.get("responder_em_audio"):
        try:
            st.session_state.audio_resposta = client.sintetizar(resultado.resposta)
        except Exception:
            st.toast("Não foi possível gerar o áudio da resposta.", icon="⚠️")
    st.rerun()
