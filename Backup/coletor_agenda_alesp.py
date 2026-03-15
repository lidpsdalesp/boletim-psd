#!/usr/bin/env python3
"""
Coletor automatico da Agenda da ALESP
- Segunda a Quinta: exibe HOJE + AMANHA
- Sexta: exibe HOJE + SABADO + DOMINGO + SEGUNDA
- Sab/Dom: resolve para proxima segunda como HOJE
"""

import re
import requests
from datetime import date, timedelta
from typing import List, Dict

ALESP_AGENDA_URL = "https://www.al.sp.gov.br/alesp/agenda"

BANCADA_PSD = [
    "Marcio Nakashima",
    "Marta Costa",
    "Oseias de Madureira",
    "Paulo Correa Jr",
    "Rafael Silva",
]

IGNORAR = [
    "Montagem", "Desmontagem", "Apoio ao Evento", "Apoio a",
    "Reuniao de Equipe", "Alesp de Portas Abertas",
    "Divisao de Comunicacao", "Exposicao", "Exposicoes",
    "Exposição", "Exposições", "Apoio à",
]

DIAS_SEMANA = [
    "Segunda-Feira", "Terca-Feira", "Quarta-Feira",
    "Quinta-Feira", "Sexta-Feira", "Sabado", "Domingo"
]
MESES = ["janeiro","fevereiro","marco","abril","maio","junho",
         "julho","agosto","setembro","outubro","novembro","dezembro"]


# ── Datas ─────────────────────────────────────────────────────────────────────

def dia_do_boletim(hoje=None):
    d = hoje or date.today()
    if d.weekday() == 5:
        return d + timedelta(days=2)
    elif d.weekday() == 6:
        return d + timedelta(days=1)
    return d


def dias_a_exibir(hoje=None):
    hoje = hoje or date.today()
    ref  = dia_do_boletim(hoje)

    if ref.weekday() == 4:
        return [
            {"data": ref,                     "label": "HOJE",          "estilo": "destaque"},
            {"data": ref + timedelta(days=1), "label": "SABADO",        "estilo": "muted"},
            {"data": ref + timedelta(days=2), "label": "DOMINGO",       "estilo": "muted"},
            {"data": ref + timedelta(days=3), "label": "SEGUNDA-FEIRA", "estilo": "muted"},
        ]
    else:
        return [
            {"data": ref,                     "label": "HOJE",   "estilo": "destaque"},
            {"data": ref + timedelta(days=1), "label": "AMANHA", "estilo": "muted"},
        ]


def formatar_data_br(d):
    dias = ["Segunda-Feira","Terca-Feira","Quarta-Feira",
            "Quinta-Feira","Sexta-Feira","Sabado","Domingo"]
    meses = ["janeiro","fevereiro","marco","abril","maio","junho",
             "julho","agosto","setembro","outubro","novembro","dezembro"]
    return "{}, {:02d}/{:02d}/{}".format(dias[d.weekday()], d.day, d.month, d.year)


# ── Parser ────────────────────────────────────────────────────────────────────

def parsear_evento(horario, texto):
    # Remove campo Horario
    texto = re.sub(r'Hor[aá]rio\s*:\s*das\s*\S+\s*[aà]s\s*\S+', '', texto)

    # Extrai Local
    local = ""
    m = re.search(r'Local\s*:\s*(.+?)(?=Solicitante|$)', texto, re.IGNORECASE)
    if m:
        local = m.group(1).strip().rstrip('*').strip()

    # Extrai Solicitante
    solicitante = ""
    m = re.search(r'Solicitante\(s\)\s*:\s*(.+?)$', texto, re.IGNORECASE)
    if m:
        solicitante = m.group(1).strip()

    # Titulo = tudo antes de "Horario", "Local" ou "Solicitante"
    titulo = re.split(r'Hor[aá]rio\s*:|Local\s*:|Solicitante', texto, flags=re.IGNORECASE)[0]
    titulo = titulo.strip().strip('"').strip()

    is_psd = any(dep.lower() in solicitante.lower() for dep in BANCADA_PSD)

    return {
        "horario": horario,
        "titulo": titulo,
        "local": local,
        "solicitante": solicitante,
        "is_psd": is_psd
    }


def deve_ignorar(ev):
    combinado = ev["titulo"] + " " + ev["solicitante"]
    return any(ig.lower() in combinado.lower() for ig in IGNORAR)


def parsear_evento(horario, texto):
    """Extrai titulo, local e solicitante do formato da ALESP."""
    # Remove campo Horario
    texto = re.sub(r'Hor[aá]rio\s*:?\s*das\s*\S+\s*[aà]s\s*\S+', '', texto, flags=re.IGNORECASE)

    # Extrai Local (aparece como "Local :" com espaço por causa do get_text do BeautifulSoup)
    local = ""
    m = re.search(r'Local\s*:?\s*(.+?)(?=Solicitante|$)', texto, re.IGNORECASE)
    if m:
        local = m.group(1).strip().rstrip('*').strip()

    # Extrai Solicitante
    solicitante = ""
    m = re.search(r'Solicitante\(s\)\s*:?\s*(.+?)$', texto, re.IGNORECASE)
    if m:
        solicitante = re.sub(r'https?://\S+', '', m.group(1)).strip()

    # Título = tudo antes de Horário, Local ou Solicitante
    titulo = re.split(r'Hor[aá]rio\s*:|Local\s*:|Solicitante', texto, flags=re.IGNORECASE)[0]
    titulo = re.sub(r'\s*"\s*', ' ', titulo).strip().strip("'\" ").strip()

    is_psd = any(dep.lower() in solicitante.lower() for dep in BANCADA_PSD)

    return {"horario": horario, "titulo": titulo,
            "local": local, "solicitante": solicitante, "is_psd": is_psd}


def deve_ignorar(ev):
    combinado = ev["titulo"] + " " + ev["solicitante"]
    return any(ig.lower() in combinado.lower() for ig in IGNORAR)


def parsear_agenda_html(html, data_alvo):
    """
    Parser correto para o HTML da ALESP.
    Estrutura real: <h3>Dia</h3> → <h4>Horário</h4> → <p>Conteúdo</p>
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    data_str = data_alvo.strftime("%d/%m/%Y")

    eventos = []
    dentro_do_dia = False

    for tag in soup.find_all(["h3", "h4"]):
        # Detecta cabeçalho do dia
        if tag.name == "h3":
            dentro_do_dia = data_str in tag.get_text()
            continue

        if not dentro_do_dia:
            continue

        # h4 = horário do evento
        horario = tag.get_text(strip=True)
        if not re.match(r'^\d{1,2}h\d{2}$', horario):
            continue

        # Conteúdo vem no próximo <p> irmão
        prox = tag.find_next_sibling()
        if not prox:
            continue
        texto = prox.get_text(" ", strip=True)

        ev = parsear_evento(horario, texto)
        if not ev["titulo"]:
            continue
        if deve_ignorar(ev):
            continue

        # Deduplicação por título
        chave = ev["titulo"][:40].lower().strip()
        if any(e["titulo"][:40].lower().strip() == chave for e in eventos):
            continue

        eventos.append(ev)

    return eventos


# ── Scraping ──────────────────────────────────────────────────────────────────

def buscar_agenda_completa(dias):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; BoletimPSD/1.0)"}
    resp = requests.get(ALESP_AGENDA_URL, headers=headers, timeout=15)
    resp.raise_for_status()
    for d in dias:
        d["eventos"] = parsear_agenda_html(resp.text, d["data"])
    return dias


# ── HTML ──────────────────────────────────────────────────────────────────────

def _itens_html(eventos, estilo):
    if not eventos:
        cor = "#5A6A85" if estilo == "destaque" else "#A0AABF"
        return '<p style="color:{cor};font-style:italic;font-size:12.5px;padding:6px 0">Sem eventos.</p>'.format(cor=cor)

    html = ""
    for ev in eventos:
        badge = '<span class="badge badge-psd">PSD</span>' if ev["is_psd"] else ""

        if ev["is_psd"] and estilo == "destaque":
            item_s = ' style="background:linear-gradient(90deg,#FFFBEA 0%,#FFFFF8 100%);border-left:3px solid #F5C800;margin:0 -20px;padding:10px 20px;"'
            time_s = ""
            name_s = ""
        elif estilo == "muted":
            item_s = ' style="opacity:0.5;filter:grayscale(15%);"'
            time_s = ' style="background:#96A7C0;"'
            name_s = ' style="font-weight:500;color:#4A5A75;"'
        else:
            item_s = ""
            time_s = ""
            name_s = ""

        local_h = "<span>&#128205; " + ev["local"] + "</span>" if ev["local"] else ""
        sol_h   = "<span>&#128100; " + ev["solicitante"] + "</span>" if ev["solicitante"] else ""
        b       = (" " + badge) if badge else ""

        html += "\n      <div class=\"agenda-item\"" + item_s + ">"
        html += "\n        <div class=\"agenda-time\"" + time_s + ">" + ev["horario"] + "</div>"
        html += "\n        <div class=\"agenda-content\">"
        html += "\n          <div class=\"agenda-name\"" + name_s + ">" + ev["titulo"] + b + "</div>"
        html += "\n          <div class=\"agenda-meta\">" + local_h + sol_h + "</div>"
        html += "\n        </div>"
        html += "\n      </div>"

    return html


def gerar_html_agenda(dias):
    corpo = ""
    for i, d in enumerate(dias):
        cor = "#1A3A9C" if d["estilo"] == "destaque" else "#8A9AB5"
        bt  = "border-top:none; padding-top:0;" if i == 0 else ""
        mt  = "" if i == 0 else "margin-top:16px;"
        corpo += """
    <div class="sub-label" style="color:{cor};{bt}{mt}">
      {label} &mdash; {data}
    </div>
    {itens}""".format(
            cor=cor, bt=bt, mt=mt,
            label="&#128197; " + d["label"],
            data=formatar_data_br(d["data"]),
            itens=_itens_html(d["eventos"], d["estilo"])
        )

    return """
  <div class="section-header">
    <span class="section-icon">&#128197;</span>
    <span class="section-title">Agenda de Eventos da Casa</span>
  </div>
  <div class="section-body">{corpo}
  </div>""".format(corpo=corpo)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    hoje = date.today()
    ref  = dia_do_boletim(hoje)
    print("Executando em:      {}".format(formatar_data_br(hoje)))
    print("Boletim para:       {}".format(formatar_data_br(ref)))

    dias = dias_a_exibir(hoje)
    print("Dias a exibir:      {}".format([d["label"] for d in dias]))
    print("")

    try:
        dias = buscar_agenda_completa(dias)

        for d in dias:
            print("[{}] {} -- {} evento(s)".format(
                d["label"], formatar_data_br(d["data"]), len(d["eventos"])))
            for ev in d["eventos"]:
                psd = "  [PSD]" if ev["is_psd"] else ""
                print("  {}  {}{}".format(ev["horario"], ev["titulo"][:55], psd))
                if ev["local"]:
                    print("         Local: {}".format(ev["local"]))
                if ev["solicitante"]:
                    print("         Solicitante: {}".format(ev["solicitante"]))
            print("")

        html_bloco = gerar_html_agenda(dias)
        with open("agenda_bloco.html", "w", encoding="utf-8") as f:
            f.write(html_bloco)
        print("Bloco HTML salvo em: agenda_bloco.html")

    except Exception as e:
        print("Erro: {}".format(e))
        raise
