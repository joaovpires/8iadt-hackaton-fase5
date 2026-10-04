from datetime import datetime, time, timedelta

CORRETORES = [
    {"nome": "Carla Mendes", "especialidade": "residencial"},
    {"nome": "Rafael Souza", "especialidade": "residencial"},
    {"nome": "Beatriz Lima", "especialidade": "investimento"},
]

EXPEDIENTE = {0: (9, 18), 1: (9, 18), 2: (9, 18), 3: (9, 18), 4: (9, 18), 5: (9, 13)}
HORA_ALMOCO = 12
HORARIOS_PREFERIDOS = [10, 14, 16, 11, 15, 9, 17]
DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
INDICE_DIA = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5}
ANTECEDENCIA_MINIMA = timedelta(hours=3)


def especialidade_para(intencao: str | None) -> str:
    return "investimento" if intencao == "investimento" else "residencial"


def _horas_do_dia(dia_semana: int, deslocamento: int, periodo: str | None) -> list[int]:
    inicio, fim = EXPEDIENTE[dia_semana]
    validas = [h for h in range(inicio, fim) if h != HORA_ALMOCO]
    if periodo == "manha":
        validas = [h for h in validas if h < HORA_ALMOCO]
    elif periodo == "tarde":
        validas = [h for h in validas if h > HORA_ALMOCO]
    preferidas = [h for h in HORARIOS_PREFERIDOS if h in validas]
    restantes = [h for h in validas if h not in preferidas]
    ordem = preferidas + restantes
    if not ordem:
        return []
    deslocamento %= len(ordem)
    return ordem[deslocamento:] + ordem[:deslocamento]


def horarios_disponiveis(
    ocupados: set[tuple[str, str]],
    especialidade: str,
    agora: datetime | None = None,
    dia: str | None = None,
    periodo: str | None = None,
    quantidade: int = 3,
    dias_busca: int = 14,
) -> list[dict]:
    agora = agora or datetime.now()
    corretores = [c["nome"] for c in CORRETORES if c["especialidade"] == especialidade]
    limite = agora + ANTECEDENCIA_MINIMA
    por_dia = quantidade if dia else 1
    indice_dia = INDICE_DIA.get(dia) if dia else None
    resultado = []
    for d in range(dias_busca):
        data = agora.date() + timedelta(days=d)
        if data.weekday() not in EXPEDIENTE or (indice_dia is not None and data.weekday() != indice_dia):
            continue
        no_dia = 0
        for hora in _horas_do_dia(data.weekday(), len(resultado), periodo):
            inicio = datetime.combine(data, time(hora))
            if inicio < limite:
                continue
            livre = next((c for c in corretores if (inicio.isoformat(timespec="minutes"), c) not in ocupados), None)
            if not livre:
                continue
            resultado.append({"inicio": inicio.isoformat(timespec="minutes"), "corretor": livre})
            no_dia += 1
            if no_dia >= por_dia or len(resultado) >= quantidade:
                break
        if len(resultado) >= quantidade:
            break
    return sorted(resultado, key=lambda h: h["inicio"])


def formatar_horario(inicio_iso: str) -> str:
    inicio = datetime.fromisoformat(inicio_iso)
    hora = f"{inicio.hour}h" if inicio.minute == 0 else f"{inicio.hour}h{inicio.minute:02d}"
    return f"{DIAS_SEMANA[inicio.weekday()]}, {inicio:%d/%m} às {hora}"
