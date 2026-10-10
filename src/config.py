import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

RAIZ = Path(__file__).resolve().parent.parent

LLM_API_KEY = (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip() or None
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or None
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT") or None
LLM_MODELOS_RESERVA = [m.strip() for m in os.getenv("LLM_MODELOS_RESERVA", "").split(",") if m.strip()]
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
TRANSCRICAO_MODEL = os.getenv("TRANSCRICAO_MODEL", "whisper-1")
TTS_MODEL = os.getenv("TTS_MODEL", "gpt-4o-mini-tts")
TTS_VOZ = os.getenv("TTS_VOZ", "nova")

EMPRESA_NOME = os.getenv("EMPRESA_NOME", "Aurora Imóveis")
ASSISTENTE_NOME = os.getenv("ASSISTENTE_NOME", "Lia")

DB_PATH = Path(os.getenv("DB_PATH", RAIZ / "storage" / "sdr.db"))
CACHE_EMBEDDINGS = Path(os.getenv("CACHE_EMBEDDINGS", RAIZ / "storage" / "embeddings_imoveis.json"))
IMOVEIS_CSV = RAIZ / "src" / "data" / "imoveis.csv"
SOBRE_EMPRESA_MD = RAIZ / "src" / "data" / "imobiliaria.md"

HISTORICO_MAX_MENSAGENS = int(os.getenv("HISTORICO_MAX_MENSAGENS", "30"))
FOLLOWUP_INATIVIDADE_MIN = int(os.getenv("FOLLOWUP_INATIVIDADE_MIN", "1440"))
FOLLOWUP_MAX_TENTATIVAS = int(os.getenv("FOLLOWUP_MAX_TENTATIVAS", "3"))

API_TOKEN = os.getenv("API_TOKEN")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")

# CRM externo (diferencial): "mock" grava localmente em storage/ sem precisar de credenciais;
# "hubspot" sincroniza de verdade via API, bastando informar CRM_API_KEY
CRM_PROVIDER = os.getenv("CRM_PROVIDER", "mock")
CRM_API_KEY = os.getenv("CRM_API_KEY")
CRM_BASE_URL = os.getenv("CRM_BASE_URL", "https://api.hubapi.com")


def llm_configurado() -> bool:
    return bool(LLM_API_KEY)


def busca_semantica_disponivel() -> bool:
    return llm_configurado() and bool(EMBEDDING_MODEL)


def transcricao_disponivel() -> bool:
    return llm_configurado() and bool(TRANSCRICAO_MODEL)


def voz_disponivel() -> bool:
    return llm_configurado() and bool(TTS_MODEL)


def crm_configurado() -> bool:
    return CRM_PROVIDER == "mock" or bool(CRM_API_KEY)
