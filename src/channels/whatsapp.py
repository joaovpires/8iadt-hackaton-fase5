import base64
import hashlib
import hmac
import logging
from xml.sax.saxutils import escape

import httpx

from src.config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM

logger = logging.getLogger(__name__)

URL_API = "https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"


def configurado() -> bool:
    return bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_WHATSAPP_FROM)


def assinatura_esperada(url: str, parametros: dict, token: str) -> str:
    dados = url + "".join(f"{chave}{parametros[chave]}" for chave in sorted(parametros))
    digest = hmac.new(token.encode(), dados.encode(), hashlib.sha1).digest()
    return base64.b64encode(digest).decode()


def validar_assinatura(url: str, parametros: dict, assinatura: str | None) -> bool:
    if not TWILIO_AUTH_TOKEN:
        logger.warning("TWILIO_AUTH_TOKEN ausente: assinatura do webhook não validada (aceitável só em desenvolvimento)")
        return True
    return hmac.compare_digest(assinatura_esperada(url, parametros, TWILIO_AUTH_TOKEN), assinatura or "")


def twiml(texto: str) -> str:
    return f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{escape(texto)}</Message></Response>'


def enviar(destino: str, texto: str) -> bool:
    if not configurado():
        logger.info("WhatsApp não configurado; mensagem para %s não enviada", destino)
        return False
    resposta = httpx.post(
        URL_API.format(sid=TWILIO_ACCOUNT_SID),
        data={"From": TWILIO_WHATSAPP_FROM, "To": destino, "Body": texto},
        auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
        timeout=15,
    )
    resposta.raise_for_status()
    return True


def baixar_midia(url: str) -> bytes:
    resposta = httpx.get(url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), follow_redirects=True, timeout=30)
    resposta.raise_for_status()
    return resposta.content
