import pytest
from langchain_core.messages import AIMessage

from src.graph.state import DadosLead, Extracao, SinaisMensagem
from src.llm import client


class ExtratorFalso:
    def __init__(self, resultado):
        self.resultado = resultado

    def invoke(self, mensagens):
        if isinstance(self.resultado, Exception):
            raise self.resultado
        return self.resultado


@pytest.fixture(autouse=True)
def limpar_preferencia():
    client._metodo_que_funcionou.clear()
    yield
    client._metodo_que_funcionou.clear()


def test_extracao_cai_para_json_schema_quando_function_calling_falha(monkeypatch):
    esperado = Extracao(dados=DadosLead(intencao="aluguel"), sinais=SinaisMensagem())
    tentativas = []

    def extrator(schema, metodo, modelo):
        tentativas.append(metodo)
        return ExtratorFalso(RuntimeError("tool_choice não suportado") if metodo == "function_calling" else esperado)

    monkeypatch.setattr(client, "_extrator", extrator)
    assert client.extrair("sistema", "conversa", Extracao) == esperado
    assert tentativas == ["function_calling", "json_schema"]

    tentativas.clear()
    client.extrair("sistema", "conversa", Extracao)
    assert tentativas == ["json_schema"]


def test_extracao_propaga_erro_quando_todos_os_metodos_falham(monkeypatch):
    monkeypatch.setattr(client, "_extrator", lambda schema, metodo, modelo: ExtratorFalso(None))
    with pytest.raises(ValueError):
        client.extrair("sistema", "conversa", Extracao)


def test_sobrecarga_troca_de_modelo_sem_tentar_outro_formato(monkeypatch):
    esperado = Extracao(dados=DadosLead(intencao="compra"), sinais=SinaisMensagem())
    chamadas = []

    def extrator(schema, metodo, modelo):
        chamadas.append((modelo, metodo))
        if modelo == "principal":
            return ExtratorFalso(RuntimeError("Error code: 503 - model is currently experiencing high demand"))
        return ExtratorFalso(esperado)

    monkeypatch.setattr(client, "modelos", lambda: ["principal", "reserva"])
    monkeypatch.setattr(client, "_extrator", extrator)
    assert client.extrair("sistema", "conversa", Extracao) == esperado
    assert chamadas == [("principal", "function_calling"), ("reserva", "function_calling")]


def test_resposta_usa_modelo_reserva_quando_principal_falha(monkeypatch):
    class LLMFalso:
        def __init__(self, modelo):
            self.modelo = modelo

        def invoke(self, mensagens):
            if self.modelo == "principal":
                raise RuntimeError("429 RateLimit")
            return AIMessage(content="resposta da reserva")

    monkeypatch.setattr(client, "modelos", lambda: ["principal", "reserva"])
    monkeypatch.setattr(client, "get_llm", lambda temperature=0.6, modelo=None: LLMFalso(modelo))
    assert client.responder("sistema", [], "oi") == "resposta da reserva"


def test_resposta_em_blocos_vira_texto():
    mensagem = AIMessage(content=[{"type": "text", "text": "Oi! "}, {"type": "text", "text": "Tudo bem?"}])
    assert mensagem.text == "Oi! Tudo bem?"
