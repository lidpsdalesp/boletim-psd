#!/usr/bin/env python3
"""
coletor_proposituras.py
Busca a Pauta mais recente da ALESP e extrai as proposituras.
Fonte: https://www.al.sp.gov.br/alesp/pauta/
Estratégia:
  1. Busca a lista de pautas (HTML)
  2. Identifica a entrada mais recente (link PDF ou página HTML)
  3. Se PDF: usa pdfplumber para extrair texto
  4. Se HTML: scraping direto
  5. Parseia número, tipo, autor e ementa de cada propositura
"""

import re
import requests
from bs4 import BeautifulSoup
from datetime import date

try:
    import pdfplumber
    TEM_PDFPLUMBER = True
except ImportError:
    TEM_PDFPLUMBER = False

ALESP_BASE    = "https://www.al.sp.gov.br"
PAUTA_URL     = "https://www.al.sp.gov.br/alesp/pauta/"
HEADERS       = {"User-Agent": "Mozilla/5.0 (compatible; BoletimPSD/1.0)"}

# Deputados do PSD (mantém sincronizado com coletor_agenda_alesp.py)
PSD_NOMES = [
    "Oseias de Madureira","Rogério Santos","Marta Costa","Marcio Nakashima",
    "Maria Lucia Amary","Maria Lúcia Amary","Cerinha","Emidio de Souza",
    "Emídio de Souza","Ana Lima","Fernando Marangoni","Solange Freitas",
    "Jonas Donizette","Paulo Correia","Sargento Neto",
]

TIPOS_BADGE = {
    "PL":  ("EBF2FF", "1A3A9C", "BFD0F7"),
    "PLC": ("EBF2FF", "1A3A9C", "BFD0F7"),
    "PLO": ("EBF2FF", "1A3A9C", "BFD0F7"),
    "PDL": ("F5F0FF", "6B21A8", "D8B4FE"),
    "Moc": ("F0FFF4", "276749", "9AE6B4"),
    "Res": ("FEF9EE", "92400E", "FCD34D"),
    "Ind": ("F0F9FF", "0369A1", "BAE6FD"),
    "Req": ("FFF7ED", "C05621", "FDBA74"),
    "Dec": ("FFF1F2", "9F1239", "FCA5A5"),
}

def _badge_tipo(tipo_abrev):
    key = tipo_abrev[:3]
    bg, cor, borda = TIPOS_BADGE.get(key, ("F3F4F6", "374151", "D1D5DB"))
    return (
        '<span style="background:#{bg};color:#{cor};border:1px solid #{borda};'
        'border-radius:4px;padding:1px 7px;font-size:10.5px;font-weight:700;">'
        '{tipo}</span>'
    ).format(bg=bg, cor=cor, borda=borda, tipo=tipo_abrev)


def _is_psd(autor):
    autor_l = autor.lower()
    return any(p.lower() in autor_l for p in PSD_NOMES)


def _parsear_linha_prop(linha):
    """
    Tenta extrair tipo, número e autor de uma linha de texto da pauta.
    Exemplos de formatos:
      'PL nº 190/2026 - Dep. Marta Costa - Medicamentos Supressores de Apetite...'
      'Moção nº 76/2026 - Dep. Marcio Nakashima - Aplauso ao Grupo Boticário...'
    """
    linha = linha.strip()
    if not linha:
        return None

    m = re.match(
        r'^(?P<tipo>\w[\w\s]{0,12}?)\s+n[ºo°]?\.?\s*(?P<num>[\d]+/\d{4})'
        r'(?:\s*[-–]\s*(?P<rest>.+))?$',
        linha, re.IGNORECASE
    )
    if not m:
        return None

    tipo  = m.group("tipo").strip()
    num   = m.group("num")
    rest  = (m.group("rest") or "").strip()

    # Separa autor e ementa (delimitados por " - " ou " – ")
    partes = re.split(r"\s*[-–]\s*", rest, maxsplit=1)
    autor  = partes[0].strip() if partes else ""
    ementa = partes[1].strip() if len(partes) > 1 else ""

    return {
        "tipo":   tipo,
        "numero": "{} Nº {}" .format(tipo, num),
        "autor":  autor,
        "ementa": ementa,
        "is_psd": _is_psd(autor),
    }


def _buscar_link_pdf(soup):
    """Retorna o href do PDF da pauta mais recente na lista."""
    for a in soup.find_all("a", href=True):
        href = a["href"]
        txt  = a.get_text(strip=True)
        # Links que apontam para PDF de pauta ou para detalhe de pauta
        if re.search(r"pauta", href, re.I) and href.endswith(".pdf"):
            return href if href.startswith("http") else ALESP_BASE + href
        if re.search(r"pauta", href, re.I) and "idSessao" in href:
            return href if href.startswith("http") else ALESP_BASE + href
    # Fallback: pega o primeiro link com "pauta" no href
    for a in soup.find_all("a", href=True):
        if "pauta" in a["href"].lower() and a["href"] != PAUTA_URL:
            href = a["href"]
            return href if href.startswith("http") else ALESP_BASE + href
    return None


def _extrair_de_pdf(pdf_bytes):
    """Extrai proposituras de um PDF de pauta usando pdfplumber."""
    if not TEM_PDFPLUMBER:
        return []
    import io
    props = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            for linha in (page.extract_text() or "").splitlines():
                p = _parsear_linha_prop(linha)
                if p:
                    props.append(p)
    return props


def _extrair_de_html(soup):
    """Extrai proposituras de uma página HTML de pauta da ALESP."""
    props = []
    # Estratégia A: linhas em <li> ou <p> com padrão de número
    for tag in soup.find_all(["li", "p", "tr", "td"]):
        texto = tag.get_text(" ", strip=True)
        p = _parsear_linha_prop(texto)
        if p:
            # Evita duplicata
            if not any(x["numero"] == p["numero"] for x in props):
                props.append(p)
    return props


def buscar_proposituras():
    """
    Fluxo principal: busca lista → segue link → parseia proposituras.
    Retorna lista de dicts com: tipo, numero, autor, ementa, is_psd.
    """
    resp = requests.get(PAUTA_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    link = _buscar_link_pdf(soup)
    if not link:
        return []

    resp2 = requests.get(link, headers=HEADERS, timeout=20)
    resp2.raise_for_status()

    content_type = resp2.headers.get("content-type", "")

    if "pdf" in content_type or link.endswith(".pdf"):
        props = _extrair_de_pdf(resp2.content)
    else:
        soup2 = BeautifulSoup(resp2.text, "html.parser")
        props = _extrair_de_html(soup2)

    return props


def gerar_html_proposituras(props, sessao_label="Sessão"):
    """Gera o bloco HTML da seção Proposituras em Pauta."""
    PRAZO_HTML = (
        '<span style="background:#FFF3CD;color:#856404;border:1px solid #FFECB5;'
        'border-radius:4px;padding:1px 6px;font-size:10px;font-weight:600;'
        'margin-left:6px;">&#9203; 5 sessões</span>'
    )

    header = (
        '\n  <div class="section-header">'
        '\n    <span class="section-icon">&#128196;</span>'
        '\n    <span class="section-title">Proposituras em Pauta &mdash; '
        '5 Sessões para Emendas / Coautoria</span>'
        '\n  </div>'
    )

    if not props:
        return header + (
            '\n  <div class="section-body">'
            '\n    <p style="color:#5A6A85;font-style:italic;font-size:12.5px;padding:6px 0">'
            'Pauta não divulgada ou não disponível para a data do boletim.</p>'
            '\n  </div>'
        )

    corpo = '\n    <div class="sub-label" style="color:#1A3A9C;border-top:none;padding-top:0;">&#128196; {}</div>'.format(sessao_label)

    for ev in props:
        badge  = _badge_tipo(ev["tipo"])
        psd_b  = '<span class="badge badge-psd">PSD</span>' if ev["is_psd"] else ""

        if ev["is_psd"]:
            item_s = ' style="background:linear-gradient(90deg,#FFFBEA 0%,#FFFFF8 100%);border-left:3px solid #F5C800;margin:0 -20px;padding:10px 20px;"'
        else:
            item_s = ""

        autor_h = ""
        if ev["autor"]:
            autor_h = '<span>&#128100; {}</span>'.format(ev["autor"])
            if psd_b:
                autor_h += " " + psd_b

        ementa_h = ""
        if ev["ementa"]:
            ementa_h = '<div style="font-size:11.5px;color:#4A5A75;margin-top:3px;">{}</div>'.format(
                ev["ementa"][:160] + ("..." if len(ev["ementa"]) > 160 else "")
            )

        corpo += (
            '\n    <div class="agenda-item"{item_s}>'
            '\n      <div class="agenda-time" style="min-width:48px;font-size:11px;'
            'padding:4px 6px;text-align:center;">{badge}</div>'
            '\n      <div class="agenda-content">'
            '\n        <div class="event-name">{num} {prazo}</div>'
            '\n        <div class="event-meta">{autor_h}</div>'
            '\n        {ementa_h}'
            '\n      </div>'
            '\n    </div>'
        ).format(
            item_s=item_s,
            badge=badge,
            num=ev["numero"],
            prazo=PRAZO_HTML,
            autor_h=autor_h,
            ementa_h=ementa_h,
        )

    return header + '\n  <div class="section-body">' + corpo + '\n  </div>'


if __name__ == "__main__":
    print("Buscando proposituras em pauta...")
    props = buscar_proposituras()
    print("Encontradas: {}".format(len(props)))
    for p in props:
        psd = " [PSD]" if p["is_psd"] else ""
        print("  {:8s} {} — {}{}".format(p["tipo"], p["numero"], p["autor"][:40], psd))
