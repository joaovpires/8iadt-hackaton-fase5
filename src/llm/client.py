import logging
from functools import lru_cache
from io import BytesIO

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from openai import OpenAI

from src.config import (
    EMBEDDING_MODEL,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_MODELOS_RESERVA,
    LLM_REASONING_EFFORT,
    TRANSCRICAO_MODEL,
    TTS_MODEL,
    TTS_VOZ,
)

logger = logging.getLogger(__name__)

METODOS_ESTRUTURADOS = ("function_calling", "json_schema")
SINAIS_SOBRECARGA = ("RateLimit", "429", "500", "502", "503", "504", "Timeout", "timed out", "Connection", "high demand", "overloaded", "UNAVAILABLE")
_metodo_que_funcionou: dict[str, str] = {}


def modelos() -> list[str]:
    return [LLM_MODEL, *[m for m in LLM_MODELOS_RESERVA if m != LLM_MODEL]]


@lru_cache
def get_llm(temperature: float = 0.6, modelo: str | None = None) -> ChatOpenAI:
    extras = {"reasoning_effort": LLM_REASONING_EFFORT} if LLM_REASONING_EFFORT else {}
    tem_reserva = len(modelos()) > 1
    return ChatOpenAI(
        model=modelo or LLM_MODEL,
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
        temperature=temperature,
        timeout=20 if tem_reserva else 60,
        max_retries=0 if tem_reserva else 2,
        **extras,
    )


@lru_cache
def _extrator(schema, metodo: str, modelo: str):
    return get_llm(temperature=0, modelo=modelo).with_structured_output(schema, method=metodo)


def sobrecarga(erro: Exception) -> bool:
    texto = f"{type(erro).__name__} {erro}"[:500]
    return any(sinal in texto for sinal in SINAIS_SOBRECARGA)


@lru_cache
def _openai() -> OpenAI:
    return OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)


def limite_atingido(erro: Exception) -> bool:
    return sobrecarga(erro)


def para_mensagens(historico: list[dict]) -> list:
    mensagens = []
    for m in historico:
        if m["papel"] == "user":
            mensagens.append(HumanMessage(m["conteudo"]))
        elif m["papel"] == "assistant":
            mensagens.append(AIMessage(m["conteudo"]))
    return mensagens


def responder(sistema: str, historico: list[dict], mensagem: str | None = None, instrucao_final: str | None = None) -> str:
    mensagens = [SystemMessage(sistema), *para_mensagens(historico)]
    if mensagem:
        mensagens.append(HumanMessage(mensagem))
    if instrucao_final:
        mensagens.append(HumanMessage(f"[Instrução interna do sistema, não é o cliente falando] {instrucao_final}"))
    ultimo_erro: Exception | None = None
    for modelo in modelos():
        try:
            return get_llm(modelo=modelo).invoke(mensagens).text.strip()
        except Exception as erro:
            ultimo_erro = erro
            logger.warning("Modelo %s falhou ao responder (%s); tentando o próximo", modelo, type(erro).__name__)
    raise ultimo_erro


def extrair(sistema: str, conteudo: str, schema):
    mensagens = [SystemMessage(sistema), HumanMessage(conteudo)]
    ultimo_erro: Exception | None = None
    for modelo in modelos():
        preferido = _metodo_que_funcionou.get(schema.__name__)
        for metodo in sorted(METODOS_ESTRUTURADOS, key=lambda m: m != preferido):
            try:
                resultado = _extrator(schema, metodo, modelo).invoke(mensagens)
                if resultado is None:
                    raise ValueError("o modelo não retornou a estrutura")
                _metodo_que_funcionou[schema.__name__] = metodo
                return resultado
            except Exception as erro:
                ultimo_erro = erro
                logger.warning("Extração com %s via %s falhou (%s)", modelo, metodo, type(erro).__name__)
                if sobrecarga(erro):
                    break
    raise ultimo_erro


def embed(textos: list[str]) -> list[list[float]]:
    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
        check_embedding_ctx_length=LLM_BASE_URL is None,
    ).embed_documents(textos)


def transcrever(audio: bytes, nome_arquivo: str = "audio.wav") -> str:
    arquivo = BytesIO(audio)
    arquivo.name = nome_arquivo
    resultado = _openai().audio.transcriptions.create(model=TRANSCRICAO_MODEL, file=arquivo, language="pt")
    return resultado.text.strip()


def sintetizar(texto: str) -> bytes:
    resposta = _openai().audio.speech.create(model=TTS_MODEL, voice=TTS_VOZ, input=texto, response_format="mp3")
    return resposta.content
