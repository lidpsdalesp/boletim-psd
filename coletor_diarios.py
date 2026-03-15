#!/usr/bin/env python3
"""
coletor_diarios.py
Gera as seções Diário Legislativo e Diário Executivo do Boletim PSD.

Estratégia (3 camadas):
  1. Tenta buscar a API interna do doe.sp.gov.br (detectada via source JS)
  2. Tenta requests normal (caso o servidor retorne HTML sem JS)
  3. Fallback: gera card com link direto ao DOE — sempre funciona
"""

import re
import requests
from bs4 import BeautifulSoup
from datetime import date, timedelta
from urllib.parse import urlencode, quote

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BoletimPSD/1.0)"}
DOE_BASE = "https://www.doe.sp.gov.br"

# ── Seções de interesse ───────────────────────────────────────────────────────
DIARIO_LEG = {
    "journalName":    "Legislativo",
    "rootSectionName": "Atos Legislativos e Parlamentares da Assembleia",
    "icon":  "&#128218;",
    "titulo": "Diário Legislativo — Atos da ALESP",
    "cor":    "#1A3A9C",
    "bg":     "#EBF2FF",
}

DIARIO_EXE = {
    "journalName":    "Executivo",
    "rootSectionName": "Atos de Gestão e Despesas",
    "icon":  "&#127963;",
    "titulo": "Diário Executivo — Atos do Governo",
    "cor":    "#276749",
    "bg":     "#F0FFF4",
}

# ── URLs ──────────────────────────────────────────────────────────────────────
def _url_sumario(cfg, ref_date):
    """Monta a URL do sumário no doe.sp.gov.br para uma data."""
    # Formato da data no DOE: YYYY-M-D (sem zero-padding)
    d = "{}-{}-{}".format(ref_date.year, ref_date.month, ref_date.day)
    params = {
        "journalName":    cfg["journalName"],
        "rootSectionName": cfg["rootSectionName"],
        "editionDate":    d,
    }
    return DOE_BASE + "/sumario?" + urlencode(params)


def _url_api_articles(cfg, ref_date):
    """Tenta endpoint de API REST que o SPA usa internamente."""
    d = ref_date.strftime("%Y-%m-%d")
    secao = quote(cfg["rootSectionName"])
    return (
        "{}/api/v1/articles?journalName={}&editionDate={}&sectionName={}&pageSize=50"
        .format(DOE_BASE, cfg["journalName"], d, secao)
    )


# ── Tentativa de scraping ─────────────────────────────────────────────────────
def _tentar_api(cfg, ref_date):
    """Tenta a API REST interna. Retorna lista de {titulo, url} ou []."""
    url = _url_api_articles(cfg, ref_date)
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200 and r.headers.get("content-type","").startswith("application/json"):
            data = r.json()
            items = data if isinstance(data, list) else data.get("items", data.get("data", []))
            result = []
            for item in items[:15]:
                titulo = item.get("title") or item.get("titulo") or item.get("name","")
                href   = item.get("url")  or item.get("link")  or ""
                if titulo:
                    result.append({"titulo": titulo, "url": href})
            return result
    except Exception:
        pass
    return []


# Palavras de links de navegação/menu que não são matérias
_NAV_SKIP = {
    "sp + digital", "diário oficial", "doe/sp", "busca", "mapa do site",
    "acessibilidade", "início", "home", "sair", "entrar", "login",
    "anteriores", "próximo", "anterior", "voltar",
}

def _tentar_html(cfg, ref_date):
    """Tenta scraping HTML (caso o DOE sirva server-side). Retorna lista ou []."""
    url = _url_sumario(cfg, ref_date)
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        items = []
        for a in soup.find_all("a", href=True):
            txt = a.get_text(strip=True)
            # Filtra links de navegação/menu
            if txt.lower() in _NAV_SKIP or len(txt) < 15:
                continue
            # Precisa ter traço ou número (padrão de matérias do DOE)
            if not re.search(r"[\-–/]|\d", txt):
                continue
            href = a["href"]
            if not href.startswith("http"):
                href = DOE_BASE + href
            items.append({"titulo": txt, "url": href})
        return items[:15]
    except Exception:
        return []


def buscar_diario(cfg, ref_date):
    """
    Tenta obter os atos publicados. Retorna dict:
      {
        'items': [{'titulo': ..., 'url': ...}, ...],  # pode ser vazio
        'url_sumario': '...',   # link direto ao DOE para fallback
        'data_ref': date,
      }
    """
    url_sumario = _url_sumario(cfg, ref_date)

    # Camada 1: API REST interna
    items = _tentar_api(cfg, ref_date)

    # Camada 2: HTML direto
    if not items:
        items = _tentar_html(cfg, ref_date)

    return {
        "items":       items,
        "url_sumario": url_sumario,
        "data_ref":    ref_date,
    }


# ── Renderização HTML ─────────────────────────────────────────────────────────
def _card_link(cfg, result):
    """Card com link direto ao DOE (sempre exibido, mesmo se houver itens)."""
    data_fmt = result["data_ref"].strftime("%d/%m/%Y")
    return (
        '\n    <div style="margin:8px 0 4px 0;">'
        '<a href="{url}" target="_blank" rel="noopener" '
        'style="display:inline-flex;align-items:center;gap:6px;'
        'background:{bg};color:{cor};border:1px solid {cor}33;'
        'border-radius:6px;padding:5px 12px;font-size:11.5px;font-weight:600;'
        'text-decoration:none;">'
        '&#128279; Ver íntegra no Diário Oficial &mdash; {data}'
        '</a></div>'
    ).format(url=result["url_sumario"], bg=cfg["bg"], cor=cfg["cor"], data=data_fmt)


def gerar_html_diario(cfg, result):
    """Gera o bloco HTML completo de um Diário (Legislativo ou Executivo)."""
    header = (
        '\n  <div class="section-header">'
        '\n    <span class="section-icon">{icon}</span>'
        '\n    <span class="section-title">{titulo}</span>'
        '\n  </div>'
    ).format(icon=cfg["icon"], titulo=cfg["titulo"])

    items = result["items"]
    card  = _card_link(cfg, result)
    data_fmt = result["data_ref"].strftime("%d/%m/%Y")  # usado no corpo com itens

    data_fmt = result["data_ref"].strftime("%d/%m/%Y")
    if not items:
        # Sem itens: mensagem estilo DOE + link para consulta
        corpo = (
            '\n  <div class="section-body">'
            '\n    <p style="color:#5A6A85;font-style:italic;font-size:12px;padding:6px 0;">'
            'Não existem matérias para o dia {data}.</p>'
            '{card}'
            '\n  </div>'
        ).format(data=data_fmt, card=card)
        return header + corpo

    # Com itens: lista + botão
    linhas = ""
    for item in items:
        url_h = ""
        if item.get("url"):
            url_h = ' <a href="{}" target="_blank" style="color:{};font-size:10.5px;margin-left:6px;text-decoration:none;">&#128279;</a>'.format(item["url"], cfg["cor"])
        linhas += (
            '\n    <div class="agenda-item">'
            '\n      <div class="agenda-content">'
            '\n        <div class="event-name" style="font-size:12px;">{titulo}{url_h}</div>'
            '\n      </div>'
            '\n    </div>'
        ).format(titulo=item["titulo"][:120], url_h=url_h)

    corpo = (
        '\n  <div class="section-body">'
        '\n    <div class="sub-label" style="color:{cor};border-top:none;padding-top:0;">'
        'Publicações de {data}</div>'
        '{linhas}'
        '{card}'
        '\n  </div>'
    ).format(cor=cfg["cor"], data=result["data_ref"].strftime("%d/%m/%Y"), linhas=linhas, card=card)

    return header + corpo


# ── Funções de entrada ────────────────────────────────────────────────────────
def buscar_diario_legislativo(ref_date):
    return buscar_diario(DIARIO_LEG, ref_date)

def buscar_diario_executivo(ref_date):
    return buscar_diario(DIARIO_EXE, ref_date)

def gerar_html_diario_legislativo(result):
    return gerar_html_diario(DIARIO_LEG, result)

def gerar_html_diario_executivo(result):
    return gerar_html_diario(DIARIO_EXE, result)


if __name__ == "__main__":
    from datetime import date
    hoje = date.today()
    # DOE publica o dia útil anterior
    ref = hoje - timedelta(days=1)
    print("Buscando Diário Legislativo de {}...".format(ref.strftime("%d/%m/%Y")))
    r_leg = buscar_diario_legislativo(ref)
    print("  Itens encontrados: {}".format(len(r_leg["items"])))
    print("  Link: {}".format(r_leg["url_sumario"]))

    print("Buscando Diário Executivo de {}...".format(ref.strftime("%d/%m/%Y")))
    r_exe = buscar_diario_executivo(ref)
    print("  Itens encontrados: {}".format(len(r_exe["items"])))
    print("  Link: {}".format(r_exe["url_sumario"]))
