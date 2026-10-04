import logging
import os

from src.security.guardrails import mascarar_pii

_configurado = False


class FiltroPII(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mascarar_pii(record.getMessage())
        record.args = ()
        return True


def configurar_logs(nivel: str | None = None) -> None:
    global _configurado
    raiz = logging.getLogger("src")
    if _configurado or getattr(raiz, "_sdr_configurado", False):
        return
    manipulador = logging.StreamHandler()
    manipulador.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    manipulador.addFilter(FiltroPII())
    raiz.setLevel(nivel or os.getenv("LOG_LEVEL", "INFO"))
    raiz.addHandler(manipulador)
    raiz.propagate = False
    raiz._sdr_configurado = True
    _configurado = True


def tracing_ativo() -> bool:
    return os.getenv("LANGSMITH_TRACING", "").lower() == "true" and bool(os.getenv("LANGSMITH_API_KEY"))
