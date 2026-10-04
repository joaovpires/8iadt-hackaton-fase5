import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import lru_cache
from pathlib import Path

from src.config import DB_PATH

ESQUEMA = """
CREATE TABLE IF NOT EXISTS leads (
    id TEXT PRIMARY KEY,
    canal TEXT NOT NULL,
    nome TEXT,
    dados TEXT NOT NULL DEFAULT '{}',
    etapa TEXT NOT NULL DEFAULT 'novo',
    score INTEGER NOT NULL DEFAULT 0,
    temperatura TEXT NOT NULL DEFAULT 'frio',
    motivos_score TEXT NOT NULL DEFAULT '[]',
    resumo TEXT,
    imoveis_sugeridos TEXT NOT NULL DEFAULT '[]',
    horarios_ofertados TEXT NOT NULL DEFAULT '[]',
    tentativas_followup INTEGER NOT NULL DEFAULT 0,
    ultimo_autor TEXT,
    ultima_interacao_em TEXT,
    criado_em TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mensagens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id TEXT NOT NULL REFERENCES leads(id),
    papel TEXT NOT NULL,
    conteudo TEXT NOT NULL,
    agente TEXT,
    latencia_ms INTEGER,
    criado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reunioes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id TEXT NOT NULL REFERENCES leads(id),
    tipo TEXT NOT NULL,
    inicio TEXT NOT NULL,
    corretor TEXT NOT NULL,
    imovel_codigo TEXT,
    status TEXT NOT NULL DEFAULT 'agendada',
    criado_em TEXT NOT NULL,
    UNIQUE (inicio, corretor)
);
CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id TEXT,
    tipo TEXT NOT NULL,
    detalhe TEXT,
    criado_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mensagens_lead ON mensagens(lead_id, id);
CREATE INDEX IF NOT EXISTS idx_leads_followup ON leads(etapa, ultimo_autor, ultima_interacao_em);
"""

CAMPOS_JSON = ("dados", "motivos_score", "imoveis_sugeridos", "horarios_ofertados")
CAMPOS_ATUALIZAVEIS = {
    "canal", "nome", "dados", "etapa", "score", "temperatura", "motivos_score", "resumo",
    "imoveis_sugeridos", "horarios_ofertados", "tentativas_followup",
}
ETAPAS_FOLLOWUP = ("em_qualificacao", "qualificado")


def agora_iso(agora: datetime | None = None) -> str:
    return (agora or datetime.now()).isoformat(timespec="seconds")


class Repositorio:
    def __init__(self, caminho: Path | str = DB_PATH):
        self.caminho = Path(caminho)
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self._conexao() as con:
            con.executescript(ESQUEMA)

    @contextmanager
    def _conexao(self):
        con = sqlite3.connect(self.caminho, timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        try:
            yield con
            con.commit()
        finally:
            con.close()

    @staticmethod
    def _lead(linha: sqlite3.Row | None) -> dict | None:
        if linha is None:
            return None
        lead = dict(linha)
        for campo in CAMPOS_JSON:
            lead[campo] = json.loads(lead[campo] or ("{}" if campo == "dados" else "[]"))
        return lead

    def obter_lead(self, lead_id: str) -> dict | None:
        with self._conexao() as con:
            return self._lead(con.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone())

    def obter_ou_criar_lead(self, lead_id: str, canal: str) -> dict:
        lead = self.obter_lead(lead_id)
        if lead:
            return lead
        momento = agora_iso()
        with self._conexao() as con:
            con.execute(
                "INSERT OR IGNORE INTO leads (id, canal, criado_em, atualizado_em) VALUES (?, ?, ?, ?)",
                (lead_id, canal, momento, momento),
            )
        self.registrar_evento(lead_id, "lead_criado", canal)
        return self.obter_lead(lead_id)

    def atualizar_lead(self, lead_id: str, **campos) -> None:
        invalidos = set(campos) - CAMPOS_ATUALIZAVEIS
        if invalidos:
            raise ValueError(f"Campos não atualizáveis: {invalidos}")
        if "dados" in campos and campos["dados"].get("nome"):
            campos.setdefault("nome", campos["dados"]["nome"])
        valores = {k: json.dumps(v, ensure_ascii=False) if k in CAMPOS_JSON else v for k, v in campos.items()}
        valores["atualizado_em"] = agora_iso()
        atribuicoes = ", ".join(f"{k} = ?" for k in valores)
        with self._conexao() as con:
            con.execute(f"UPDATE leads SET {atribuicoes} WHERE id = ?", (*valores.values(), lead_id))

    def listar_leads(self) -> list[dict]:
        with self._conexao() as con:
            linhas = con.execute("SELECT * FROM leads ORDER BY COALESCE(ultima_interacao_em, criado_em) DESC").fetchall()
        return [self._lead(l) for l in linhas]

    def salvar_mensagem(self, lead_id: str, papel: str, conteudo: str, agente: str | None = None, latencia_ms: int | None = None, momento: datetime | None = None) -> None:
        criado_em = agora_iso(momento)
        with self._conexao() as con:
            con.execute(
                "INSERT INTO mensagens (lead_id, papel, conteudo, agente, latencia_ms, criado_em) VALUES (?, ?, ?, ?, ?, ?)",
                (lead_id, papel, conteudo, agente, latencia_ms, criado_em),
            )
            reset = ", tentativas_followup = 0" if papel == "user" else ""
            con.execute(
                f"UPDATE leads SET ultimo_autor = ?, ultima_interacao_em = ?, atualizado_em = ?{reset} WHERE id = ?",
                (papel, criado_em, criado_em, lead_id),
            )

    def historico(self, lead_id: str, limite: int | None = None) -> list[dict]:
        consulta = "SELECT papel, conteudo, agente, latencia_ms, criado_em FROM mensagens WHERE lead_id = ? ORDER BY id DESC"
        parametros: tuple = (lead_id,)
        if limite:
            consulta += " LIMIT ?"
            parametros += (limite,)
        with self._conexao() as con:
            linhas = con.execute(consulta, parametros).fetchall()
        return [dict(l) for l in reversed(linhas)]

    def contar_mensagens_lead(self, lead_id: str) -> int:
        with self._conexao() as con:
            return con.execute("SELECT COUNT(*) FROM mensagens WHERE lead_id = ? AND papel = 'user'", (lead_id,)).fetchone()[0]

    def horarios_ocupados(self) -> set[tuple[str, str]]:
        with self._conexao() as con:
            linhas = con.execute("SELECT inicio, corretor FROM reunioes WHERE status = 'agendada'").fetchall()
        return {(l["inicio"], l["corretor"]) for l in linhas}

    def salvar_reuniao(self, lead_id: str, tipo: str, inicio: str, corretor: str, imovel_codigo: str | None) -> dict | None:
        try:
            with self._conexao() as con:
                cursor = con.execute(
                    "INSERT INTO reunioes (lead_id, tipo, inicio, corretor, imovel_codigo, criado_em) VALUES (?, ?, ?, ?, ?, ?)",
                    (lead_id, tipo, inicio, corretor, imovel_codigo, agora_iso()),
                )
                reuniao_id = cursor.lastrowid
        except sqlite3.IntegrityError:
            return None
        self.registrar_evento(lead_id, "reuniao_agendada", f"{tipo} {inicio} {corretor}")
        return self.obter_reuniao(reuniao_id)

    def obter_reuniao(self, reuniao_id: int) -> dict | None:
        with self._conexao() as con:
            linha = con.execute("SELECT * FROM reunioes WHERE id = ?", (reuniao_id,)).fetchone()
        return dict(linha) if linha else None

    def reuniao_do_lead(self, lead_id: str) -> dict | None:
        with self._conexao() as con:
            linha = con.execute(
                "SELECT * FROM reunioes WHERE lead_id = ? AND status = 'agendada' ORDER BY inicio DESC LIMIT 1", (lead_id,)
            ).fetchone()
        return dict(linha) if linha else None

    def listar_reunioes(self) -> list[dict]:
        with self._conexao() as con:
            linhas = con.execute(
                "SELECT r.*, l.nome AS lead_nome, l.canal FROM reunioes r JOIN leads l ON l.id = r.lead_id ORDER BY r.inicio"
            ).fetchall()
        return [dict(l) for l in linhas]

    def leads_para_followup(self, inatividade_min: int, max_tentativas: int, agora: datetime | None = None) -> list[dict]:
        limite = agora_iso((agora or datetime.now()) - timedelta(minutes=inatividade_min))
        marcadores = ", ".join("?" for _ in ETAPAS_FOLLOWUP)
        with self._conexao() as con:
            linhas = con.execute(
                f"""SELECT * FROM leads WHERE etapa IN ({marcadores}) AND ultimo_autor = 'assistant'
                    AND ultima_interacao_em <= ? AND tentativas_followup < ? ORDER BY ultima_interacao_em""",
                (*ETAPAS_FOLLOWUP, limite, max_tentativas),
            ).fetchall()
        return [self._lead(l) for l in linhas]

    def leads_esgotados(self, inatividade_min: int, max_tentativas: int, agora: datetime | None = None) -> list[dict]:
        limite = agora_iso((agora or datetime.now()) - timedelta(minutes=inatividade_min))
        marcadores = ", ".join("?" for _ in ETAPAS_FOLLOWUP)
        with self._conexao() as con:
            linhas = con.execute(
                f"""SELECT * FROM leads WHERE etapa IN ({marcadores}) AND ultimo_autor = 'assistant'
                    AND ultima_interacao_em <= ? AND tentativas_followup >= ?""",
                (*ETAPAS_FOLLOWUP, limite, max_tentativas),
            ).fetchall()
        return [self._lead(l) for l in linhas]

    def simular_inatividade(self, lead_id: str, minutos: int) -> None:
        lead = self.obter_lead(lead_id)
        if not lead or not lead["ultima_interacao_em"]:
            return
        recuado = datetime.fromisoformat(lead["ultima_interacao_em"]) - timedelta(minutes=minutos)
        with self._conexao() as con:
            con.execute("UPDATE leads SET ultima_interacao_em = ? WHERE id = ?", (agora_iso(recuado), lead_id))
        self.registrar_evento(lead_id, "inatividade_simulada", f"{minutos} min")

    def registrar_evento(self, lead_id: str | None, tipo: str, detalhe: str | None = None) -> None:
        with self._conexao() as con:
            con.execute(
                "INSERT INTO eventos (lead_id, tipo, detalhe, criado_em) VALUES (?, ?, ?, ?)",
                (lead_id, tipo, detalhe, agora_iso()),
            )

    def listar_eventos(self, limite: int = 200) -> list[dict]:
        with self._conexao() as con:
            linhas = con.execute("SELECT * FROM eventos ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
        return [dict(l) for l in linhas]

    def metricas_mensagens(self) -> list[dict]:
        with self._conexao() as con:
            linhas = con.execute(
                """SELECT agente, COUNT(*) AS respostas, AVG(latencia_ms) AS latencia_media_ms
                   FROM mensagens WHERE papel = 'assistant' AND agente IS NOT NULL GROUP BY agente ORDER BY respostas DESC"""
            ).fetchall()
        return [dict(l) for l in linhas]

    def contar_eventos(self) -> dict[str, int]:
        with self._conexao() as con:
            linhas = con.execute("SELECT tipo, COUNT(*) AS total FROM eventos GROUP BY tipo").fetchall()
        return {l["tipo"]: l["total"] for l in linhas}


@lru_cache
def get_repositorio() -> Repositorio:
    return Repositorio()
