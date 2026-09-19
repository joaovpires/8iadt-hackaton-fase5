from langchain_openai import ChatOpenAI
from src.config import OPENAI_API_KEY, LLM_MODEL

def get_llm(temperature: float = 0.4):
    return ChatOpenAI(
        model=LLM_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=temperature, #criativo/aleatório
    )