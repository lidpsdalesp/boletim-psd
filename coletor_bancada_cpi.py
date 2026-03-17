#!/usr/bin/env python3
"""
coletor_bancada_cpi.py
Busca membros das CPIs ativas via XML de Dados Abertos da ALESP.
Fonte: http://www.al.sp.gov.br/repositorioDados/processo_legislativo/comissoes_membros.xml
Fallback: membros_cpis.json local
Importa bancada PSD de coletor_bancada_psd.py
"""

import json
import os
import requests
import xml.etree.ElementTree as ET
from datetime import date

from coletor_bancada_psd import get_bancada_psd, atualizar_bancada

HEADERS       = {"User-Agent": "Mozilla/5.0 (compatible; BoletimPSD/1.0)"}
XML_URL       = "http://www.al.sp.gov.br/repositorioDados/processo_legislativo/comissoes_membros.xml"
MEMBROS_FILE  = "membros_cpis.json"

# IDs das CPIs ativas na 20a legislatura
CPIS_ATIVAS = {
    "questoes_impactantes":  "1000001276",
    "vazamento_dados":       "1000001274",
    "descarte_materiais":    "1000001275",
    "lixoes":                "1000001273",
}

# Mapa de palavras-chave do titulo do evento -> chave do dicionario
MAPA_CHAVE = [
    ("questoes impactantes",  "questoes_impactantes"),
    ("questao impactante",    "questoes_impactantes"),
    ("vazamento de dados",    "vazamento_dados"),
    ("descarte de materiais", "descarte_materiais"),
    ("lixoes",                "lixoes"),
    ("lixão",                 "lixoes"),
    ("lixao",                 "lixoes"),
]

# ── XML ───────────────────────────────────────────────────────────────────────

def _buscar_xml():
    """Le o XML de membros e retorna dict {id_comissao: [membros]}."""
    r = requests.get(XML_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()

    root = ET.fromstring(r.content)
    ids_alvo = set(CPIS_ATIVAS.values())
    resultado = {chave: [] for chave in CPIS_ATIVAS}

    id_para_chave = {v: k for k, v in CPIS_ATIVAS.items()}

    for m in root.findall("MembroComissao"):
        id_com = (m.findtext("IdComissao") or "").strip()
        if id_com not in ids_alvo:
            continue

        nome     = (m.findtext("NomeMembro") or "").strip()
        papel    = (m.findtext("Papel")      or "").strip()
        efetivo  = (m.findtext("Efetivo")    or "S").strip().upper()
        data_fim = (m.findtext("DataFim")    or "").strip()

        # Ignora membros que ja saíram
        if data_fim:
            continue

        tipo = "Titular" if efetivo == "S" else "Suplente"
        chave = id_para_chave[id_com]

        resultado[chave].append({
            "nome":    nome,
            "partido": "",       # XML de membros nao traz partido; sera cruzado se necessario
            "tipo":    tipo,
            "papel":   papel,
        })

    return resultado


# ── Persistencia ──────────────────────────────────────────────────────────────

def _carregar_json():
    if os.path.exists(MEMBROS_FILE):
        try:
            with open(MEMBROS_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _salvar_json(dados):
    payload = {
        "atualizado_em": date.today().isoformat(),
        "fonte": "xml_dados_abertos",
        "cpis": dados,
    }
    with open(MEMBROS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


# ── Interface publica ─────────────────────────────────────────────────────────

def atualizar_membros_cpis():
    """
    Busca membros das CPIs via XML da ALESP.
    Salva em membros_cpis.json e retorna dict {chave: [membros]}.
    """
    print("  [membros_cpi] Verificando membros das CPIs...")

    try:
        dados = _buscar_xml()
        total = sum(len(v) for v in dados.values())
        print("  [membros_cpi] XML OK — {} membros encontrados nas CPIs ativas.".format(total))
        _salvar_json(dados)
        return dados
    except Exception as e:
        print("  [membros_cpi] AVISO: Erro ao acessar XML: {}".format(e))
        print("  [membros_cpi] Usando membros_cpis.json local (fallback).")
        salvo = _carregar_json()
        return salvo.get("cpis", {})


def get_membros_cpi(chave):
    """Retorna membros de uma CPI do JSON salvo."""
    dados = _carregar_json()
    cpis  = dados.get("cpis", dados)   # compatibilidade com formato antigo
    return cpis.get(chave, [])


def get_membros_psd_cpi(chave):
    """Retorna apenas membros da bancada PSD em uma CPI."""
    import unicodedata

    def norm(t):
        return "".join(
            c for c in unicodedata.normalize("NFD", t.lower())
            if unicodedata.category(c) != "Mn"
        )

    bancada = get_bancada_psd()
    membros = get_membros_cpi(chave)
    return [
        m for m in membros
        if any(norm(dep) in norm(m["nome"]) for dep in bancada)
    ]


def chave_por_titulo(titulo):
    """Mapeia titulo de evento de CPI para chave do dicionario."""
    import unicodedata

    def norm(t):
        return "".join(
            c for c in unicodedata.normalize("NFD", t.lower())
            if unicodedata.category(c) != "Mn"
        )

    t = norm(titulo)
    for kw, chave in MAPA_CHAVE:
        if norm(kw) in t:
            return chave
    return None


if __name__ == "__main__":
    # Atualiza bancada PSD
    deputados, entradas, saidas = atualizar_bancada()
    print("\nBancada PSD ({} dep.): {}".format(len(deputados), ", ".join(deputados)))

    # Atualiza membros das CPIs
    dados = atualizar_membros_cpis()

    print()
    for chave, membros in dados.items():
        psd = [m for m in membros if any(d.lower() in m["nome"].lower() for d in deputados)]
        print("[{}] {} membros total | {} PSD".format(chave, len(membros), len(psd)))
        for m in membros:
            flag = " *** PSD ***" if m in psd else ""
            print("   {} ({}){}".format(m["nome"], m["tipo"], flag))
