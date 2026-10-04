import logging

from langchain_core.runnables import RunnableConfig

from src.config import EMPRESA_NOME, FOLLOWUP_MAX_TENTATIVAS
from src.graph import prompts
from src.graph.state import CAMPOS_POR_INTENCAO, ROTULOS, ROTULOS_ETAPA, Extracao, SDRState, campos_requeridos
from src.llm import client
from src.security import guardrails
from src.services.score import calcular_score
from src.tools import agenda, imoveis

logger = logging.getLogger(__name__)

CAMPOS_BUSCA = ("intencao", "tipo_imovel", "regiao", "preco_max", "quartos", "preferencias", "ticket", "perfil_investidor")
URGENCIA_TEXTO = {"alta": "alta (até 1 mês)", "media": "média (de 1 a 6 meses)", "baixa": "baixa (mais de 6 meses ou pesquisando)"}


def formatar_valor(campo: str, valor) -> str:
    if campo in ("preco_max", "ticket"):
        return imoveis.formatar_preco(valor)
    if campo == "urgencia":
        return URGENCIA_TEXTO.get(valor, str(valor))
    return str(valor)


def formatar_dados(lead: dict, campos: list[str] | None = None) -> str:
    campos = campos or list(ROTULOS)
    linhas = [f"- {ROTULOS[c]}: {formatar_valor(c, lead[c])}" for c in campos if lead.get(c) not in (None, "")]
    return "\n".join(linhas) or "- nada ainda"


def campos_faltantes(lead: dict) -> list[str]:
    if not lead.get("intencao"):
        return ["intencao"]
    return [c for c in campos_requeridos(lead) if lead.get(c) is None]


def descrever_faltantes(campos: list[str]) -> str:
    return ", ".join(ROTULOS[c] for c in campos) or "nada, a qualificação está completa"


def formatar_transcricao(historico: list[dict], mensagem_atual: str | None = None) -> str:
    papeis = {"user": "Cliente", "assistant": "Assistente"}
    linhas = [f"{papeis[m['papel']]}: {m['conteudo']}" for m in historico if m["papel"] in papeis]
    if mensagem_atual:
        linhas.append(f"Cliente: {mensagem_atual}")
    return "\n".join(linhas) or "(sem mensagens)"


def formatar_horarios(horarios: list[dict]) -> str:
    return "\n".join(f"{n}. {agenda.formatar_horario(h['inicio'])}" for n, h in enumerate(horarios, 1)) or "nenhum"


def formatar_imoveis(lista: list[dict]) -> str:
    return "\n".join(f"- {imoveis.resumo_imovel(i)}" for i in lista) or "nenhum"


def humanizar_tempo(minutos: int) -> str:
    if minutos < 60:
        return f"{max(minutos, 1)} minutos"
    if minutos < 60 * 24:
        horas = round(minutos / 60)
        return f"{horas} hora{'s' if horas > 1 else ''}"
    dias = round(minutos / (60 * 24))
    return f"{dias} dia{'s' if dias > 1 else ''}"


def _repo(config: RunnableConfig):
    return config["configurable"]["repo"]


def decidir_entrada(state: SDRState) -> str:
    return "followup" if state.get("evento") == "followup" else "mensagem"


def verificar_seguranca(state: SDRState) -> dict:
    texto = state.get("mensagem_atual", "")
    if guardrails.detectar_injecao(texto):
        logger.warning("Tentativa de prompt injection bloqueada lead=%s", state["lead_id"])
        return {"bloqueado": True, "agente": "seguranca", "resposta_final": prompts.RESPOSTA_SEGURA}
    return {"bloqueado": False, "mensagem_atual": guardrails.sanitizar(texto)}


def decidir_apos_seguranca(state: SDRState) -> str:
    return "bloqueado" if state.get("bloqueado") else "seguir"


def analisar_mensagem(state: SDRState) -> dict:
    sistema = prompts.EXTRACAO.format(
        horarios=formatar_horarios(state.get("horarios_ofertados") or []),
        imoveis=formatar_imoveis(state.get("imoveis_sugeridos") or []),
    )
    conversa = formatar_transcricao(state.get("historico", []), state["mensagem_atual"])
    extracao = client.extrair(sistema, f"Conversa:\n{conversa}", Extracao)

    anterior = dict(state.get("lead") or {})
    lead = dict(anterior)
    for campo, valor in extracao.dados.model_dump().items():
        if valor not in (None, ""):
            lead[campo] = valor
    if lead.get("imovel_interesse") and not imoveis.obter(lead["imovel_interesse"]):
        lead.pop("imovel_interesse")
    if lead.get("tipo_imovel") == "studio" and lead.get("quartos") is None:
        lead["quartos"] = 1

    criterios_mudaram = any(anterior.get(c) != lead.get(c) for c in CAMPOS_BUSCA)
    logger.info("lead=%s intencao=%s faltando=%s", state["lead_id"], lead.get("intencao"), campos_faltantes(lead))
    return {"lead": lead, "sinais": extracao.sinais.model_dump(), "imoveis_sugeridos": [] if criterios_mudaram else state.get("imoveis_sugeridos", [])}


def qualificar(state: SDRState) -> dict:
    lead = state["lead"]
    sinais = state.get("sinais") or {}
    etapa_anterior = state.get("etapa") or "novo"
    faltando = campos_faltantes(lead)
    if sinais.get("desinteresse"):
        etapa = "perdido"
    elif state.get("reuniao"):
        etapa = "agendado"
    elif not faltando:
        etapa = "qualificado"
    else:
        etapa = "em_qualificacao"
    return {"etapa": etapa, "etapa_anterior": etapa_anterior, "faltando": faltando}


def decidir_agente(state: SDRState) -> str:
    etapa = state["etapa"]
    if etapa == "perdido":
        return "agente_encerramento"
    if etapa in ("qualificado", "agendado"):
        return "buscar_imoveis"
    if state["lead"].get("intencao") == "investimento":
        return "agente_investimento"
    return "agente_qualificador"


def buscar_imoveis(state: SDRState) -> dict:
    if state.get("imoveis_sugeridos"):
        return {}
    lead = state["lead"]
    encontrados = imoveis.buscar(lead)
    interesse = imoveis.obter(lead.get("imovel_interesse") or "")
    if interesse and all(i["codigo"] != interesse["codigo"] for i in encontrados):
        encontrados = [{**interesse, "fora_da_regiao": False}, *encontrados][:3]
    return {"imoveis_sugeridos": encontrados}


def agente_qualificador(state: SDRState) -> dict:
    lead = state["lead"]
    intencao = lead.get("intencao")
    contexto = {
        "compra": "que quer comprar um imóvel",
        "aluguel": "que quer alugar um imóvel",
    }.get(intencao, "que ainda não disse se quer comprar, alugar ou investir")
    dica_preco = (
        "Em aluguel, o valor é mensal: pergunte quanto cabe no orçamento por mês."
        if intencao == "aluguel"
        else "Em compra, pergunte o valor máximo do imóvel; se surgir naturalmente, entenda a forma de pagamento."
    )
    sistema = prompts.QUALIFICADOR.format(
        persona=prompts.persona(),
        contexto=contexto,
        dados=formatar_dados(lead),
        faltando=descrever_faltantes(state["faltando"]),
        dica_preco=dica_preco,
    )
    resposta = client.responder(sistema, state.get("historico", []), state["mensagem_atual"])
    return {"resposta_final": resposta, "agente": "qualificador"}


def agente_investimento(state: SDRState) -> dict:
    sistema = prompts.INVESTIMENTO.format(
        persona=prompts.persona(),
        empresa=EMPRESA_NOME,
        dados=formatar_dados(state["lead"]),
        faltando=descrever_faltantes(state["faltando"]),
    )
    resposta = client.responder(sistema, state.get("historico", []), state["mensagem_atual"])
    return {"resposta_final": resposta, "agente": "investimento"}


def _local_reuniao(reuniao: dict) -> str:
    imovel = imoveis.obter(reuniao.get("imovel_codigo") or "")
    if reuniao["tipo"] == "visita" and imovel:
        return f" no imóvel {imovel['codigo']} em {imovel['bairro']}"
    if reuniao["tipo"] == "visita":
        return " para conhecer os imóveis selecionados"
    return " no escritório ou por vídeo, como o cliente preferir"


def _bloco_imoveis(sugeridos: list[dict], intencao: str | None) -> str:
    if not sugeridos:
        return (
            "Não há imóveis na base que atendam a todos os critérios do cliente. Diga isso com naturalidade e explique "
            "que o corretor vai fazer uma curadoria personalizada, inclusive com imóveis que ainda não estão no site."
        )
    titulo = "Oportunidades selecionadas para este cliente" if intencao == "investimento" else "Imóveis selecionados para este cliente"
    aviso = ""
    if sugeridos[0].get("acima_do_orcamento"):
        aviso += (
            "\nAtenção: não há opções dentro do valor informado; estes são os mais próximos, acima do orçamento. "
            "Diga isso com transparência, cite o valor e pergunte se faz sentido considerar ou ajustar o orçamento."
        )
    if sugeridos[0].get("fora_da_regiao"):
        aviso += "\nAtenção: não há opções na região pedida; estes são de outras regiões. Deixe isso claro e pergunte se faria sentido."
    return f"{titulo} (cite somente estes, pelo código):\n{formatar_imoveis(sugeridos)}{aviso}"


def agente_agendamento(state: SDRState, config: RunnableConfig) -> dict:
    repo = _repo(config)
    lead = state["lead"]
    sinais = state.get("sinais") or {}
    intencao = lead.get("intencao")
    especialidade = agenda.especialidade_para(intencao)
    tipo = "reunião" if intencao == "investimento" else "visita"
    reuniao = state.get("reuniao")
    ofertados = list(state.get("horarios_ofertados") or [])
    etapa = state["etapa"]
    horarios = ofertados
    acabou_de_agendar = False
    horario_indisponivel = False

    if not reuniao:
        escolha = sinais.get("opcao_horario")
        if escolha and 1 <= escolha <= len(ofertados):
            slot = ofertados[escolha - 1]
            imovel = lead.get("imovel_interesse") if tipo == "visita" else None
            reuniao = repo.salvar_reuniao(state["lead_id"], tipo, slot["inicio"], slot["corretor"], imovel)
            if reuniao:
                etapa, acabou_de_agendar, horarios = "agendado", True, []
            else:
                horario_indisponivel = True
        pediu_outro = sinais.get("dia_preferido") or sinais.get("periodo_preferido")
        if not reuniao and sinais.get("quer_agendar") is not False and (not ofertados or pediu_outro or horario_indisponivel):
            horarios = agenda.horarios_disponiveis(
                repo.horarios_ocupados(), especialidade, dia=sinais.get("dia_preferido"), periodo=sinais.get("periodo_preferido")
            )

    if acabou_de_agendar:
        quando = agenda.formatar_horario(reuniao["inicio"])
        situacao = (
            f"A {tipo} acabou de ser agendada para {quando} com {reuniao['corretor']}{_local_reuniao(reuniao)}. "
            "Confirme com entusiasmo e clareza (dia, hora e com quem) e diga que o corretor vai entrar em contato para confirmar."
        )
        if not lead.get("nome"):
            situacao += " Pergunte o nome do cliente para deixar a agenda no nome dele."
    elif reuniao:
        quando = agenda.formatar_horario(reuniao["inicio"])
        situacao = (
            f"Já existe uma {reuniao['tipo']} agendada para {quando} com {reuniao['corretor']}{_local_reuniao(reuniao)}. "
            "Responda às dúvidas do cliente. Se ele quiser remarcar ou cancelar, diga que vai avisar o corretor, que fará o ajuste diretamente com ele."
        )
    elif sinais.get("quer_agendar") is False:
        horarios = []
        situacao = (
            "O cliente não quer agendar agora. Respeite, não insista e não ofereça horários. "
            "Diga que fica à disposição e pergunte se ele prefere receber mais opções de imóveis por aqui."
        )
    elif not horarios:
        situacao = "Não há horários livres na agenda dos próximos dias. Diga que o corretor vai entrar em contato para combinar o melhor horário."
    elif horarios == ofertados:
        situacao = "Você já apresentou os imóveis e ofereceu os horários abaixo. Responda ao que o cliente disse e, se fizer sentido, relembre as opções de horário."
    elif ofertados or horario_indisponivel:
        motivo = "O horário escolhido acabou de ser ocupado" if horario_indisponivel else "O cliente pediu outro horário"
        situacao = f"{motivo}. Ofereça as novas opções abaixo para ele escolher pelo número, sem reapresentar os imóveis."
    elif intencao == "investimento":
        situacao = (
            "O cliente acabou de ser qualificado. Apresente de forma breve as oportunidades abaixo, destacando a rentabilidade "
            "estimada (deixe claro que é bruta e estimada), e convide para uma conversa com a especialista em investimentos, "
            "oferecendo os horários abaixo para ele escolher pelo número."
        )
    else:
        situacao = (
            "O cliente acabou de ser qualificado. Apresente os imóveis abaixo destacando o que combina com o que ele pediu "
            "e convide para uma visita com um corretor, oferecendo os horários abaixo para ele escolher pelo número."
        )

    bloco_horarios = ""
    if horarios and not reuniao:
        bloco_horarios = f"Horários disponíveis para oferecer (mantenha esta numeração):\n{formatar_horarios(horarios)}"

    sistema = prompts.AGENDAMENTO.format(
        persona=prompts.persona(),
        situacao=situacao,
        dados=formatar_dados(state["lead"]),
        bloco_imoveis=_bloco_imoveis(state.get("imoveis_sugeridos") or [], intencao),
        bloco_horarios=bloco_horarios,
    )
    resposta = client.responder(sistema, state.get("historico", []), state["mensagem_atual"])
    return {"resposta_final": resposta, "agente": "agendamento", "horarios_ofertados": horarios, "reuniao": reuniao, "etapa": etapa}


def agente_encerramento(state: SDRState) -> dict:
    sistema = prompts.ENCERRAMENTO.format(persona=prompts.persona())
    resposta = client.responder(sistema, state.get("historico", []), state["mensagem_atual"])
    return {"resposta_final": resposta, "agente": "encerramento", "horarios_ofertados": []}


def agente_followup(state: SDRState) -> dict:
    lead = state.get("lead") or {}
    tentativa = state.get("tentativas_followup") or 1
    sugestoes = state.get("imoveis_sugeridos") or []
    if not sugestoes and lead.get("intencao") and any(lead.get(c) for c in ("regiao", "preco_max", "ticket")):
        sugestoes = imoveis.buscar(lead)
    if sugestoes:
        bloco = f"Imóveis que combinam com o cliente (pode citar um deles como gancho, pelo código):\n{formatar_imoveis(sugestoes[:2])}"
        gancho = " (por exemplo, um dos imóveis listados acima)"
    else:
        bloco = "Não cite imóveis específicos."
        gancho = " (por exemplo, ajudar a encontrar o imóvel certo para o momento dele)"
    tom = prompts.TONS_FOLLOWUP[3] if tentativa >= FOLLOWUP_MAX_TENTATIVAS else prompts.TONS_FOLLOWUP[min(tentativa, 2)]
    sistema = prompts.FOLLOWUP.format(
        persona=prompts.persona(),
        tempo=humanizar_tempo(state.get("minutos_inativo") or 0),
        tentativa=tentativa,
        maximo=FOLLOWUP_MAX_TENTATIVAS,
        dados=formatar_dados(lead),
        faltando=descrever_faltantes(campos_faltantes(lead)),
        bloco_imoveis=bloco,
        gancho=gancho,
        tom=tom,
    )
    resposta = client.responder(sistema, state.get("historico", []), instrucao_final="Escreva agora a mensagem de retomada para o cliente.")
    return {"resposta_final": resposta, "agente": "followup"}


def gerar_resumo(state: SDRState) -> str:
    historico = list(state.get("historico", []))
    if state.get("mensagem_atual") and state.get("evento") != "followup":
        historico.append({"papel": "user", "conteudo": state["mensagem_atual"]})
    if state.get("resposta_final"):
        historico.append({"papel": "assistant", "conteudo": state["resposta_final"]})
    reuniao = state.get("reuniao")
    texto_reuniao = ""
    if reuniao:
        texto_reuniao = f"Agendamento: {reuniao['tipo']} em {agenda.formatar_horario(reuniao['inicio'])} com {reuniao['corretor']}{_local_reuniao(reuniao)}\n"
    sistema = prompts.RESUMO.format(
        dados=formatar_dados(state.get("lead") or {}),
        score=state.get("score", 0),
        temperatura=state.get("temperatura", "frio"),
        motivos="; ".join(state.get("motivos_score") or []) or "sem dados",
        etapa=ROTULOS_ETAPA.get(state.get("etapa"), state.get("etapa")),
        reuniao=texto_reuniao,
        imoveis=formatar_imoveis(state.get("imoveis_sugeridos") or []),
    )
    return client.responder(sistema, [], f"Conversa completa:\n{formatar_transcricao(historico)}")


def consolidar(state: SDRState) -> dict:
    etapa = state["etapa"]
    score = calcular_score(state["lead"], etapa, (state.get("mensagens_lead") or 0) + 1)
    atualizacao = {"score": score.valor, "temperatura": score.temperatura, "motivos_score": score.motivos}
    if etapa in ("qualificado", "agendado") and etapa != state.get("etapa_anterior"):
        try:
            atualizacao["resumo_corretor"] = gerar_resumo({**state, **atualizacao})
        except Exception:
            logger.exception("Falha ao gerar resumo do lead=%s", state["lead_id"])
    return atualizacao
