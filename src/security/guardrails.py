import re
import unicodedata

TAMANHO_MAXIMO = 1500

ALVOS_INTERNOS = r"(prompt|suas (instrucoes|regras)|instrucoes (do sistema|iniciais|originais|internas)|regras internas|configuracao interna)"

PADROES_INJECAO = [
    r"ignor\w* .{0,25}(instrucoes|regras|orientacoes|comandos) (anteriores|acima|iniciais|originais|do sistema)",
    r"ignor\w* (todas )?(as )?suas (instrucoes|regras|orientacoes)",
    r"ignore (all |the |any )?(previous|prior|above|your) (instructions|rules|prompts?)",
    r"esquec\w* (as |todas as )?(suas )?(instrucoes|regras)",
    rf"(revele|mostre|repita|imprima|copie|me (diga|passe|mostre|envie)) (o |a |as |os |seu |sua )?{ALVOS_INTERNOS}",
    r"system prompt|prompt do sistema|developer message",
    r"(voce|vc) agora (e|sera)\b",
    r"a partir de agora (voce|vc) (e|sera|vai ser|deve)\b",
    r"(modo|mode) (desenvolvedor|developer|dan|deus|god)",
    r"\bjailbreak\b",
    r"\bact as\b|\bpretend (you are|to be)\b|finja (que (e|voce e)|ser)\b",
    r"</?(system|assistant|instructions?)>",
]

PADROES_SENSIVEIS = [
    (re.compile(r"\b(?:\d[ -]?){13,16}\b"), "[cartão removido]"),
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[CPF removido]"),
]

PADROES_PII_LOG = [
    *PADROES_SENSIVEIS,
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[e-mail]"),
    (re.compile(r"(?:\+?55\s?)?\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}"), "[telefone]"),
]


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento.lower())


def detectar_injecao(texto: str) -> bool:
    alvo = _normalizar(texto or "")
    return any(re.search(p, alvo) for p in PADROES_INJECAO)


def remover_dados_sensiveis(texto: str) -> str:
    for padrao, substituto in PADROES_SENSIVEIS:
        texto = padrao.sub(substituto, texto)
    return texto


def sanitizar(texto: str) -> str:
    limpo = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", texto or "").strip()
    return remover_dados_sensiveis(limpo[:TAMANHO_MAXIMO])


def mascarar_pii(texto: str) -> str:
    for padrao, substituto in PADROES_PII_LOG:
        texto = padrao.sub(substituto, texto)
    return texto
