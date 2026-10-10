import os

os.environ["OPENAI_API_KEY"] = ""
os.environ["LLM_API_KEY"] = ""
os.environ["LLM_BASE_URL"] = ""
os.environ["LLM_MODEL"] = "modelo-teste"
os.environ["LLM_MODELOS_RESERVA"] = ""
os.environ["LLM_REASONING_EFFORT"] = ""
os.environ["LANGSMITH_TRACING"] = "false"

import pytest

from src.config import IMOVEIS_CSV
from src.graph.state import DadosLead, Extracao, SinaisMensagem
from src.llm import client
from src.memory.repositorio import Repositorio


class LLMFalso:
    def __init__(self):
        self.extracoes: list[tuple[dict, dict]] = []
        self.chamadas: list[dict] = []

    def roteirizar(self, dados: dict | None = None, sinais: dict | None = None):
        self.extracoes.append((dados or {}, sinais or {}))

    def extrair(self, sistema, conteudo, schema):
        dados, sinais = self.extracoes.pop(0) if self.extracoes else ({}, {})
        return Extracao(dados=DadosLead(**dados), sinais=SinaisMensagem(**sinais))

    def responder(self, sistema, historico, mensagem=None, instrucao_final=None):
        self.chamadas.append({"sistema": sistema, "historico": historico, "mensagem": mensagem, "instrucao_final": instrucao_final})
        return f"resposta-{len(self.chamadas)}"

    @property
    def chamadas_agentes(self) -> list[dict]:
        return [c for c in self.chamadas if not c["sistema"].startswith("Você prepara o resumo")]

    @property
    def resumos(self) -> list[dict]:
        return [c for c in self.chamadas if c["sistema"].startswith("Você prepara o resumo")]

    @property
    def ultimo_sistema(self) -> str:
        return self.chamadas_agentes[-1]["sistema"]


@pytest.fixture
def llm(monkeypatch):
    falso = LLMFalso()
    monkeypatch.setattr(client, "extrair", falso.extrair)
    monkeypatch.setattr(client, "responder", falso.responder)
    monkeypatch.setattr(client, "embed", lambda textos: (_ for _ in ()).throw(RuntimeError("sem rede nos testes")))
    return falso


@pytest.fixture
def repo(tmp_path):
    return Repositorio(tmp_path / "teste.db")


@pytest.fixture(autouse=True)
def base_imoveis_existe():
    assert IMOVEIS_CSV.exists(), "Rode scripts/gerar_imoveis.py antes dos testes"
