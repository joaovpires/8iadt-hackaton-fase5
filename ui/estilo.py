import hashlib
from html import escape

import streamlit as st

from src.tools import agenda, imoveis

FOTOS = {
    "apartamento": [
        "1493809842364-78817add7ffb", "1502672260266-1c1ef2d93688", "1505691938895-1758d7feb511",
        "1554995207-c18c203602cb", "1560185007-cde436f6a4d0", "1560448204-e02f11c3d0e2",
        "1600607687939-ce8a6c25118c", "1484154218962-a197022b5858",
    ],
    "studio": ["1522708323590-d24dbb6b0267", "1586023492125-27b2c045efd7", "1631049307264-da0ec9d70304"],
    "casa": [
        "1512917774080-9991f1c4c750", "1567496898669-ee935f5f647a", "1600585154340-be6161a56a0c",
        "1600596542815-ffad4c1539a9", "1613490493576-7fde63acd811",
    ],
    "sala_comercial": ["1497366216548-37526070297c", "1486406146926-c627a92ad1ab"],
    "loja": ["1497366216548-37526070297c", "1545324418-cc1a3fa10c00"],
}
FOTO_HERO = "1600607687939-ce8a6c25118c"

CSS = """
<style>
:root {
  --azul: #2B4BF2;
  --azul-escuro: #1C33B8;
  --azul-claro: #EEF1FF;
  --tinta: #14171F;
  --texto-2: #5A6172;
  --texto-3: #8A90A0;
  --borda: #E6E9F0;
  --fundo-2: #F4F6FB;
  --verde: #12A26B;
  --verde-claro: #E6F6EF;
  --laranja: #C96A0A;
  --laranja-claro: #FDF1E3;
  --vermelho: #D93D42;
  --vermelho-claro: #FDECEC;
  --sombra: 0 1px 2px rgba(20, 23, 31, .04), 0 8px 24px rgba(20, 23, 31, .06);
}
.block-container { padding-top: 3.6rem; padding-bottom: 1.5rem; max-width: 1180px; }
h1, h2, h3 { letter-spacing: -0.02em; }
[data-testid="stHeader"] { border-bottom: 1px solid var(--borda); }

.hero {
  display: grid; grid-template-columns: 1.15fr 1fr; gap: 0; overflow: hidden;
  border-radius: 20px; background: var(--azul-claro); margin-bottom: 1rem;
}
.hero-texto { padding: 1.7rem 1.9rem 1.6rem; display: flex; flex-direction: column; justify-content: center; }
.hero-texto .selo {
  align-self: flex-start; background: #fff; color: var(--azul); font-weight: 700; font-size: .78rem;
  padding: .35rem .75rem; border-radius: 999px; margin-bottom: 1rem; box-shadow: var(--sombra);
}
.hero-texto h1 { font-size: 1.85rem; line-height: 1.15; margin: 0 0 .6rem; color: var(--tinta); font-weight: 800; padding: 0; }
.hero-texto h1 span { color: var(--azul); }
.hero-texto p { color: var(--texto-2); font-size: .95rem; margin: 0; line-height: 1.55; }
.hero-foto { min-height: 200px; background-size: cover; background-position: center; }
.hero-compacto {
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  padding: .65rem 1.1rem; border-radius: 16px; background: var(--azul-claro); margin-bottom: .6rem;
}
.hero-compacto b { font-size: 1.02rem; color: var(--tinta); }
.hero-compacto span { color: var(--texto-2); font-size: .85rem; }
[data-testid="stLayoutWrapper"]:has(> .st-key-janela-chat) { flex: 0 0 auto !important; height: auto !important; }
.st-key-janela-chat { height: clamp(260px, calc(100vh - 400px), 380px) !important; flex: 0 0 auto !important; }

.chat { display: flex; flex-direction: column; gap: .7rem; padding: .25rem .1rem; }
.msg { display: flex; gap: .6rem; align-items: flex-end; max-width: 86%; }
.msg.cliente { align-self: flex-end; flex-direction: row-reverse; }
.avatar-lia {
  flex: 0 0 30px; height: 30px; border-radius: 50%; background: var(--azul); color: #fff;
  display: grid; place-items: center; font-weight: 800; font-size: .95rem;
}
.bolha {
  padding: .6rem .9rem; border-radius: 16px; line-height: 1.5; font-size: .95rem; color: var(--tinta);
  background: var(--fundo-2); border-bottom-left-radius: 6px; white-space: pre-wrap; word-wrap: break-word;
}
.msg.cliente .bolha { background: var(--azul); color: #fff; border-bottom-left-radius: 18px; border-bottom-right-radius: 6px; }
.meta { font-size: .74rem; color: var(--texto-3); margin-top: .35rem; }
.msg.cliente .meta { color: rgba(255,255,255,.75); text-align: right; }
.digitando span {
  display: inline-block; width: 7px; height: 7px; margin: 0 2px; border-radius: 50%;
  background: var(--texto-3); animation: pulo 1.2s infinite ease-in-out;
}
.digitando span:nth-child(2) { animation-delay: .15s; }
.digitando span:nth-child(3) { animation-delay: .3s; }
@keyframes pulo { 0%, 60%, 100% { transform: translateY(0); opacity: .5; } 30% { transform: translateY(-5px); opacity: 1; } }
.vazio { text-align: center; color: var(--texto-3); padding: 2.5rem 1rem; font-size: .95rem; }

.painel-titulo { font-weight: 800; font-size: 1rem; margin: 0 0 .6rem; color: var(--tinta); }
.pilulas { display: flex; flex-wrap: wrap; gap: .4rem; margin-bottom: .5rem; }
.pilula {
  display: inline-flex; align-items: center; gap: .3rem; padding: .3rem .7rem; border-radius: 999px;
  font-size: .8rem; font-weight: 700; background: var(--fundo-2); color: var(--texto-2);
}
.pilula.azul { background: var(--azul-claro); color: var(--azul); }
.pilula.verde { background: var(--verde-claro); color: var(--verde); }
.pilula.laranja { background: var(--laranja-claro); color: var(--laranja); }
.pilula.vermelho { background: var(--vermelho-claro); color: var(--vermelho); }
.progresso { margin: .4rem 0 .7rem; }
.progresso .rotulo { display: flex; justify-content: space-between; font-size: .82rem; color: var(--texto-2); margin-bottom: .35rem; }
.progresso .trilho { height: 8px; border-radius: 999px; background: var(--fundo-2); overflow: hidden; }
.progresso .barra { height: 100%; border-radius: 999px; background: var(--azul); }
.dados { display: grid; grid-template-columns: 1fr 1fr; gap: .35rem; }
.dado { background: var(--fundo-2); border-radius: 10px; padding: .4rem .6rem; }
.dado small { display: block; color: var(--texto-3); font-size: .66rem; font-weight: 600; text-transform: uppercase; letter-spacing: .03em; }
.dado b { font-size: .85rem; color: var(--tinta); font-weight: 700; }
.dado.largo { grid-column: span 2; }

.visita {
  display: flex; gap: .8rem; align-items: center; padding: .9rem 1rem; border-radius: 16px;
  background: var(--verde-claro); color: var(--tinta); margin: .25rem 0 .9rem;
}
.visita .icone { font-size: 1.5rem; }
.visita small { display: block; color: var(--verde); font-weight: 800; font-size: .72rem; text-transform: uppercase; letter-spacing: .04em; }
.visita b { font-size: .95rem; }

.cards { display: grid; gap: .8rem; }
.cards.grade { grid-template-columns: repeat(auto-fill, minmax(175px, 1fr)); }
.card-imovel { border: 1px solid var(--borda); border-radius: 18px; overflow: hidden; background: #fff; box-shadow: var(--sombra); }
.card-imovel .foto {
  height: 120px; background-color: var(--azul-claro); background-size: cover; background-position: center;
  position: relative;
}
.card-imovel .etiquetas { position: absolute; top: .6rem; left: .6rem; display: flex; gap: .35rem; }
.card-imovel .etiqueta {
  background: rgba(255,255,255,.94); color: var(--tinta); font-size: .72rem; font-weight: 800;
  padding: .22rem .55rem; border-radius: 999px;
}
.card-imovel .etiqueta.destaque { background: var(--azul); color: #fff; }
.card-imovel .info { padding: .65rem .8rem .8rem; }
.card-imovel .preco { font-size: 1.05rem; font-weight: 800; color: var(--tinta); }
.card-imovel .extra { font-size: .78rem; color: var(--texto-3); margin-bottom: .35rem; }
.card-imovel .titulo { font-weight: 700; font-size: .92rem; color: var(--tinta); }
.card-imovel .specs { font-size: .82rem; color: var(--texto-2); margin-top: .15rem; }
.card-imovel .rent { margin-top: .45rem; }

.secao { font-weight: 800; font-size: 1rem; margin: .9rem 0 .5rem; }
.cabecalho-pagina h1 { font-size: 1.6rem; margin: 0; padding: 0; font-weight: 800; }
.cabecalho-pagina p { color: var(--texto-2); margin: .2rem 0 .9rem; font-size: .92rem; }

[data-testid="stMetric"] { background: #fff; box-shadow: var(--sombra); padding: .7rem .9rem !important; }
[data-testid="stMetricLabel"] p { color: var(--texto-2); font-weight: 600; font-size: .85rem; }
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) { border-radius: 20px; }
.stButton button, .stDownloadButton button { font-weight: 700; }

@media (max-width: 760px) {
  .hero { grid-template-columns: 1fr; }
  .hero-foto { min-height: 160px; }
  .hero-texto { padding: 1.6rem; }
  .hero-texto h1 { font-size: 1.7rem; }
  .msg { max-width: 94%; }
}
</style>
"""


def aplicar_estilo() -> None:
    st.html(CSS)


def url_foto(foto_id: str, largura: int = 640, altura: int = 420) -> str:
    return f"https://images.unsplash.com/photo-{foto_id}?w={largura}&h={altura}&fit=crop&q=70&auto=format"


def foto_do_imovel(imovel: dict, evitar: set[str] | None = None) -> str:
    opcoes = FOTOS.get(imovel["tipo"], FOTOS["apartamento"])
    inicio = int(hashlib.md5(imovel["codigo"].encode()).hexdigest(), 16) % len(opcoes)
    evitar = evitar if evitar is not None else set()
    for deslocamento in range(len(opcoes)):
        foto = opcoes[(inicio + deslocamento) % len(opcoes)]
        if foto not in evitar:
            evitar.add(foto)
            return url_foto(foto)
    return url_foto(opcoes[inicio])


def texto_html(texto: str) -> str:
    return escape(texto or "").replace("\n", "<br>")


def bolha(papel: str, conteudo: str, meta: str = "") -> str:
    meta_html = f'<div class="meta">{escape(meta)}</div>' if meta else ""
    if papel == "user":
        return f'<div class="msg cliente"><div class="bolha">{texto_html(conteudo)}{meta_html}</div></div>'
    return f'<div class="msg lia"><div class="avatar-lia">L</div><div class="bolha">{texto_html(conteudo)}{meta_html}</div></div>'


def bolha_digitando() -> str:
    return '<div class="chat"><div class="msg lia"><div class="avatar-lia">L</div><div class="bolha digitando"><span></span><span></span><span></span></div></div></div>'


def pilula(texto: str, cor: str = "") -> str:
    return f'<span class="pilula {cor}">{escape(texto)}</span>'


def barra_progresso(rotulo: str, valor: int, total: int) -> str:
    percentual = 0 if not total else round(100 * valor / total)
    return (
        f'<div class="progresso"><div class="rotulo"><span>{escape(rotulo)}</span><b>{valor}/{total}</b></div>'
        f'<div class="trilho"><div class="barra" style="width:{percentual}%"></div></div></div>'
    )


def card_imovel(imovel: dict, destaque: bool = False, investimento: bool = False, fotos_usadas: set[str] | None = None) -> str:
    aluguel = imovel["finalidade"] == "aluguel"
    preco = imoveis.formatar_preco(imovel["preco"]) + ("<small style='font-weight:600;font-size:.8rem'>/mês</small>" if aluguel else "")
    extra = f"Condomínio {imoveis.formatar_preco(imovel['condominio'])}" if imovel["condominio"] else "Sem condomínio"
    detalhes = [f"{imovel['area_m2']} m²"]
    if imovel["quartos"]:
        detalhes.append(f"{imovel['quartos']} quarto{'s' if imovel['quartos'] > 1 else ''}")
    if imovel["vagas"]:
        detalhes.append(f"{imovel['vagas']} vaga{'s' if imovel['vagas'] > 1 else ''}")
    rentabilidade = ""
    if investimento and imovel.get("rentabilidade_mensal") and not aluguel:
        taxa = f"{imovel['rentabilidade_mensal']:.2f}".replace(".", ",")
        rentabilidade = f'<div class="rent">{pilula(f"Rentab. estimada {taxa}% a.m.", "verde")}</div>'
    etiqueta_destaque = '<span class="etiqueta destaque">Seu favorito</span>' if destaque else ""
    if imovel.get("acima_do_orcamento"):
        etiqueta_destaque += '<span class="etiqueta">Acima do orçamento</span>'
    return f"""
<div class="card-imovel">
  <div class="foto" style="background-image:url('{foto_do_imovel(imovel, fotos_usadas)}')">
    <div class="etiquetas"><span class="etiqueta">{'Aluguel' if aluguel else 'Venda'}</span><span class="etiqueta">{escape(imovel['codigo'])}</span>{etiqueta_destaque}</div>
  </div>
  <div class="info">
    <div class="preco">{preco}</div>
    <div class="extra">{extra}</div>
    <div class="titulo">{imoveis.NOMES_TIPO[imovel['tipo']]} · {escape(imovel['bairro'])}</div>
    <div class="specs">{' · '.join(detalhes)}</div>
    {rentabilidade}
  </div>
</div>"""


def cards_imoveis(lista: list[dict], grade: bool = False, favorito: str | None = None, investimento: bool = False) -> str:
    fotos_usadas: set[str] = set()
    cartoes = "".join(card_imovel(i, destaque=i["codigo"] == favorito, investimento=investimento, fotos_usadas=fotos_usadas) for i in lista)
    return f'<div class="cards {"grade" if grade else ""}">{cartoes}</div>'


def card_visita(reuniao: dict) -> str:
    imovel = f" · imóvel {escape(reuniao['imovel_codigo'])}" if reuniao.get("imovel_codigo") else ""
    titulo = "Visita agendada" if reuniao["tipo"] == "visita" else "Reunião agendada"
    return (
        f'<div class="visita"><div class="icone">📅</div><div><small>{titulo}</small>'
        f'<b>{escape(agenda.formatar_horario(reuniao["inicio"]).capitalize())}</b><br>'
        f'<span style="color:var(--texto-2);font-size:.85rem">com {escape(reuniao["corretor"])}{imovel}</span></div></div>'
    )


def cabecalho(titulo: str, subtitulo: str) -> None:
    st.html(f'<div class="cabecalho-pagina"><h1>{escape(titulo)}</h1><p>{escape(subtitulo)}</p></div>')
