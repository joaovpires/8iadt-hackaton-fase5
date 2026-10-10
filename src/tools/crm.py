"""Sincronização ativa do lead com um CRM externo (diferencial do desafio).

Hoje a API REST já expõe `GET /leads` para um CRM externo *puxar* os dados
(ver `docs/arquitetura.md`). Este módulo complementa isso com um *push*
ativo: quando o lead é qualificado ou agendado, o resultado é enviado para
o CRM configurado.

Por padrão (`CRM_PROVIDER=mock`) os leads são gravados em
`storage/crm_mock.json`, sem precisar de credenciais — assim a demo
funciona offline. Com `CRM_PROVIDER=hubspot` e `CRM_API_KEY`, sincroniza de
verdade com a API de Contatos do HubSpot.
"""
import json
import logging

import httpx

from src.config import CRM_API_KEY, CRM_BASE_URL, CRM_PROVIDER, RAIZ

logger = logging.getLogger(__name__)

CRM_MOCK_PATH = RAIZ / "storage" / "crm_mock.json"


def configurado() -> bool:
    return CRM_PROVIDER == "mock" or bool(CRM_API_KEY)


def _ler_mock() -> dict:
    if CRM_MOCK_PATH.exists():
        return json.loads(CRM_MOCK_PATH.read_text(encoding="utf-8") or "{}")
    return {}


def _upsert_mock(lead: dict) -> bool:
    CRM_MOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    registros = _ler_mock()
    registros[lead["id"]] = {
        "nome": lead.get("nome") or (lead.get("dados") or {}).get("nome"),
        "canal": lead.get("canal"),
        "intencao": (lead.get("dados") or {}).get("intencao"),
        "regiao": (lead.get("dados") or {}).get("regiao"),
        "etapa": lead.get("etapa"),
        "score": lead.get("score"),
    }
    CRM_MOCK_PATH.write_text(json.dumps(registros, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def _upsert_hubspot(lead: dict) -> bool:
    dados = lead.get("dados") or {}
    resposta = httpx.post(
        f"{CRM_BASE_URL}/crm/v3/objects/contacts",
        headers={"Authorization": f"Bearer {CRM_API_KEY}"},
        json={
            "properties": {
                "firstname": lead.get("nome") or dados.get("nome") or lead["id"],
                "hs_lead_status": lead.get("etapa"),
                "intencao_imovel": dados.get("intencao"),
                "regiao_interesse": dados.get("regiao"),
            }
        },
        timeout=15,
    )
    resposta.raise_for_status()
    return True


def sincronizar(lead: dict) -> bool:
    """Envia o lead para o CRM configurado. Nunca lança exceção (loga e retorna False)."""
    try:
        if CRM_PROVIDER == "hubspot":
            return _upsert_hubspot(lead)
        return _upsert_mock(lead)
    except Exception:
        logger.exception("Falha ao sincronizar lead=%s com o CRM (%s)", lead.get("id"), CRM_PROVIDER)
        return False
