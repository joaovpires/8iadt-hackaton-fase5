import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import DB_PATH
from src.memory.repositorio import Repositorio
from src.services.score import calcular_score
from src.tools import agenda, imoveis

LEADS = [
    {
        "id": "web-demo-ana",
        "canal": "web",
        "etapa": "agendado",
        "horas_atras": 3,
        "dados": {"intencao": "compra", "nome": "Ana", "tipo_imovel": "apartamento", "regiao": "zona sul", "preco_max": 950000, "quartos": 2, "urgencia": "alta", "forma_pagamento": "financiamento", "preferencias": "varanda, perto do metrô"},
        "conversa": [
            ("user", "Estou procurando apartamento na zona sul."),
            ("assistant", "Que legal! A zona sul tem ótimas opções. Você pensa em comprar ou alugar?"),
            ("user", "Comprar, com financiamento. Até uns 950 mil."),
            ("assistant", "Perfeito, dá pra achar coisa boa nessa faixa. Quantos quartos você precisa?"),
            ("user", "2 quartos, de preferência com varanda e perto do metrô. Preciso me mudar mês que vem, sou a Ana."),
            ("assistant", "Prazer, Ana! Separei 3 opções que combinam com você. Quer visitar? Tenho 1) terça às 10h, 2) quarta às 14h, 3) quinta às 16h."),
            ("user", "A segunda opção!"),
            ("assistant", "Fechado, Ana! Visita marcada para quarta às 14h com a Carla Mendes. Ela vai te chamar para confirmar 😊"),
        ],
        "agentes": {5: "agendamento", 7: "agendamento"},
        "resumo": "**Perfil** Ana, compradora com financiamento.\n\n**O que procura** Apartamento de 2 quartos na zona sul, até R$ 950 mil, com varanda e perto do metrô.\n\n**Imóveis de interesse** Opções em Moema, Brooklin e Campo Belo.\n\n**Temperatura** Quente: urgência alta (mudança no próximo mês) e visita agendada.\n\n**Próximos passos** Confirmar a visita, levar simulação de financiamento e preparar 1 opção extra com vaga dupla.",
        "agendar": True,
    },
    {
        "id": "web-demo-marcos",
        "canal": "web",
        "etapa": "qualificado",
        "horas_atras": 30,
        "dados": {"intencao": "investimento", "nome": "Marcos", "perfil_investidor": "residencial, já tem 1 imóvel alugado", "ticket": 600000, "retorno_esperado": "renda mensal de aluguel", "urgencia": "media"},
        "conversa": [
            ("user", "Quero investir em imóveis para renda."),
            ("assistant", "Ótimo objetivo! Você prefere imóvel residencial ou comercial? Já investe em imóveis?"),
            ("user", "Residencial, já tenho um apê alugado. Tenho uns 600 mil."),
            ("assistant", "Boa, com 600 mil dá pra montar uma carteira interessante. Seu foco é renda mensal ou valorização?"),
            ("user", "Renda mensal."),
            ("assistant", "Separei 3 oportunidades com boa rentabilidade estimada. Quer conversar com a Beatriz, nossa especialista? Tenho 1) segunda às 10h, 2) terça às 14h, 3) quarta às 16h."),
        ],
        "resumo": None,
        "agentes": {1: "investimento", 3: "investimento", 5: "agendamento"},
        "ofertar": True,
    },
    {
        "id": "web-demo-juliana",
        "canal": "web",
        "etapa": "em_qualificacao",
        "horas_atras": 49,
        "dados": {"intencao": "aluguel", "nome": "Juliana", "regiao": "Pinheiros", "preco_max": 5000},
        "conversa": [
            ("user", "Oi, quero alugar em Pinheiros"),
            ("assistant", "Oi! Pinheiros é uma delícia de bairro. Quanto cabe no seu orçamento por mês?"),
            ("user", "Até 5 mil. Sou a Juliana"),
            ("assistant", "Prazer, Juliana! E quantos quartos você precisa?"),
        ],
    },
    {
        "id": "web-demo-pedro",
        "canal": "web",
        "etapa": "em_qualificacao",
        "horas_atras": 26,
        "followups": 1,
        "dados": {"intencao": "compra", "nome": "Pedro", "regiao": "Tatuapé", "quartos": 3},
        "conversa": [
            ("user", "Procuro casa ou apê de 3 quartos no Tatuapé pra comprar"),
            ("assistant", "Tatuapé tem ótimas opções para família! Até quanto você pensa em investir?"),
            ("assistant", "Oi, Pedro! Vi aqui um apê de 3 quartos no Tatuapé perto do metrô que lembrou de você. Quer que eu te mande os detalhes?"),
        ],
        "agentes": {2: "followup"},
    },
    {
        "id": "web-demo-renata",
        "canal": "web",
        "etapa": "agendado",
        "horas_atras": 6,
        "dados": {"intencao": "aluguel", "nome": "Renata", "tipo_imovel": "studio", "regiao": "perto da Paulista", "preco_max": 3000, "quartos": 1, "urgencia": "alta"},
        "conversa": [
            ("user", "Preciso alugar um studio perto da Paulista, pra já."),
            ("assistant", "Entendi, vamos agilizar! Até quanto você pode pagar de aluguel por mês?"),
            ("user", "Até 3 mil. Renata."),
            ("assistant", "Renata, separei 3 studios na região. Quer visitar? 1) amanhã às 10h, 2) sexta às 14h, 3) sábado às 11h."),
            ("user", "Amanhã às 10h"),
            ("assistant", "Combinado! Visita amanhã às 10h com o Rafael Souza. Ele vai te chamar para confirmar."),
        ],
        "agentes": {3: "agendamento", 5: "agendamento"},
        "resumo": "**Perfil** Renata, locatária com urgência.\n\n**O que procura** Studio perto da Av. Paulista até R$ 3.000/mês.\n\n**Imóveis de interesse** Studios na Bela Vista e Consolação.\n\n**Temperatura** Quente: precisa se mudar imediatamente.\n\n**Próximos passos** Confirmar visita, já enviar a lista de garantias aceitas (seguro-fiança, caução).",
        "agendar": True,
    },
    {
        "id": "web-demo-lucas",
        "canal": "web",
        "etapa": "perdido",
        "horas_atras": 72,
        "dados": {"intencao": "compra", "nome": "Lucas", "regiao": "Santana"},
        "conversa": [
            ("user", "Quero comprar em Santana"),
            ("assistant", "Santana é ótima! Até quanto você pensa em investir?"),
            ("user", "Na verdade desisti por enquanto, obrigado"),
            ("assistant", "Imagina, Lucas! Se mudar de ideia é só me chamar por aqui."),
        ],
        "agentes": {3: "encerramento"},
    },
    {
        "id": "whatsapp:+5511900000001",
        "canal": "whatsapp",
        "etapa": "em_qualificacao",
        "horas_atras": 1,
        "dados": {"intencao": "investimento", "perfil_investidor": "comercial", "ticket": 1500000},
        "conversa": [
            ("user", "Boa tarde, quero investir em sala comercial, tenho 1,5 milhão"),
            ("assistant", "Boa tarde! Ticket muito interessante para salas comerciais. Você busca renda mensal com aluguel ou valorização?"),
        ],
        "agentes": {1: "investimento"},
    },
]


def popular(repo: Repositorio) -> None:
    agora = datetime.now()
    ocupados = repo.horarios_ocupados()
    for item in LEADS:
        repo.obter_ou_criar_lead(item["id"], item["canal"])
        inicio = agora - timedelta(hours=item["horas_atras"])
        for indice, (papel, texto) in enumerate(item["conversa"]):
            momento = inicio + timedelta(minutes=2 * indice)
            agente = item.get("agentes", {}).get(indice) or ("qualificador" if papel == "assistant" else None)
            repo.salvar_mensagem(item["id"], papel, texto, agente=agente, latencia_ms=1800 + 150 * indice if papel == "assistant" else None, momento=momento)

        sugeridos = imoveis.buscar(item["dados"]) if item["etapa"] in ("qualificado", "agendado") else []
        especialidade = agenda.especialidade_para(item["dados"].get("intencao"))
        horarios = agenda.horarios_disponiveis(ocupados, especialidade) if item.get("ofertar") or item.get("agendar") else []
        if item.get("agendar") and horarios:
            escolhido = horarios[1]
            tipo = "reunião" if item["dados"]["intencao"] == "investimento" else "visita"
            codigo = sugeridos[0]["codigo"] if sugeridos else None
            repo.salvar_reuniao(item["id"], tipo, escolhido["inicio"], escolhido["corretor"], codigo)
            ocupados.add((escolhido["inicio"], escolhido["corretor"]))
            horarios = []

        mensagens_lead = sum(1 for papel, _ in item["conversa"] if papel == "user")
        score = calcular_score(item["dados"], item["etapa"], mensagens_lead)
        repo.atualizar_lead(
            item["id"],
            dados=item["dados"],
            etapa=item["etapa"],
            score=score.valor,
            temperatura=score.temperatura,
            motivos_score=score.motivos,
            resumo=item.get("resumo"),
            imoveis_sugeridos=sugeridos,
            horarios_ofertados=horarios,
            tentativas_followup=item.get("followups", 0),
        )
        print(f"{item['id']}: {item['etapa']} · score {score.valor} ({score.temperatura})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Popula o banco com leads de demonstração")
    parser.add_argument("--limpar", action="store_true", help="Apaga o banco atual antes de popular")
    args = parser.parse_args()
    if args.limpar:
        for sufixo in ("", "-wal", "-shm"):
            Path(f"{DB_PATH}{sufixo}").unlink(missing_ok=True)
    popular(Repositorio(DB_PATH))
    print(f"Banco de demonstração pronto em {DB_PATH}")


if __name__ == "__main__":
    main()
