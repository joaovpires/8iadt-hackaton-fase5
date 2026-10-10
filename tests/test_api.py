import pytest
from fastapi.testclient import TestClient

import api
from src.channels import whatsapp
from src.services import atendimento


@pytest.fixture
def cliente(llm, repo, monkeypatch):
    monkeypatch.setattr(atendimento, "get_repositorio", lambda: repo)
    monkeypatch.setattr(api, "get_repositorio", lambda: repo)
    return TestClient(api.app)


def test_health(cliente):
    assert cliente.get("/health").json()["status"] == "ok"


def test_mensagem_pela_api(cliente, llm):
    llm.roteirizar({"intencao": "aluguel", "regiao": "Mooca"})
    resposta = cliente.post("/mensagens", json={"lead_id": "site-1", "texto": "Quero alugar na Mooca"})
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["agente"] == "qualificador" and corpo["etapa"] == "em_qualificacao"
    assert cliente.get("/leads").json()[0]["id"] == "site-1"


def test_token_obrigatorio_quando_configurado(cliente, monkeypatch):
    monkeypatch.setattr(api, "API_TOKEN", "segredo")
    assert cliente.post("/mensagens", json={"lead_id": "site-2", "texto": "oi"}).status_code == 401


def test_webhook_whatsapp_responde_twiml(cliente, llm, repo):
    llm.roteirizar({"intencao": "compra"})
    resposta = cliente.post("/webhooks/whatsapp", data={"From": "whatsapp:+5511999999999", "Body": "Quero comprar um apê"})
    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("application/xml")
    assert "<Message>resposta-1</Message>" in resposta.text
    assert repo.obter_lead("whatsapp:+5511999999999")["canal"] == "whatsapp"


def test_webhook_rejeita_assinatura_invalida(cliente, monkeypatch):
    monkeypatch.setattr(whatsapp, "TWILIO_AUTH_TOKEN", "token-twilio")
    resposta = cliente.post("/webhooks/whatsapp", data={"From": "whatsapp:+5511", "Body": "oi"}, headers={"X-Twilio-Signature": "falsa"})
    assert resposta.status_code == 403


def test_assinatura_twilio_valida(monkeypatch):
    monkeypatch.setattr(whatsapp, "TWILIO_AUTH_TOKEN", "token-twilio")
    url, params = "https://exemplo.com/webhooks/whatsapp", {"Body": "oi", "From": "whatsapp:+5511"}
    assinatura = whatsapp.assinatura_esperada(url, params, "token-twilio")
    assert whatsapp.validar_assinatura(url, params, assinatura)
    assert not whatsapp.validar_assinatura(url, {**params, "Body": "alterado"}, assinatura)
