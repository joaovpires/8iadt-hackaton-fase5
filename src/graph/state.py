from typing import TypedDict, Optional, List, Literal

#  O "estado" que viaja entre os agentes, define o formato dos dados que passam de um nó do grafo pro outro
class SDRState(TypedDict):
    lead_id: str
    mensagem_atual: str
    historico: List[dict]              

    # extraído pela qualificação
    intencao: Optional[Literal["compra", "aluguel", "investimento"]]
    regiao: Optional[str]
    preco_max: Optional[float]
    quartos: Optional[int]
    urgencia: Optional[str]

    # resultado de tools
    imoveis_encontrados: Optional[list]
    reuniao_agendada: Optional[str]

    resposta_final: Optional[str]
    resumo_corretor: Optional[str]