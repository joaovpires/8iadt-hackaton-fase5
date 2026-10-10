import json

import httpx
import pytest

from src.services.atendimento import processar_mensagem
from src.tools import crm


@pytest.fixture(autouse=True)
def crm_mock_path(tmp_path, monkeypatch):
    caminho = tmp_path / "crm_mock.json"
    monkeypatch.setattr(crm, "CRM_MOCK_PATH", caminho)
    return caminho


def _lead(etapa="qualificado", score=80):
    return {
        "id": "web-teste",
        "canal": "web",
        "nome": None,
        "dados": {"intencao": "compra", "regiao": "Moema", "nome": "Ana"},
        "etapa": etapa,
        "score": score,
    }


def test_sincronizar_mock_nao_precisa_de_credenciais(monkeypatch, crm_mock_path):
    monkeypatch.setattr(crm, "CRM_PROVIDER", "mock")
    assert crm.sincronizar(_lead()) is True
    registros = json.loads(crm_mock_path.read_text(encoding="utf-8"))
    assert registros["web-teste"]["nome"] == "Ana"
    assert registros["web-teste"]["etapa"] == "qualificado"


def test_sincronizar_mock_atualiza_lead_existente(monkeypatch, crm_mock_path):
    monkeypatch.setattr(crm, "CRM_PROVIDER", "mock")
    crm.sincronizar(_lead(etapa="qualificado"))
    crm.sincronizar(_lead(etapa="agendado", score=95))
    registros = json.loads(crm_mock_path.read_text(encoding="utf-8"))
    assert len(registros) == 1
    assert registros["web-teste"]["etapa"] == "agendado"
    assert registros["web-teste"]["score"] == 95


def test_sincronizar_hubspot_chama_api_com_token(monkeypatch):
    monkeypatch.setattr(crm, "CRM_PROVIDER", "hubspot")
    monkeypatch.setattr(crm, "CRM_API_KEY", "chave-teste")
    chamadas = []

    def post_falso(url, headers=None, json=None, timeout=None):
        chamadas.append({"url": url, "headers": headers, "json": json})
        return httpx.Response(200, json={"id": "123"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post_falso)
    assert crm.sincronizar(_lead()) is True
    assert chamadas[0]["headers"]["Authorization"] == "Bearer chave-teste"
    assert chamadas[0]["json"]["properties"]["intencao_imovel"] == "compra"


def test_sincronizar_falha_nao_lanca_excecao(monkeypatch):
    monkeypatch.setattr(crm, "CRM_PROVIDER", "hubspot")
    monkeypatch.setattr(crm, "CRM_API_KEY", "chave-teste")

    def post_com_erro(*args, **kwargs):
        raise httpx.ConnectError("sem rede")

    monkeypatch.setattr(httpx, "post", post_com_erro)
    assert crm.sincronizar(_lead()) is False


def test_configurado_mock_sempre_true_hubspot_exige_chave(monkeypatch):
    monkeypatch.setattr(crm, "CRM_PROVIDER", "mock")
    assert crm.configurado() is True
    monkeypatch.setattr(crm, "CRM_PROVIDER", "hubspot")
    monkeypatch.setattr(crm, "CRM_API_KEY", None)
    assert crm.configurado() is False


def test_lead_qualificado_sincroniza_com_crm_automaticamente(llm, repo, monkeypatch):
    sincronizados = []
    monkeypatch.setattr(crm, "sincronizar", lambda lead: sincronizados.append(lead["id"]) or True)

    lead_id = "web-crm"
    llm.roteirizar({"intencao": "compra", "regiao": "zona sul", "preco_max": 950000, "quartos": 2, "urgencia": "alta", "nome": "Ana"})
    r = processar_mensagem(lead_id, "Apartamento na zona sul, até 950 mil, 2 quartos, urgente. Sou a Ana", repo=repo)

    assert r.etapa == "qualificado"
    assert sincronizados == [lead_id]
    assert repo.obter_lead(lead_id)["crm_sincronizado"] == 1
    assert repo.contar_eventos().get("crm_sincronizado") == 1
