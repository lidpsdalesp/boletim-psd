#!/usr/bin/env python3
"""
coletor_comissoes.py
Extrai Convocacoes para Comissoes a partir dos eventos ja coletados da Agenda.
Nao faz scraping adicional — usa os dados de 'dias' ja preenchidos.
"""

COMISSAO_KEYWORDS = [
    "Reuniao da Comissao", "Reunião da Comissão",
    "Reuniao do Conselho", "Reunião do Conselho",
    "Reuniao da CPI",      "Reunião da CPI",
    "Reuniao da CPMI",     "Reunião da CPMI",
    "Reuniao da Frente",   "Reunião da Frente",
    "Audiencia Publica",   "Audiência Pública",
    "Sessao Tematica",     "Sessão Temática",
    "Seminario",           "Seminário",
    "Forum",               "Fórum",
]

NAO_COMISSAO = ["Montagem", "Desmontagem", "Apoio ao Evento"]


def is_comissao(ev):
    titulo = ev.get("titulo", "")
    if any(nc.lower() in titulo.lower() for nc in NAO_COMISSAO):
        return False
    return any(kw.lower() in titulo.lower() for kw in COMISSAO_KEYWORDS)


def extrair_comissoes(dias):
    """Filtra eventos de comissao de cada dia da lista 'dias'."""
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


def _badge_tipo(titulo):
    t = titulo.lower()
    if "cpi" in t or "cpmi" in t:
        bg, cor, borda, txt = "#FEF0E7", "#C05621", "#F6AD55", "CPI"
    elif "audiencia" in t or "audiência" in t:
        bg, cor, borda, txt = "#EBF8FF", "#2B6CB0", "#90CDF4", "Audiência"
    elif "frente" in t:
        bg, cor, borda, txt = "#F0FFF4", "#276749", "#9AE6B4", "Frente"
    elif "conselho" in t:
        bg, cor, borda, txt = "#FAF5FF", "#6B46C1", "#D6BCFA", "Conselho"
    else:
        bg, cor, borda, txt = "#EBF2FF", "#1A3A9C", "#BFD0F7", "Comissão"
    return (
        '<span style="background:{bg};color:{cor};border:1px solid {borda};'
        'border-radius:4px;padding:1px 7px;font-size:10.5px;font-weight:700;">'
        '{txt}</span>'
    ).format(bg=bg, cor=cor, borda=borda, txt=txt)


def gerar_html_comissoes(dias_comissoes):
    """Gera o bloco HTML completo da secao Convocacoes para Comissoes."""
    header = (
        '\n  <div class="section-header">'
        '\n    <span class="section-icon">&#127963;</span>'
        '\n    <span class="section-title">Convocações para Comissões</span>'
        '\n  </div>'
    )

    if not dias_comissoes:
        vazio = (
            '\n  <div class="section-body">'
            '\n    <p style="color:#5A6A85;font-style:italic;font-size:12.5px;padding:6px 0">'
            'Nenhuma convocação de comissão divulgada para os próximos dias.</p>'
            '\n  </div>'
        )
        return header + vazio

    corpo = ""
    for i, d in enumerate(dias_comissoes):
        cor = "#1A3A9C" if d["estilo"] == "destaque" else "#8A9AB5"
        bt  = "border-top:none;padding-top:0;" if i == 0 else ""
        mt  = "" if i == 0 else "margin-top:16px;"
        corpo += (
            '\n    <div class="sub-label" style="color:{cor};{bt}{mt}">'
            '\n      &#128203; {label} &mdash; {data}'
            '\n    </div>'
        ).format(
            cor=cor, bt=bt, mt=mt,
            label=d["label"],
            data=d["data"].strftime("%d/%m/%Y"),
        )

        for ev in d["eventos"]:
            badge_tipo = _badge_tipo(ev["titulo"])
            badge_psd  = '<span class="badge badge-psd">PSD</span>' if ev.get("is_psd") else ""

            if ev.get("is_psd") and d["estilo"] == "destaque":
                item_s = ' style="background:linear-gradient(90deg,#FFFBEA 0%,#FFFFF8 100%);border-left:3px solid #F5C800;margin:0 -20px;padding:10px 20px;"'
            elif d["estilo"] == "muted":
                item_s = ' style="opacity:0.55;filter:grayscale(15%);"'
            else:
                item_s = ""

            local_h = ""
            if ev.get("local"):
                local_h = "&#128205; " + ev["local"]

            sol_h = ""
            if ev.get("solicitante"):
                sol_h = "&#128100; " + ev["solicitante"]
                if badge_psd:
                    sol_h += " " + badge_psd

            meta_parts = [p for p in [local_h, sol_h] if p]
            meta_h = ""
            if meta_parts:
                meta_h = (
                    '<div class="event-meta">'
                    + " &nbsp;·&nbsp; ".join(meta_parts)
                    + "</div>"
                )

            corpo += (
                '\n    <div class="agenda-item"{item_s}>'
                '\n      <div class="agenda-time">{hora}</div>'
                '\n      <div class="agenda-content">'
                '\n        <div class="event-name">{badge_tipo} {titulo}</div>'
                '\n        {meta_h}'
                '\n      </div>'
                '\n    </div>'
            ).format(
                item_s=item_s,
                hora=ev["horario"],
                badge_tipo=badge_tipo,
                titulo=ev["titulo"],
                meta_h=meta_h,
            )

    return header + '\n  <div class="section-body">' + corpo + '\n  </div>'


if __name__ == "__main__":
    from datetime import date
    from coletor_agenda_alesp import dias_a_exibir, buscar_agenda_completa

    hoje = date.today()
    dias = dias_a_exibir(hoje)
    dias = buscar_agenda_completa(dias)

    comissoes = extrair_comissoes(dias)
    total = sum(len(d["eventos"]) for d in comissoes)
    print("Comissoes encontradas: {}".format(total))
    for d in comissoes:
        print("\n  {} ({})".format(d["label"], d["data"].strftime("%d/%m/%Y")))
        for ev in d["eventos"]:
            psd = " [PSD]" if ev.get("is_psd") else ""
            print("    {}  {}{}".format(ev["horario"], ev["titulo"][:65], psd))
