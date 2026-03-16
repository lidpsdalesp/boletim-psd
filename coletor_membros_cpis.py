#!/usr/bin/env python3
"""
coletor_membros_cpis.py
Scrapa as CPIs ativas da ALESP e identifica membros PSD.
Usa APENAS dados primários do site da ALESP.
"""

import json, re, requests
from bs4 import BeautifulSoup

LISTA_URL        = "https://www.al.sp.gov.br/comissao/comissoes-parlamentares-de-inquerito"
BASE_CPI_URL     = "https://www.al.sp.gov.br/comissao/cpi/"
HEADERS          = {"User-Agent": "Mozilla/5.0"}
BANCADA_FILE     = "bancada_psd.json"
OUTPUT_FILE      = "cpis_membros.json"

def _carregar_bancada():
    try:
        with open(BANCADA_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return {d["nome"].strip().lower() for d in data}
    except Exception as e:
        print(f"  [AVISO] bancada_psd.json: {e}")
        return set()

def _buscar_cpis_ativas():
    """Retorna lista de {nome, id} de CPIs SEM data de encerramento."""
    resp = requests.get(LISTA_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    cpis = []
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue
        link = tds[0].find("a", href=True)
        if not link:
            continue
        href = link["href"]
        m = re.search(r"idComissao=(\d+)", href)
        if not m:
            continue
        nome = link.get_text(strip=True)
        if not nome.upper().startswith("CPI"):
            continue
        encerramento = tds[4].get_text(strip=True)
        if encerramento:          # já encerrada
            continue
        cpis.append({"nome": nome, "id": m.group(1),
                     "url": f"{BASE_CPI_URL}?idComissao={m.group(1)}"})
    return cpis

def _scrapa_membros(url, bancada_psd):
    """
    Lê a aba MEMBROS da página de CPI.
    Estrutura real: seções PRESIDENTE / VICE-PRESIDENTE / EFETIVOS / SUPLENTES
    cada uma seguida de links <a> com nome do deputado + texto do partido.
    """
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    membros  = []
    psd_list = []

    # Cargo atual detectado por cabeçalhos de seção
    CARGOS = {
        "presidente":      "Presidente",
        "vice-presidente": "Vice-Presidente",
        "efetivo":         "Efetivo",
        "suplente":        "Suplente",
    }
    cargo_atual = "Efetivo"

    # Percorre todos os elementos em ordem
    for tag in soup.find_all(["h2","h3","h4","strong","b","a","td"]):
        texto = tag.get_text(strip=True)

        # Detecta mudança de cargo pela seção
        texto_lower = texto.lower()
        for chave, valor in CARGOS.items():
            if texto_lower.startswith(chave):
                cargo_atual = valor
                break

        # Links para páginas de deputado = membro
        if tag.name == "a" and "deputado" in tag.get("href", ""):
            nome = texto.strip()
            if not nome:
                continue

            # Partido: próximo texto irmão ou próxima td
            partido = ""
            nxt = tag.find_next_sibling(string=True)
            if nxt:
                partido = nxt.strip()
            if not partido:
                nxt_tag = tag.find_next_sibling()
                if nxt_tag:
                    partido = nxt_tag.get_text(strip=True)
            # Limpa partido
            partido = partido.strip("\n\r\t –-").strip()

            # Evita duplicatas
            if any(m["nome"] == nome and m["cargo"] == cargo_atual for m in membros):
                continue

            is_psd = nome.lower() in bancada_psd or "PSD" in partido.upper()
            membros.append({"nome": nome, "partido": partido, "cargo": cargo_atual})
            if is_psd:
                psd_list.append({"nome": nome, "cargo": cargo_atual, "partido": "PSD"})

    return membros, psd_list

def main():
    bancada_psd = _carregar_bancada()
    print(f"  [cpis] {len(bancada_psd)} deputados PSD carregados")

    cpis = _buscar_cpis_ativas()
    print(f"  [cpis] {len(cpis)} CPIs ativas encontradas")

    anterior = {}
    try:
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            anterior = json.load(f)
    except FileNotFoundError:
        pass

    resultado = {}
    mudancas  = []

    for cpi in cpis:
        nome = cpi["nome"]
        try:
            membros, psd = _scrapa_membros(cpi["url"], bancada_psd)
        except Exception as e:
            print(f"    ⚠️  {nome} — ERRO: {e}")
            continue

        resultado[nome] = {"nome": nome, "url": cpi["url"],
                           "membros": membros, "psd": psd}

        tag = " | PSD: " + ", ".join(
            f"{p['nome']} ({p['cargo']})" for p in psd
        ) if psd else ""
        print(f"    ✅ {nome} — {len(membros)} membros{tag}")

        ant_nomes = {m["nome"] for m in anterior.get(nome, {}).get("membros", [])}
        for m in membros:
            if m["nome"] not in ant_nomes:
                mudancas.append(f"    ✅ {nome} Entrou: {m['nome']} ({m['cargo']})")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    if mudancas:
        print(f"\n  [cpis] 🔔 {len(mudancas)} mudança(s) detectada(s):")
        for m in mudancas[:20]:
            print(m)

    print("\n=== RESUMO PSD POR CPI ===")
    for nome, dados in resultado.items():
        if dados["psd"]:
            print(f"\n  {nome}")
            for p in dados["psd"]:
                print(f"    • {p['nome']} | {p['cargo']}")

if __name__ == "__main__":
    main()
