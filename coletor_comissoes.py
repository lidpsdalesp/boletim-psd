#!/usr/bin/env python3
"""
coletor_comissoes.py
Extrai Convocacoes para Comissoes a partir dos eventos ja coletados da Agenda.
Busca membros das CPIs diretamente da ALESP (JSON leve; Selenium como fallback).
"""

import re
import time
import requests

# ── Dados primarios da ALESP ──────────────────────────────────────────────────

CPIS_CONHECIDAS = {
    "questoes impactantes":  {"id": "1000001276", "nome": "CPI – Questoes Impactantes e Nocivas ao Meio Ambiente"},
    "questões impactantes":  {"id": "1000001276", "nome": "CPI – Questoes Impactantes e Nocivas ao Meio Ambiente"},
    "vazamento de dados":    {"id": "1000001274", "nome": "CPI – Vazamento de Dados Cadastrais"},
    "descarte de materiais": {"id": "1000001275", "nome": "CPI – Descarte de Materiais Contaminantes"},
    "lixoes":                {"id": "1000001273", "nome": "CPI – Lixoes"},
    "lixões":                {"id": "1000001273", "nome": "CPI – Lixoes"},
}

BANCADA_PSD = [
    "Oseias de Madureira",
    "Marta Costa",
    "Marcio Nakashima",
    "Paulo Correa Jr",
    "Rafael Silva",
]

COMISSAO_KEYWORDS = [
    "Reuniao da Comissao", "Reunião da Comissão",
    "Reuniao do Conselho", "Reunião do Conselho",
    "Reuniao da CPI",     "Reunião da CPI",
    "Reuniao da CPMI",    "Reunião da CPMI",
    "Reuniao da Frente",  "Reunião da Frente",
    "Audiencia Publica",  "Audiência Pública",
    "Sessao Tematica",    "Sessão Temática",
    "Seminario",          "Seminário",
    "Forum",              "Fórum",
]

NAO_COMISSAO = ["Montagem", "Desmontagem", "Apoio ao Evento"]

# ── Filtros ───────────────────────────────────────────────────────────────────

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

# ── Busca de membros PSD ──────────────────────────────────────────────────────

def _id_cpi_por_titulo(titulo):
    """Mapeia titulo de evento para id_comissao da ALESP."""
    t = titulo.lower()
    for chave, dados in CPIS_CONHECIDAS.items():
        if chave in t:
            return dados["id"]
    return None


def _buscar_membros_requests(id_comissao):
    """Tenta endpoints JSON leves antes de recorrer ao Selenium."""
    candidatos = [
        "https://www.al.sp.gov.br/spl/api/comissao/membros?idComissao={id}&idLegislatura=20",
        "https://www.al.sp.gov.br/alesp/comissao/membros?idComissao={id}&idLegislatura=20",
        "https://www.al.sp.gov.br/WS/membrosComissao?idComissao={id}",
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.al.sp.gov.br/",
    }
    for url_tpl in candidatos:
        try:
            r = requests.get(url_tpl.format(id=id_comissao), headers=headers, timeout=8)
            if r.status_code == 200 and r.text.strip().startswith("["):
                dados = r.json()
                return [
                    {
                        "nome":    d.get("nomeDeputado", d.get("nome", "")),
                        "partido": d.get("siglaPartido", d.get("partido", "")),
                        "tipo":    d.get("tipoMembro", "Titular"),
                    }
                    for d in dados if d.get("nomeDeputado") or d.get("nome")
                ]
        except Exception:
            continue
    return []


def _buscar_membros_selenium(id_comissao):
    """Selenium headless — fallback para paginas com JS dinamico."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        opts = Options()
        opts.add_argument("--headless")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--disable-gpu")
        opts.add_argument("--window-size=1280,800")

        driver = webdriver.Chrome(options=opts)
        url = (
            "https://www.al.sp.gov.br/comissao/cpi/"
            "?idLegislatura=20&idComissao={}".format(id_comissao)
        )
        driver.get(url)

        # Clica na aba Membros se existir
        try:
            aba = driver.find_element(By.XPATH, "//a[contains(text(),'Membros')]")
            aba.click()
        except Exception:
            pass

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "table tr td, #membros tr td")
            )
        )
        time.sleep(1)

        membros = []
        rows = driver.find_elements(By.CSS_SELECTOR, "table tr")
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 2:
                nome    = cols[0].text.strip()
                partido = cols[1].text.strip() if len(cols) > 1 else ""
                tipo    = cols[2].text.strip() if len(cols) > 2 else "Titular"
                if nome and nome.lower() not in ("deputado", "nome", ""):
                    membros.append({"nome": nome, "partido": partido, "tipo": tipo})
        driver.quit()
        return membros

    except Exception as e:
        print("  [membros_cpi] Selenium indisponivel: {}".format(e))
        return []


def buscar_membros_cpi(id_comissao):
    """Retorna lista de membros de uma CPI. Tenta JSON, depois Selenium."""
    membros = _buscar_membros_requests(id_comissao)
    if not membros:
        membros = _buscar_membros_selenium(id_comissao)
    return membros


def membros_psd_na_cpi(id_comissao):
    """Retorna apenas membros da bancada PSD em uma CPI."""
    todos = buscar_membros_cpi(id_comissao)
    return [
        m for m in todos
        if any(dep.lower() in m["nome"].lower() for dep in BANCADA_PSD)
    ]


def enriquecer_cpis_com_membros(dias_comissoes):
    """
    Para cada evento de CPI/CPMI, busca membros PSD e
    injeta a chave 'membros_psd' no evento.
    """
    for dia in dias_comissoes:
        for ev in dia["eventos"]:
            titulo = ev.get("titulo", "")
            if "cpi" not in titulo.lower() and "cpmi" not in titulo.lower():
                ev.setdefault("membros_psd", [])
                continue
            id_cpi = _id_cpi_por_titulo(titulo)
            if id_cpi:
                print("  [membros_cpi] Buscando CPI id={}...".format(id_cpi))
                ev["membros_psd"] = membros_psd_na_cpi(id_cpi)
                if ev["membros_psd"]:
                    nomes = ", ".join(m["nome"] for m in ev["membros_psd"])
                    print("  [membros_cpi] PSD encontrado: {}".format(nomes))
                else:
                    print("  [membros_cpi] Sem membros PSD nesta CPI.")
            else:
                ev["membros_psd"] = []
    return dias_comissoes

# ── HTML ──────────────────────────────────────────────────────────────────────

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
        '<span style="display:inline-block;font-size:10px;font-weight:700;' +
        'padding:1px 7px;border-radius:10px;border:1px solid {borda};' +
        'background:{bg};color:{cor};margin-right:6px;">' +
        '{txt}</span>'
    ).format(bg=bg, cor=cor, borda=borda, txt=txt)


def _html_membros_psd(membros_psd):
    if not membros_psd:
        return ""
    nomes = ", ".join(
        "{} ({})".format(m["nome"], m["tipo"]) if m.get("tipo") else m["nome"]
        for m in membros_psd
    )
    return (
        '<div style="margin-top:5px;padding:3px 8px;border-radius:4px;' +
        'background:#FFFBEA;border:1px solid #F5C800;font-size:11px;color:#7B6200;">' +
        '<strong>🏛️ PSD:</strong> {}</div>'
    ).format(nomes)


def gerar_html_comissoes(dias_comissoes):
    """Gera o bloco HTML completo da secao Convocacoes para Comissoes."""
    header = (
        '\n<section id="comissoes">\n'
        '<h2 style="font-size:13px;font-weight:700;color:#1A3A9C;' +
        'text-transform:uppercase;letter-spacing:.08em;' +
        'border-bottom:2px solid #BFD0F7;padding-bottom:4px;margin-bottom:12px;">' +
        '🔎 Reuniões de Comissões</h2>\n'
    )
    footer = '</section>\n'

    if not dias_comissoes:
        return (
            header
            + '<p style="color:#999;font-size:12px;">Nenhuma convocação ' +
              'de comissão divulgada para os próximos dias.</p>\n'
            + footer
        )

    blocos = []
    for dia in dias_comissoes:
        label   = dia["label"]
        estilo  = dia["estilo"]
        eventos = dia["eventos"]

        cor = "#1A3A9C" if estilo == "destaque" else "#96A7C0"
        bloco = (
            '<p style="font-size:11px;font-weight:700;color:{cor};' +
            'text-transform:uppercase;letter-spacing:.06em;margin:10px 0 4px;">' +
            '— {label} —</p>\n'
        ).format(cor=cor, label=label)

        for ev in eventos:
            horario     = ev.get("horario", "")
            titulo      = ev.get("titulo", "")
            local       = ev.get("local",  "")
            membros_psd = ev.get("membros_psd", [])

            local_h   = (
                '<br><span style="font-size:11px;color:#666;">📍 {}</span>'.format(local)
                if local else ""
            )
            membros_h = _html_membros_psd(membros_psd)
            opacity   = ' style="opacity:0.6"' if estilo == "muted" else ""

            bloco += (
                '<div{op} style="margin-bottom:8px;padding:6px 10px;' +
                'border-left:3px solid {cor};background:#F7F9FF;">' +
                '<span style="font-size:11px;font-weight:700;color:{cor};">{hr}</span> ' +
                '{badge}<span style="font-size:12px;">{titulo}</span>' +
                '{local}{membros}' +
                '</div>\n'
            ).format(
                op=opacity, cor=cor, hr=horario,
                badge=_badge_tipo(titulo), titulo=titulo,
                local=local_h, membros=membros_h,
            )

        blocos.append(bloco)

    return header + "\n".join(blocos) + footer
