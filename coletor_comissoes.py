#!/usr/bin/env python3
"""
coletor_comissoes.py
Extrai Convocacoes para Comissoes dos eventos ja coletados da Agenda.
Enriquece CPIs com membros buscados ao vivo via coletor_bancada_cpi.
"""

import unicodedata
from coletor_bancada_cpi import buscar_deputados_psd, buscar_membros_cpi, CPIS_ATIVAS

COMISSAO_KEYWORDS = [
    "Reuniao da Comissao", "Reuniao da Comissao",
    "Reuniao do Conselho", "Reuniao do Conselho",
    "Reuniao da CPI",      "Reuniao da CPI",
    "Reuniao da CPMI",     "Reuniao da CPMI",
    "Reuniao da Frente",   "Reuniao da Frente",
    "Audiencia Publica",   "Audiencia Publica",
    "Sessao Tematica",     "Sessao Tematica",
    "Seminario",
    "Forum",
]

NAO_COMISSAO = ["Montagem", "Desmontagem", "Apoio ao Evento"]

_MAPA_CHAVE = [
    ("questoes impactantes",  "questoes_impactantes"),
    ("vazamento de dados",    "vazamento_dados"),
    ("descarte de materiais", "descarte_materiais"),
    ("lixoes",                "lixoes"),
]

# ── Utilitario ────────────────────────────────────────────────────────────────

def _normalizar(texto):
    return "".join(
        c for c in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(c) != "Mn"
    )

# ── Filtros ───────────────────────────────────────────────────────────────────

def is_comissao(ev):
    titulo = ev.get("titulo", "")
    if any(nc.lower() in titulo.lower() for nc in NAO_COMISSAO):
        return False
    return any(kw.lower() in titulo.lower() for kw in COMISSAO_KEYWORDS)


def extrair_comissoes(dias):
    resultado = []
    for d in dias:
        comissoes = [ev for ev in d.get("eventos", []) if is_comissao(ev)]
        if comissoes:
            resultado.append({
                "label":   d["label"],
                "data":    d["data"],
                "estilo":  d["estilo"],
                "eventos": comissoes,
            })
    return resultado


def _chave_por_titulo(titulo):
    t = _normalizar(titulo)
    for kw, chave in _MAPA_CHAVE:
        if _normalizar(kw) in t:
            return chave
    return None

# ── Enriquecimento com membros ────────────────────────────────────────────────

def enriquecer_cpis_com_membros(dias_comissoes):
    """Busca membros PSD frescos para cada evento de CPI/CPMI."""
    bancada_psd = buscar_deputados_psd()

    for dia in dias_comissoes:
        for ev in dia["eventos"]:
            titulo = ev.get("titulo", "")
            t = titulo.lower()

            if "cpi" not in t and "cpmi" not in t:
                ev.setdefault("membros_cpi", [])
                ev.setdefault("membros_psd", [])
                continue

            chave = _chave_por_titulo(titulo)
            if chave and chave in CPIS_ATIVAS:
                todos = buscar_membros_cpi(chave, CPIS_ATIVAS[chave])
            else:
                todos = []

            psd = [
                m for m in todos
                if any(_normalizar(dep) in _normalizar(m["nome"]) for dep in bancada_psd)
            ]

            ev["membros_cpi"] = todos
            ev["membros_psd"] = psd

            if psd:
                print("  [CPI] PSD: {}".format(", ".join(m["nome"] for m in psd)))

    return dias_comissoes

# ── HTML ──────────────────────────────────────────────────────────────────────

def _badge_tipo(titulo):
    t = titulo.lower()
    if "cpi" in t or "cpmi" in t:
        bg, cor, borda, txt = "#FEF0E7", "#C05621", "#F6AD55", "CPI"
    elif "audiencia" in t:
        bg, cor, borda, txt = "#EBF8FF", "#2B6CB0", "#90CDF4", "Audiencia"
    elif "frente" in t:
        bg, cor, borda, txt = "#F0FFF4", "#276749", "#9AE6B4", "Frente"
    elif "conselho" in t:
        bg, cor, borda, txt = "#FAF5FF", "#6B46C1", "#D6BCFA", "Conselho"
    else:
        bg, cor, borda, txt = "#EBF2FF", "#1A3A9C", "#BFD0F7", "Comissao"
    return (
        '<span style="display:inline-block;font-size:10px;font-weight:700;'
        'padding:1px 7px;border-radius:10px;border:1px solid {borda};'
        'background:{bg};color:{cor};margin-right:6px;">{txt}</span>'
    ).format(bg=bg, cor=cor, borda=borda, txt=txt)


def _html_membros(membros_lista, membros_psd):
    if not membros_lista:
        return ""
    nomes_psd = {_normalizar(m["nome"]) for m in membros_psd}
    partes = []
    for m in membros_lista:
        eh_psd = _normalizar(m["nome"]) in nomes_psd
        nome_fmt = (
            '<strong style="color:#7B6200;">{}</strong>'.format(m["nome"])
            if eh_psd else m["nome"]
        )
        partes.append(
            '{} <span style="color:#999;font-size:10px;">{}</span>'.format(
                nome_fmt, m["partido"]
            )
        )
    return (
        '<div style="margin-top:5px;font-size:11px;line-height:1.8;'
        'padding:4px 8px;border-radius:4px;background:#F0F4FF;'
        'border-left:2px solid #BFD0F7;">{}</div>'
    ).format(" &nbsp;&middot;&nbsp; ".join(partes))


def gerar_html_comissoes(dias_comissoes):
    header = (
        '\n<section id="comissoes">\n'
        '<h2 style="font-size:13px;font-weight:700;color:#1A3A9C;'
        'text-transform:uppercase;letter-spacing:.08em;'
        'border-bottom:2px solid #BFD0F7;padding-bottom:4px;margin-bottom:12px;">'
        '\U0001f50e Reuni\u00f5es de CPIs</h2>\n'
    )
    footer = '</section>\n'

    if not dias_comissoes:
        return (
            header
            + '<p style="color:#999;font-size:12px;">Nenhuma convoca\u00e7\u00e3o '
              'divulgada para os pr\u00f3ximos dias.</p>\n'
            + footer
        )

    blocos = []
    for dia in dias_comissoes:
        label, estilo, eventos = dia["label"], dia["estilo"], dia["eventos"]
        cor = "#1A3A9C" if estilo == "destaque" else "#96A7C0"

        bloco = (
            '<p style="font-size:11px;font-weight:700;color:{cor};'
            'text-transform:uppercase;letter-spacing:.06em;margin:10px 0 4px;">'
            '\u2014 {label} \u2014</p>\n'
        ).format(cor=cor, label=label)

        for ev in eventos:
            horario   = ev.get("horario", "")
            titulo    = ev.get("titulo", "")
            local     = ev.get("local", "")
            m_cpi     = ev.get("membros_cpi", [])
            m_psd     = ev.get("membros_psd", [])

            local_h   = (
                '<br><span style="font-size:11px;color:#666;">\U0001f4cd {}</span>'.format(local)
                if local else ""
            )
            membros_h = _html_membros(m_cpi, m_psd)
            opacity   = ' style="opacity:0.6"' if estilo == "muted" else ""

            bloco += (
                '<div{op} style="margin-bottom:10px;padding:6px 10px;'
                'border-left:3px solid {cor};background:#F7F9FF;">'
                '<span style="font-size:11px;font-weight:700;color:{cor};">{hr}</span> '
                '{badge}<span style="font-size:12px;">{titulo}</span>'
                '{local}{membros}'
                '</div>\n'
            ).format(
                op=opacity, cor=cor, hr=horario,
                badge=_badge_tipo(titulo), titulo=titulo,
                local=local_h, membros=membros_h,
            )

        blocos.append(bloco)

    return header + "\n".join(blocos) + footer
