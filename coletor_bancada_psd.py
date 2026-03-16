#!/usr/bin/env python3
"""
coletor_bancada_psd.py
Verifica diariamente a lista de Deputados do PSD na ALESP.
Fonte: https://www.al.sp.gov.br/repositorioDados/deputados/deputados.xml
Fallback: lista salva em bancada_psd.json
"""

import json
import os
import requests
import xml.etree.ElementTree as ET
from datetime import date

HEADERS      = {"User-Agent": "Mozilla/5.0 (compatible; BoletimPSD/1.0)"}
BANCADA_FILE = "bancada_psd.json"
XML_URL      = "https://www.al.sp.gov.br/repositorioDados/deputados/deputados.xml"
PARTIDO_ALVO = "PSD"

# Situações que indicam mandato ativo
SITUACOES_ATIVAS = {"EXE", "LIC", ""}

# ── XML de Dados Abertos ──────────────────────────────────────────────────────
# Estrutura (documentada em deputados.pdf):
# <Deputados>
#   <Deputado>
#     <NomeParlamentar>...</NomeParlamentar>
#     <Partido>PSD</Partido>
#     <Situacao>EXE</Situacao>   ← EXE = em exercício, LIC = licenciado
#   </Deputado>
# </Deputados>

def _buscar_xml():
    """Lê o XML e retorna lista de nomes dos deputados PSD em exercício."""
    r = requests.get(XML_URL, headers=HEADERS, timeout=15)
    r.raise_for_status()

    root  = ET.fromstring(r.content)
    nomes = []

    for dep in root.findall("Deputado"):
        partido  = (dep.findtext("Partido")        or "").strip().upper()
        situacao = (dep.findtext("Situacao")        or "").strip().upper()
        nome     = (dep.findtext("NomeParlamentar") or "").strip()

        if partido == PARTIDO_ALVO and situacao in SITUACOES_ATIVAS and nome:
            nomes.append(nome)

    return nomes

# ── Persistência ──────────────────────────────────────────────────────────────

def _carregar_json():
    if os.path.exists(BANCADA_FILE):
        try:
            with open(BANCADA_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"deputados": [], "atualizado_em": "", "fonte": ""}

def _salvar_json(deputados, fonte):
    dados = {
        "deputados":     sorted(deputados),
        "atualizado_em": date.today().isoformat(),
        "total":         len(deputados),
        "fonte":         fonte,
    }
    with open(BANCADA_FILE, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

# ── Detecção de mudanças ──────────────────────────────────────────────────────

def _detectar_mudancas(anterior, atual):
    entradas = sorted(set(atual)    - set(anterior))
    saidas   = sorted(set(anterior) - set(atual))
    return entradas, saidas

# ── Interface pública ─────────────────────────────────────────────────────────

def atualizar_bancada():
    """
    Verifica a lista de deputados PSD via XML da ALESP.
    Salva em bancada_psd.json e retorna (lista_atual, entradas, saidas).
    """
    print("  [bancada] Verificando composição da bancada PSD...")

    dados_anteriores = _carregar_json()
    anterior         = dados_anteriores.get("deputados", [])

    try:
        nomes = _buscar_xml()
        fonte = "xml_dados_abertos"
        print(f"  [bancada] XML OK — {len(nomes)} deputado(s) PSD encontrado(s).")
    except Exception as e:
        print(f"  [bancada] ⚠️  Erro ao acessar XML: {e}")
        print("  [bancada] Usando lista salva anteriormente (fallback).")
        nomes = anterior
        fonte = "fallback"

    entradas, saidas = _detectar_mudancas(anterior, nomes)

    if entradas or saidas:
        print("  [bancada] 🔔 MUDANÇAS DETECTADAS!")
        for dep in entradas:
            print(f"    ✅ Entrou: {dep}")
        for dep in saidas:
            print(f"    ❌ Saiu:   {dep}")
    else:
        print(f"  [bancada] ✅ Bancada estável — {len(nomes)} deputado(s).")

    if sorted(nomes) != sorted(anterior) or not os.path.exists(BANCADA_FILE):
        _salvar_json(nomes, fonte)

    return nomes, entradas, saidas

def get_bancada_psd():
    """Retorna a lista atual de deputados PSD (do JSON salvo)."""
    dados = _carregar_json()
    return dados.get("deputados", [])


if __name__ == "__main__":
    deputados, entradas, saidas = atualizar_bancada()
    print(f"\nBancada PSD atual ({len(deputados)} deputados):")
    for d in sorted(deputados):
        print(f"  • {d}")
