import logging

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel, Field

from src.channels import whatsapp
from src.config import API_TOKEN, PUBLIC_BASE_URL, llm_configurado, transcricao_disponivel
from src.llm import client
from src.memory.repositorio import get_repositorio
from src.observabilidade import configurar_logs
from src.services.atendimento import processar_mensagem, sincronizar_crm_lead
from src.services.followup import executar_followups

configurar_logs()
logger = logging.getLogger("src.api")

app = FastAPI(
    title="Agente SDR Imobiliário",
    version="1.0.0",
    description="API do agente SDR: canal genérico de mensagens, webhook do WhatsApp (Twilio) e rotina de follow-up.",
)


class MensagemEntrada(BaseModel):
    lead_id: str = Field(..., min_length=3, max_length=100, examples=["site-123"])
    texto: str = Field(..., min_length=1, max_length=2000, examples=["Quero alugar um apartamento em Pinheiros"])
    canal: str = Field("api", max_length=30)


class MensagemSaida(BaseModel):
    lead_id: str
    resposta: str
    agente: str
    etapa: str
    score: int
    temperatura: str
    latencia_ms: int


def exigir_token(authorization: str | None = Header(None)) -> None:
    if API_TOKEN and authorization != f"Bearer {API_TOKEN}":
        raise HTTPException(status_code=401, detail="Token inválido")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "llm_configurado": llm_configurado(), "whatsapp_configurado": whatsapp.configurado()}


@app.post("/mensagens", response_model=MensagemSaida, dependencies=[Depends(exigir_token)])
def receber_mensagem(entrada: MensagemEntrada) -> MensagemSaida:
    resultado = processar_mensagem(entrada.lead_id, entrada.texto, canal=entrada.canal)
    return MensagemSaida(**{k: getattr(resultado, k) for k in MensagemSaida.model_fields})


@app.get("/leads", dependencies=[Depends(exigir_token)])
def listar_leads() -> list[dict]:
    return [
        {k: lead[k] for k in ("id", "canal", "nome", "etapa", "score", "temperatura", "dados", "resumo", "ultima_interacao_em")}
        for lead in get_repositorio().listar_leads()
    ]


@app.post("/followups/executar", dependencies=[Depends(exigir_token)])
def rodar_followups() -> dict:
    return executar_followups()


@app.post("/crm/{lead_id}/sincronizar", dependencies=[Depends(exigir_token)])
def sincronizar_crm(lead_id: str) -> dict:
    return {"lead_id": lead_id, "sincronizado": sincronizar_crm_lead(lead_id)}


@app.post("/webhooks/whatsapp")
async def webhook_whatsapp(request: Request) -> Response:
    formulario = dict(await request.form())
    url = f"{PUBLIC_BASE_URL.rstrip('/')}{request.url.path}" if PUBLIC_BASE_URL else str(request.url)
    if not whatsapp.validar_assinatura(url, formulario, request.headers.get("X-Twilio-Signature")):
        raise HTTPException(status_code=403, detail="Assinatura inválida")

    remetente = formulario.get("From", "")
    texto = (formulario.get("Body") or "").strip()
    eh_audio = int(formulario.get("NumMedia") or 0) and str(formulario.get("MediaContentType0", "")).startswith("audio")
    if eh_audio and transcricao_disponivel():
        try:
            audio = await run_in_threadpool(whatsapp.baixar_midia, formulario["MediaUrl0"])
            texto = await run_in_threadpool(client.transcrever, audio, "audio.ogg")
        except Exception:
            logger.exception("Falha ao transcrever áudio do WhatsApp")

    if not remetente or not texto:
        return Response(whatsapp.twiml("Recebi sua mensagem, mas não consegui entender. Pode me escrever?"), media_type="application/xml")

    resultado = await run_in_threadpool(processar_mensagem, remetente, texto, "whatsapp")
    return Response(whatsapp.twiml(resultado.resposta), media_type="application/xml")
