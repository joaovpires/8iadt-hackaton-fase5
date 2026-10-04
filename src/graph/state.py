from typing import List, Literal, Optional, TypedDict

from pydantic import BaseModel, Field

Intencao = Literal["compra", "aluguel", "investimento"]
Etapa = Literal["novo", "em_qualificacao", "qualificado", "agendado", "perdido"]


class DadosLead(BaseModel):
    intencao: Optional[Intencao] = Field(None, description="compra (comprar para morar/usar), aluguel (alugar) ou investimento (foco em renda ou valorização). Nulo se ainda não ficou claro se é compra ou aluguel.")
    nome: Optional[str] = Field(None, description="Primeiro nome do cliente, se ele informou")
    contato: Optional[str] = Field(None, description="Telefone ou e-mail que o cliente informou para contato")
    tipo_imovel: Optional[Literal["apartamento", "casa", "studio", "comercial"]] = Field(None, description="Tipo de imóvel desejado")
    regiao: Optional[str] = Field(None, description="Região, zona ou bairro de interesse, como o cliente disse (ex: zona sul, Moema, perto da Paulista)")
    preco_max: Optional[float] = Field(None, description="Valor máximo em reais. Para aluguel é o valor mensal")
    quartos: Optional[int] = Field(None, description="Número mínimo de quartos desejado")
    urgencia: Optional[Literal["alta", "media", "baixa"]] = Field(None, description="alta: imediato ou até 1 mês; media: 1 a 6 meses; baixa: mais de 6 meses ou só pesquisando")
    preferencias: Optional[str] = Field(None, description="Outros desejos citados pelo cliente, resumidos (ex: varanda, aceita pet, perto do metrô, vaga)")
    forma_pagamento: Optional[str] = Field(None, description="Como pretende pagar, se citou (à vista, financiamento, FGTS, consórcio)")
    ticket: Optional[float] = Field(None, description="Valor disponível para investir, em reais")
    retorno_esperado: Optional[str] = Field(None, description="Expectativa de retorno do investimento (ex: renda mensal de aluguel, 0,6% ao mês, valorização no longo prazo)")
    perfil_investidor: Optional[str] = Field(None, description="Perfil do investidor: residencial ou comercial e se já tem experiência com imóveis")
    imovel_interesse: Optional[str] = Field(None, description="Código do imóvel apresentado pelo qual o cliente demonstrou interesse (ex: V004)")


class SinaisMensagem(BaseModel):
    quer_agendar: Optional[bool] = Field(None, description="true se na última mensagem o cliente aceitou ou pediu visita/reunião; false se recusou agendar agora")
    opcao_horario: Optional[int] = Field(None, description="Número da opção de horário (1, 2, 3...) que o cliente escolheu entre os horários oferecidos, se escolheu")
    dia_preferido: Optional[Literal["segunda", "terca", "quarta", "quinta", "sexta", "sabado"]] = Field(None, description="Dia da semana que o cliente pediu, se pediu outro horário")
    periodo_preferido: Optional[Literal["manha", "tarde"]] = Field(None, description="Período que o cliente pediu, se pediu outro horário")
    desinteresse: bool = Field(False, description="true somente se o cliente disse claramente que não tem mais interesse ou pediu para não ser mais contatado")


class Extracao(BaseModel):
    dados: DadosLead
    sinais: SinaisMensagem


CAMPOS_LEAD = list(DadosLead.model_fields)

CAMPOS_POR_INTENCAO = {
    "compra": ["regiao", "preco_max", "quartos", "urgencia"],
    "aluguel": ["regiao", "preco_max", "quartos", "urgencia"],
    "investimento": ["perfil_investidor", "ticket", "retorno_esperado"],
}

TIPOS_SEM_QUARTOS = ("studio", "comercial")


def campos_requeridos(lead: dict) -> list[str]:
    requeridos = CAMPOS_POR_INTENCAO.get(lead.get("intencao"), [])
    if lead.get("tipo_imovel") in TIPOS_SEM_QUARTOS:
        requeridos = [c for c in requeridos if c != "quartos"]
    return requeridos


ROTULOS = {
    "intencao": "objetivo (comprar, alugar ou investir)",
    "nome": "nome",
    "contato": "contato",
    "tipo_imovel": "tipo de imóvel",
    "regiao": "região de interesse",
    "preco_max": "valor máximo",
    "quartos": "número de quartos",
    "urgencia": "urgência/prazo da mudança",
    "preferencias": "preferências",
    "forma_pagamento": "forma de pagamento",
    "ticket": "valor disponível para investir",
    "retorno_esperado": "expectativa de retorno",
    "perfil_investidor": "perfil de investidor (residencial ou comercial, experiência)",
    "imovel_interesse": "imóvel de interesse",
}

ROTULOS_ETAPA = {
    "novo": "Novo",
    "em_qualificacao": "Em qualificação",
    "qualificado": "Qualificado",
    "agendado": "Agendado",
    "perdido": "Perdido",
}


class SDRState(TypedDict, total=False):
    lead_id: str
    canal: str
    evento: Literal["mensagem", "followup"]
    mensagem_atual: str
    historico: List[dict]
    mensagens_lead: int

    lead: dict
    sinais: dict
    etapa: Etapa
    etapa_anterior: Etapa
    faltando: List[str]

    score: int
    temperatura: str
    motivos_score: List[str]

    imoveis_sugeridos: List[dict]
    horarios_ofertados: List[dict]
    reuniao: Optional[dict]
    tentativas_followup: int
    minutos_inativo: int

    bloqueado: bool
    agente: str
    resposta_final: str
    resumo_corretor: Optional[str]
