import argparse
import logging
import time
from datetime import datetime
from time import perf_counter

from src.channels import whatsapp
from src.config import FOLLOWUP_INATIVIDADE_MIN, FOLLOWUP_MAX_TENTATIVAS
from src.graph.sdr_graph import sdr_app
from src.memory.repositorio import Repositorio, get_repositorio
from src.services.atendimento import config_execucao, estado_do_lead

logger = logging.getLogger(__name__)


def enviar_followup(repo: Repositorio, lead: dict, agora: datetime | None = None) -> dict:
    agora = agora or datetime.now()
    tentativa = lead["tentativas_followup"] + 1
    minutos = int((agora - datetime.fromisoformat(lead["ultima_interacao_em"])).total_seconds() // 60)
    estado = {**estado_do_lead(repo, lead), "evento": "followup", "tentativas_followup": tentativa, "minutos_inativo": minutos}

    inicio = perf_counter()
    resultado = sdr_app.invoke(estado, config=config_execucao(repo, lead["id"], lead["canal"], "followup"))
    latencia_ms = round((perf_counter() - inicio) * 1000)

    mensagem = resultado["resposta_final"]
    repo.salvar_mensagem(lead["id"], "assistant", mensagem, agente="followup", latencia_ms=latencia_ms)
    repo.atualizar_lead(lead["id"], tentativas_followup=tentativa)
    repo.registrar_evento(lead["id"], "followup_enviado", f"tentativa {tentativa}")

    entregue = True
    if lead["canal"] == "whatsapp":
        try:
            entregue = whatsapp.enviar(lead["id"], mensagem)
        except Exception:
            logger.exception("Falha ao enviar follow-up por WhatsApp lead=%s", lead["id"])
            entregue = False
    return {"lead_id": lead["id"], "tentativa": tentativa, "mensagem": mensagem, "entregue": entregue}


def executar_followups(repo: Repositorio | None = None, agora: datetime | None = None) -> dict:
    repo = repo or get_repositorio()
    enviados = []
    for lead in repo.leads_para_followup(FOLLOWUP_INATIVIDADE_MIN, FOLLOWUP_MAX_TENTATIVAS, agora):
        try:
            enviados.append(enviar_followup(repo, lead, agora))
        except Exception:
            logger.exception("Falha ao gerar follow-up lead=%s", lead["id"])

    perdidos = []
    for lead in repo.leads_esgotados(FOLLOWUP_INATIVIDADE_MIN, FOLLOWUP_MAX_TENTATIVAS, agora):
        repo.atualizar_lead(
            lead["id"], etapa="perdido", score=0, temperatura="frio",
            motivos_score=[f"Sem resposta após {FOLLOWUP_MAX_TENTATIVAS} follow-ups"],
        )
        repo.registrar_evento(lead["id"], "lead_perdido", "sem resposta após follow-ups")
        perdidos.append(lead["id"])

    logger.info("follow-ups enviados=%s leads marcados como perdidos=%s", len(enviados), len(perdidos))
    return {"enviados": enviados, "perdidos": perdidos}


def main() -> None:
    from src.observabilidade import configurar_logs

    configurar_logs()
    parser = argparse.ArgumentParser(description="Executa o follow-up automático de leads inativos")
    parser.add_argument("--loop", type=int, default=0, help="Intervalo em segundos para rodar continuamente (0 = executa uma vez)")
    args = parser.parse_args()
    while True:
        executar_followups()
        if not args.loop:
            break
        time.sleep(args.loop)


if __name__ == "__main__":
    main()
