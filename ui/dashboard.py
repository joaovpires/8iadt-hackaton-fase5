import altair as alt
import pandas as pd
import streamlit as st

from src.config import FOLLOWUP_INATIVIDADE_MIN, FOLLOWUP_MAX_TENTATIVAS, llm_configurado
from src.graph.nodes import humanizar_tempo
from src.graph.state import ROTULOS_ETAPA
from src.observabilidade import tracing_ativo
from src.services.atendimento import atualizar_resumo
from src.services.followup import enviar_followup, executar_followups
from src.tools import agenda, imoveis
from ui import estilo
from ui.comum import (
    ICONES_TEMPERATURA,
    NOMES_AGENTE,
    ORDEM_ETAPAS,
    dados_lead_markdown,
    nome_lead,
    repositorio,
    selos_lead,
    tempo_relativo,
    texto_etapa,
    texto_reuniao,
    texto_temperatura,
)

COR_SERIE = "#2B4BF2"
NOMES_EVENTO = {
    "lead_criado": "Leads criados",
    "etapa_alterada": "Mudanças de etapa",
    "reuniao_agendada": "Reuniões agendadas",
    "followup_enviado": "Follow-ups enviados",
    "lead_perdido": "Leads perdidos por inatividade",
    "seguranca_bloqueio": "Tentativas de prompt injection bloqueadas",
    "resumo_gerado": "Resumos gerados sob demanda",
    "inatividade_simulada": "Inatividades simuladas (demo)",
}

estilo.aplicar_estilo()
repo = repositorio()
leads = repo.listar_leads()
reunioes = repo.listar_reunioes()
eventos = repo.contar_eventos()
metricas_agentes = repo.metricas_mensagens()

estilo.cabecalho("Painel do corretor", "Leads atendidos pela Lia, priorizados por temperatura, com o resumo pronto para você agir.")

if not leads:
    st.info("Nenhum lead ainda. Converse na página **Fale com a Lia** ou rode `python scripts/popular_demo.py` para carregar dados de demonstração.", icon="💡")
    st.stop()

total = len(leads)
por_etapa = pd.Series([l["etapa"] for l in leads]).value_counts().to_dict()
por_temperatura = pd.Series([l["temperatura"] for l in leads if l["etapa"] != "perdido"]).value_counts().to_dict()
agendados = por_etapa.get("agendado", 0)
respostas = sum(m["respostas"] for m in metricas_agentes)
latencia_media = sum((m["latencia_media_ms"] or 0) * m["respostas"] for m in metricas_agentes) / respostas if respostas else 0

colunas = st.columns(5)
colunas[0].metric("Leads", total, border=True)
colunas[1].metric("Quentes", por_temperatura.get("quente", 0), border=True, help="Score ≥ 70")
colunas[2].metric("Agendados", agendados, border=True)
colunas[3].metric("Conversão", f"{agendados / total:.0%}", border=True, help="Leads com visita/reunião agendada ÷ total de leads")
colunas[4].metric("Resposta média", f"{latencia_media / 1000:.1f} s", border=True, help="Tempo médio que o agente leva para responder cada mensagem")

esquerda, direita = st.columns([3, 2], gap="large")
with esquerda:
    st.html('<div class="secao">Funil por etapa</div>')
    funil = pd.DataFrame([{"Etapa": ROTULOS_ETAPA[e], "Leads": por_etapa.get(e, 0)} for e in ORDEM_ETAPAS])
    base = alt.Chart(funil).encode(
        y=alt.Y("Etapa:N", sort=[ROTULOS_ETAPA[e] for e in ORDEM_ETAPAS], title=None, axis=alt.Axis(labelLimit=200, labelPadding=8, labelFont="Plus Jakarta Sans", labelFontSize=12, ticks=False, domain=False)),
        x=alt.X("Leads:Q", title=None, axis=alt.Axis(tickMinStep=1, format="d", gridOpacity=0.4, domain=False)),
        tooltip=[alt.Tooltip("Etapa:N"), alt.Tooltip("Leads:Q")],
    )
    barras = base.mark_bar(color=COR_SERIE, cornerRadiusEnd=4, height=16)
    rotulos = base.mark_text(align="left", dx=6, fontWeight="bold").encode(text="Leads:Q")
    st.altair_chart((barras + rotulos).properties(height=190, padding={"left": 16, "right": 8, "top": 4, "bottom": 4}), width="stretch")

with direita:
    st.html('<div class="secao">Temperatura dos leads ativos</div>')
    t1, t2, t3 = st.columns(3)
    t1.metric(texto_temperatura("quente"), por_temperatura.get("quente", 0), border=True)
    t2.metric(texto_temperatura("morno"), por_temperatura.get("morno", 0), border=True)
    t3.metric(texto_temperatura("frio"), por_temperatura.get("frio", 0), border=True)
    st.html('<div class="secao">Intenção</div>')
    por_intencao = pd.Series([(l["dados"].get("intencao") or "indefinida") for l in leads]).value_counts().to_dict()
    i1, i2 = st.columns(2)
    i1.metric("🏠 Compra", por_intencao.get("compra", 0))
    i2.metric("🔑 Aluguel", por_intencao.get("aluguel", 0))
    i3, i4 = st.columns(2)
    i3.metric("📈 Investimento", por_intencao.get("investimento", 0))
    i4.metric("❔ Ainda indefinida", por_intencao.get("indefinida", 0))

aba_leads, aba_agenda, aba_followup, aba_obs = st.tabs(["Leads (CRM)", "Agenda", "Follow-up", "Observabilidade"])


def orcamento(dados: dict) -> str:
    if dados.get("ticket"):
        return imoveis.formatar_preco(dados["ticket"])
    if dados.get("preco_max"):
        return imoveis.formatar_preco(dados["preco_max"]) + ("/mês" if dados.get("intencao") == "aluguel" else "")
    return "—"


with aba_leads:
    ordenados = sorted(leads, key=lambda l: (l["etapa"] == "perdido", -l["score"]))
    tabela = pd.DataFrame([
        {
            "Lead": nome_lead(l),
            "Canal": l["canal"],
            "Intenção": l["dados"].get("intencao") or "—",
            "Região": l["dados"].get("regiao") or "—",
            "Orçamento": orcamento(l["dados"]),
            "Score": l["score"],
            "Temperatura": texto_temperatura(l["temperatura"]),
            "Etapa": texto_etapa(l["etapa"]),
            "Última interação": tempo_relativo(l["ultima_interacao_em"]),
            "Follow-ups": l["tentativas_followup"],
        }
        for l in ordenados
    ])
    st.caption("Ordenados por prioridade (score). Clique em uma linha para ver o detalhe e o resumo para o corretor.")
    selecao = st.dataframe(
        tabela,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="tabela_leads",
        column_config={
            "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
            "Follow-ups": st.column_config.NumberColumn(format="%d", help=f"Máximo de {FOLLOWUP_MAX_TENTATIVAS}"),
        },
    )
    st.download_button(
        "⬇️ Exportar CRM (CSV)",
        tabela.to_csv(index=False).encode("utf-8-sig"),
        file_name="leads_sdr.csv",
        mime="text/csv",
    )

    linhas = selecao.selection.rows if selecao and selecao.selection else []
    if linhas:
        lead = repo.obter_lead(ordenados[linhas[0]]["id"])
        with st.container(border=True):
            st.subheader(nome_lead(lead))
            selos_lead(lead)
            c1, c2 = st.columns(2, gap="large")
            with c1:
                st.markdown("**Dados coletados pela IA**")
                st.markdown(dados_lead_markdown(lead["dados"]))
                reuniao = repo.reuniao_do_lead(lead["id"])
                if reuniao:
                    st.success(texto_reuniao(reuniao), icon="📅")
            with c2:
                st.markdown("**Por que esse score?**")
                st.markdown("\n".join(f"- {m}" for m in lead["motivos_score"]) or "_Sem dados._")
            st.markdown("**Resumo para o corretor**")
            if lead["resumo"]:
                st.markdown(lead["resumo"])
            else:
                st.caption("O resumo é gerado automaticamente quando o lead fica qualificado. Você pode gerar agora:")
            if st.button("✨ Gerar/atualizar resumo", disabled=not llm_configurado(), help=None if llm_configurado() else "Configure a chave do modelo no .env"):
                with st.spinner("Gerando resumo…"):
                    atualizar_resumo(lead["id"], repo)
                st.rerun()
            if lead["imoveis_sugeridos"]:
                st.html('<div class="secao">Imóveis apresentados</div>' + estilo.cards_imoveis(lead["imoveis_sugeridos"], grade=True, favorito=lead["dados"].get("imovel_interesse"), investimento=lead["dados"].get("intencao") == "investimento"))
            with st.expander("Conversa completa"):
                for mensagem in repo.historico(lead["id"]):
                    with st.chat_message(mensagem["papel"], avatar="🏠" if mensagem["papel"] == "assistant" else "🙂"):
                        st.write(mensagem["conteudo"])
                        if mensagem["agente"]:
                            st.caption(f"{NOMES_AGENTE.get(mensagem['agente'], mensagem['agente'])} · {mensagem['criado_em']}")

with aba_agenda:
    if reunioes:
        st.dataframe(
            pd.DataFrame([
                {
                    "Quando": agenda.formatar_horario(r["inicio"]),
                    "Tipo": r["tipo"].capitalize(),
                    "Corretor": r["corretor"],
                    "Lead": r["lead_nome"] or r["lead_id"],
                    "Canal": r["canal"],
                    "Imóvel": r["imovel_codigo"] or "—",
                    "Status": r["status"],
                }
                for r in reunioes
            ]),
            hide_index=True,
        )
    else:
        st.caption("Nenhuma visita ou reunião agendada ainda.")
    st.caption("Corretores: " + " · ".join(f"{c['nome']} ({c['especialidade']})" for c in agenda.CORRETORES))

with aba_followup:
    st.markdown(
        f"Regra: lead **em qualificação** ou **qualificado** que não responde há **{humanizar_tempo(FOLLOWUP_INATIVIDADE_MIN)}** "
        f"recebe uma mensagem de retomada com o contexto da conversa, até **{FOLLOWUP_MAX_TENTATIVAS} tentativas**. "
        "Depois disso, o lead é marcado como perdido. Em produção, a rotina roda sozinha "
        "(`python -m src.services.followup --loop 300`); aqui você pode disparar e simular para a demo."
    )
    elegiveis = repo.leads_para_followup(FOLLOWUP_INATIVIDADE_MIN, FOLLOWUP_MAX_TENTATIVAS)
    st.markdown(f"**Aguardando follow-up agora:** {len(elegiveis)}")
    if elegiveis:
        st.dataframe(
            pd.DataFrame([
                {"Lead": nome_lead(l), "Etapa": texto_etapa(l["etapa"]), "Sem resposta": tempo_relativo(l["ultima_interacao_em"]), "Tentativas": l["tentativas_followup"]}
                for l in elegiveis
            ]),
            hide_index=True,
        )
    if st.button("▶️ Executar rotina de follow-up agora", type="primary", disabled=not llm_configurado()):
        with st.spinner("Gerando mensagens de retomada…"):
            resultado = executar_followups(repo)
        st.session_state.resultado_followup = resultado
        st.rerun()
    if resultado := st.session_state.pop("resultado_followup", None):
        st.success(f"{len(resultado['enviados'])} follow-up(s) enviado(s); {len(resultado['perdidos'])} lead(s) marcado(s) como perdido(s).")
        for envio in resultado["enviados"]:
            st.info(f"**{envio['lead_id']}** (tentativa {envio['tentativa']}): {envio['mensagem']}", icon="🔁")

    st.divider()
    st.markdown("**Simular inatividade (para a demonstração)**")
    candidatos = [l for l in leads if l["etapa"] in ("em_qualificacao", "qualificado") and l["ultimo_autor"] == "assistant"]
    if candidatos:
        escolhido = st.selectbox("Lead que 'parou de responder'", [l["id"] for l in candidatos], format_func=lambda i: nome_lead(next(l for l in candidatos if l["id"] == i)))
        c1, c2 = st.columns(2)
        if c1.button(f"⏩ Avançar {humanizar_tempo(FOLLOWUP_INATIVIDADE_MIN)} no relógio desse lead", width="stretch"):
            repo.simular_inatividade(escolhido, FOLLOWUP_INATIVIDADE_MIN + 1)
            st.rerun()
        if c2.button("✉️ Enviar follow-up só para ele", width="stretch", disabled=not llm_configurado()):
            with st.spinner("Gerando mensagem…"):
                envio = enviar_followup(repo, repo.obter_lead(escolhido))
            st.session_state.resultado_followup = {"enviados": [envio], "perdidos": []}
            st.rerun()
    else:
        st.caption("Nenhum lead aguardando resposta do cliente no momento.")

with aba_obs:
    o1, o2, o3 = st.columns(3)
    o1.metric("Respostas da IA", respostas, border=True)
    o2.metric("🛡️ Ataques bloqueados", eventos.get("seguranca_bloqueio", 0), border=True)
    o3.metric("LangSmith tracing", "ativo" if tracing_ativo() else "desligado", border=True, help="Defina LANGSMITH_TRACING=true e LANGSMITH_API_KEY no .env")
    st.markdown("**Desempenho por agente**")
    if metricas_agentes:
        st.dataframe(
            pd.DataFrame([
                {"Agente": NOMES_AGENTE.get(m["agente"], m["agente"]), "Respostas": m["respostas"], "Latência média (ms)": round(m["latencia_media_ms"] or 0)}
                for m in metricas_agentes
            ]),
            hide_index=True,
        )
    st.markdown("**Eventos do sistema**")
    st.dataframe(
        pd.DataFrame([{"Evento": NOMES_EVENTO.get(t, t), "Total": n} for t, n in sorted(eventos.items(), key=lambda x: -x[1])]),
        hide_index=True,
    )
    with st.expander("Últimos eventos"):
        st.dataframe(pd.DataFrame(repo.listar_eventos(50)), hide_index=True)
