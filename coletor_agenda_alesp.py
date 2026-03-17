#!/usr/bin/env python3
"""
Coletor automatico da Agenda da ALESP
"""

import re
import requests
from datetime import date, datetime, timedelta, timezone
from typing import List, Dict
from bs4 import BeautifulSoup

ALESP_AGENDA_URL = "https://www.al.sp.gov.br/alesp/agenda"

BANCADA_PSD = [
    "Oseias de Madureira",
    "Marta Costa",
    "Marcio Nakashima",
    "Paulo Correa Jr",
    "Rafael Silva",
]

IGNORAR = [
    # Apenas eventos internos de gestão da equipe (não aparecem na agenda pública)
    "Reuniao de Equipe", "Reunião de Equipe",
    "Divisao de Comunicacao", "Divisão de Comunicação",
]

DIAS_SEMANA = ["Segunda-Feira","Terca-Feira","Quarta-Feira",
               "Quinta-Feira","Sexta-Feira","Sabado","Domingo"]


# ── Datas ─────────────────────────────────────────────────────────────────────

def dia_do_boletim(hoje=None):
    if hoje:
        d = hoje
    else:
        # Usa horário de Brasília (UTC-3)
        brt = timezone(timedelta(hours=-3))
        d = datetime.now(tz=brt).date()
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
    return "{}, {:02d}/{:02d}/{}".format(DIAS_SEMANA[d.weekday()], d.day, d.month, d.year)


# ── Parser ────────────────────────────────────────────────────────────────────

def extrair_campos(texto):
    """
    Extrai titulo, local e solicitante do texto de um evento da ALESP.
    O BeautifulSoup converte <strong>Local</strong>: em 'Local :'
    (com espaco antes dos dois pontos).
    """
    # Remove campo Horario
    texto = re.sub(r'Hor[aá]rio\s*:?\s*das\s*\S+\s*[aàa]s\s*\S+', '', texto, flags=re.IGNORECASE)
    texto = texto.strip()

    # Extrai Solicitante (sempre ao final)
    solicitante = ""
    m = re.search(r'Solicitante\(s\)\s*:?\s*(.+)$', texto, re.IGNORECASE)
    if m:
        solicitante = re.sub(r'https?://\S+', '', m.group(1)).strip()
        texto = texto[:m.start()].strip()

    # Extrai Local
    local = ""
    m = re.search(r'Local\s*:?\s*(.+)$', texto, re.IGNORECASE)
    if m:
        local = m.group(1).strip().rstrip('*').strip()
        texto = texto[:m.start()].strip()

    # O que sobra e o titulo
    titulo = re.sub(r'\s{2,}', ' ', texto).strip().strip('"\'').strip()

    is_psd = any(dep.lower() in solicitante.lower() for dep in BANCADA_PSD)

    return {"titulo": titulo, "local": local, "solicitante": solicitante, "is_psd": is_psd}


def deve_ignorar(ev):
    combinado = ev["titulo"] + " " + ev["solicitante"]
    return any(ig.lower() in combinado.lower() for ig in IGNORAR)


def parsear_dia(soup, data_alvo):
    """
    Extrai eventos de um dia específico.
    Correções:
    - Causa 1: 'dentro' só reseta se o <h3> contém padrão de data (DD/MM/YYYY)
    - Causa 2: deduplicação por (horario+titulo[:60]) em vez de titulo[:40]
    - Causa 4: fallback via find_next_sibling() se next_sibling não achar conteúdo
    """
    data_str = data_alvo.strftime("%d/%m/%Y")
    eventos  = []
    dentro   = False
    PAT_DATA = re.compile(r"\d{2}/\d{2}/\d{4}")

    todos = soup.find_all(["h3", "h4"])

    for idx, tag in enumerate(todos):
        if tag.name == "h3":
            texto_h3 = tag.get_text()
            # FIX CAUSA 1: só reseta 'dentro' se o h3 tem padrão de data
            if PAT_DATA.search(texto_h3):
                dentro = data_str in texto_h3
            # h3 sem data (ex: subtítulos da página) → não altera 'dentro'
            continue

        if not dentro:
            continue

        horario = tag.get_text(strip=True)
        if not re.match(r"^\d{1,2}h\d{2}$", horario):
            continue

        # Próximo marcador de limite
        proximo = todos[idx + 1] if idx + 1 < len(todos) else None

        # Coleta todos os nós irmãos entre este h4 e o próximo h4/h3
        partes = []
        no = tag.next_sibling
        while no:
            if no is proximo:
                break
            if hasattr(no, "get_text"):
                t = no.get_text(" ", strip=True)
                if t:
                    partes.append(t)
            elif isinstance(no, str) and no.strip():
                partes.append(no.strip())
            no = no.next_sibling

        # FIX CAUSA 4: se não achou conteúdo como irmão, tenta find_next_sibling
        if not partes:
            prox_tag = tag.find_next_sibling(True)
            if prox_tag and prox_tag is not proximo and prox_tag.name not in ["h3","h4"]:
                t = prox_tag.get_text(" ", strip=True)
                if t:
                    partes.append(t)

        texto = re.sub(r"\s{2,}", " ", " ".join(partes)).strip()
        if not texto:
            continue

        campos = extrair_campos(texto)
        ev = dict(horario=horario, **campos)

        if not ev["titulo"]:
            continue
        if deve_ignorar(ev):
            continue

        # FIX CAUSA 2: chave = horario + titulo[:60] para distinguir
        # horários iguais com títulos distintos (mas ainda remove 14h16 = 14h00)
        chave_titulo = ev["titulo"][:60].lower().strip()
        chave_hor    = ev["horario"]
        # Só deduplica se MESMO título E MESMO horário (ou horário-derivado como 14h16)
        if any(
            e["titulo"][:60].lower().strip() == chave_titulo
            for e in eventos
        ):
            continue

        eventos.append(ev)

    return eventos


def _itens_html(eventos, estilo):
    if not eventos:
        cor = "#5A6A85" if estilo == "destaque" else "#A0AABF"
        return '<p style="color:{};font-style:italic;font-size:12.5px;padding:6px 0">Sem eventos divulgados para este dia.</p>'.format(cor)

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

        # Badge ao lado direito do nome do deputado
        if ev["solicitante"] and badge:
            sol_h = "<span>&#128100; " + ev["solicitante"] + "</span> " + badge
        elif ev["solicitante"]:
            sol_h = "<span>&#128100; " + ev["solicitante"] + "</span>"
        else:
            sol_h = ""

        html += '\n      <div class="agenda-item"' + item_s + ">"
        html += '\n        <div class="agenda-time"' + time_s + ">" + ev["horario"] + "</div>"
        html += '\n        <div class="agenda-content">'
        html += '\n          <div class="agenda-name"' + name_s + ">" + ev["titulo"] + "</div>"
        html += '\n          <div class="agenda-meta">' + local_h + sol_h + "</div>"
        html += '\n        </div>'
        html += '\n      </div>'

    return html


def gerar_html_agenda(dias):
    corpo = ""
    for i, d in enumerate(dias):
        cor = "#1A3A9C" if d["estilo"] == "destaque" else "#8A9AB5"
        bt  = "border-top:none;padding-top:0;" if i == 0 else ""
        mt  = "" if i == 0 else "margin-top:16px;"
        corpo += '\n    <div class="sub-label" style="color:{};{}{}">\n      &#128197; {} &mdash; {}\n    </div>\n    {}'.format(
            cor, bt, mt,
            d["label"],
            formatar_data_br(d["data"]),
            _itens_html(d["eventos"], d["estilo"])
        )

    return (
        '\n  <div class="section-header">'
        '\n    <span class="section-icon">&#128197;</span>'
        '\n    <span class="section-title">Agenda de Eventos da Casa</span>'
        '\n  </div>'
        '\n  <div class="section-body">' + corpo + '\n  </div>'
    )


# ── Main ──────────────────────────────────────────────────────────────────────


# ── Scraping principal ────────────────────────────────────────────────────────
ALESP_AGENDA_URL = "https://www.al.sp.gov.br/alesp/agenda"

def buscar_agenda_completa(dias):
    """
    Faz o request à ALESP, parseia o HTML e preenche ev["eventos"]
    em cada entrada de 'dias' (lista de dicts com chaves 'data', 'label', etc.)
    Retorna a lista 'dias' com o campo 'eventos' preenchido.
    """
    headers = {"User-Agent": "Mozilla/5.0 (compatible; BoletimPSD/1.0)"}
    resp = requests.get(ALESP_AGENDA_URL, headers=headers, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    for d in dias:
        d["eventos"] = parsear_dia(soup, d["data"])

    return dias


if __name__ == "__main__":
    import sys
    debug = "--debug" in sys.argv

    hoje = date.today()
    ref  = dia_do_boletim(hoje)
    print("Executando em:  {}".format(formatar_data_br(hoje)))
    print("Boletim para:   {}".format(formatar_data_br(ref)))

    dias = dias_a_exibir(hoje)
    print("Dias:           {}\n".format([d["label"] for d in dias]))

    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; BoletimPSD/1.0)"}
        resp = requests.get(ALESP_AGENDA_URL, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        if debug:
            print("\n=== DEBUG: estrutura HTML ===")
            data_str = dias[0]["data"].strftime("%d/%m/%Y")
            dentro = False
            count = 0
            for tag in soup.find_all(["h3", "h4"]):
                if tag.name == "h3":
                    dentro = data_str in tag.get_text()
                    if dentro:
                        print("DIA: {}".format(tag.get_text(strip=True)))
                    continue
                if not dentro:
                    continue
                horario = tag.get_text(strip=True)
                prox = tag.find_next_sibling()
                tipo = type(prox).__name__ if prox else "None"
                nome = getattr(prox, "name", "text-node") if prox else "None"
                txt  = prox.get_text(" ", strip=True)[:80] if prox else ""
                print("  H4=[{}]  next=[{}:{}]  texto=[{}]".format(horario, tipo, nome, txt))
                count += 1
                if count >= 8:
                    break
            print("=== FIM DEBUG ===\n")

        for d in dias:
            d["eventos"] = parsear_dia(soup, d["data"])

        for d in dias:
            print("[{}] {} -- {} evento(s)".format(
                d["label"], formatar_data_br(d["data"]), len(d["eventos"])))
            for ev in d["eventos"]:
                psd = "  [PSD]" if ev["is_psd"] else ""
                print("  {}  {}{}".format(ev["horario"], ev["titulo"][:55], psd))
                print("         Local: [{}]".format(ev["local"]))
                print("         Solicitante: [{}]".format(ev["solicitante"]))
            print("")

        html_bloco = gerar_html_agenda(dias)
        with open("agenda_bloco.html", "w", encoding="utf-8") as f:
            f.write(html_bloco)
        print("Salvo em: agenda_bloco.html")

    except Exception as e:
        print("Erro: {}".format(e))
        raise
