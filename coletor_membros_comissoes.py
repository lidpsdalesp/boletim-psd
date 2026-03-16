#!/usr/bin/env python3
"""
coletor_membros_comissoes.py
Verifica diariamente os membros das Comissões Permanentes da ALESP.
Fonte: https://www.al.sp.gov.br/comissao/?idComissao=XXXXX
- Dados embutidos no HTML (server-side), dentro de #painelMembros
- Cada cargo é uma <table> separada com o título no <thead>
- Headers de browser real para bypass do Radware Bot Manager
"""

import json
import os
import re
import time
import requests
from bs4 import BeautifulSoup
from datetime import date

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
    "Referer":         "https://www.al.sp.gov.br/comissao/comissoes-permanentes/",
}

BASE_URL = "https://www.al.sp.gov.br/comissao/?idComissao={}"
OUT_FILE = "comissoes_membros.json"

# Comissões Permanentes — IDs confirmados do comissoes.xml (20ª Legislatura)
COMISSOES_PERMANENTES = [
    {"id": "12452", "sigla": "CAPRT", "nome": "Administração Pública e Relações do Trabalho"},
    {"id": "12448", "sigla": "CAD",   "nome": "Assuntos Desportivos"},
    {"id": "12449", "sigla": "CAMM",  "nome": "Assuntos Metropolitanos e Municipais"},
    {"id": "12454", "sigla": "CAE",   "nome": "Atividades Econômicas"},
    {"id": "12456", "sigla": "CCTI",  "nome": "Ciência, Tecnologia, Inovação e Informação"},
    {"id": "12444", "sigla": "CCJR",  "nome": "Constituição, Justiça e Redação"},
    {"id": "12455", "sigla": "CDD",   "nome": "Defesa dos Direitos da Pessoa Humana"},
    {"id": "1000001015", "sigla": "CDDPD", "nome": "Defesa dos Direitos das Pessoas com Deficiência"},
    {"id": "1000000128", "sigla": "CDDC",  "nome": "Defesa dos Direitos do Consumidor"},
    {"id": "1000000297", "sigla": "CDDM",  "nome": "Defesa dos Direitos das Mulheres"},
    {"id": "12447", "sigla": "CEC",   "nome": "Educação e Cultura"},
    {"id": "12445", "sigla": "CFOP",  "nome": "Finanças, Orçamento e Planejamento"},
    {"id": "8509",  "sigla": "CFC",   "nome": "Fiscalização e Controle"},
    {"id": "1000001021", "sigla": "CHDRU", "nome": "Habitação, Desenvolvimento e Reforma Urbana"},
    {"id": "12450", "sigla": "CI",    "nome": "Infraestrutura"},
    {"id": "12453", "sigla": "CMADS", "nome": "Meio Ambiente e Desenvolvimento Sustentável"},
    {"id": "1000000596", "sigla": "CRI",   "nome": "Relações Internacionais"},
    {"id": "12446", "sigla": "CS",    "nome": "Saúde"},
    {"id": "12451", "sigla": "CSPAP", "nome": "Segurança Pública e Assuntos Penitenciários"},
    {"id": "8520",  "sigla": "CTC",   "nome": "Transportes e Comunicações"},
    {"id": "1000001016", "sigla": "CT",    "nome": "Turismo"},
    {"id": "8521",  "sigla": "CEDP",  "nome": "Conselho de Ética e Decoro Parlamentar"},
]

# ── Parser do #painelMembros ──────────────────────────────────────────────────
# Estrutura real (confirmada via código-fonte):
#   <div id="painelMembros">
#     <table>                          ← uma table por cargo
#       <thead><tr><th>PRESIDENTE</th></tr></thead>
#       <tbody>
#         <tr><td><a>Nome</a></td><td>PARTIDO</td></tr>
#       </tbody>
#     </table>
#     <table>
#       <thead><tr><th>VICE-PRESIDENTE</th></tr></thead>
#       ...
#     </table>
#     <table>
#       <thead><tr><th>EFETIVOS Total de Vagas = N</th></tr></thead>
#       ...
#     </table>
#     <table>
#       <thead><tr><th>SUPLENTES Total de Vagas = N</th></tr></thead>
#       ...
#     </table>
#   </div>

def _resolver_cargo(titulo):
    t = titulo.upper()
    if "VICE" in t:            return "Vice-Presidente"
    if "PRESIDENTE" in t:      return "Presidente"
    if "EFETIVO" in t:         return "Efetivo"
    if "SUPLENTE" in t:        return "Suplente"
    return titulo.strip()

def _scraping_membros(id_comissao):
    url = BASE_URL.format(id_comissao)
    r   = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()

    soup  = BeautifulSoup(r.text, "html.parser")
    painel = soup.find("div", id="painelMembros")
    if not painel:
        return []

    membros = []
    for tabela in painel.find_all("table"):
        # Título da seção está no <thead>
        thead = tabela.find("thead")
        if not thead:
            continue
        cargo = _resolver_cargo(thead.get_text(" ", strip=True))

        # Membros nas linhas do <tbody>
        tbody = tabela.find("tbody")
        if not tbody:
            continue
        for tr in tbody.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue
            nome    = tds[0].get_text(strip=True)
            partido = tds[1].get_text(strip=True)
            if len(nome) > 3 and "---" not in nome:
                membros.append({
                    "nome":    nome,
                    "partido": partido,
                    "cargo":   cargo,
                })

    return membros

# ── Persistência ──────────────────────────────────────────────────────────────

def _carregar_json():
    if os.path.exists(OUT_FILE):
        try:
            with open(OUT_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"comissoes": {}}

def _salvar_json(comissoes):
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "atualizado_em": date.today().isoformat(),
            "comissoes": comissoes
        }, f, ensure_ascii=False, indent=2)

# ── Detecção de mudanças ──────────────────────────────────────────────────────

def _chave(m):
    return f"{m['nome']}|{m['cargo']}"

def _detectar_mudancas(anterior, atual):
    mudancas = {}
    for sigla in set(anterior) | set(atual):
        val_ant = anterior.get(sigla, {})
        val_atu = atual.get(sigla, {})
        # Compatível com JSON antigo (lista) e novo (dict com chave "membros")
        lista_ant = val_ant if isinstance(val_ant, list) else val_ant.get("membros", [])
        lista_atu = val_atu if isinstance(val_atu, list) else val_atu.get("membros", [])
        ant = {_chave(m): m for m in lista_ant}
        atu = {_chave(m): m for m in lista_atu}
        entradas = [atu[k] for k in set(atu) - set(ant)]
        saidas   = [ant[k] for k in set(ant) - set(atu)]
        if entradas or saidas:
            mudancas[sigla] = {"entradas": entradas, "saidas": saidas}
    return mudancas

# ── Interface pública ─────────────────────────────────────────────────────────

def atualizar_membros_comissoes(bancada_psd=None):
    """
    Verifica membros de todas as comissões permanentes.
    bancada_psd: lista de nomes do PSD para cruzar.
    Retorna (comissoes_dict, mudancas_dict).
    """
    bancada_psd  = [b.lower() for b in (bancada_psd or [])]
    dados_ant    = _carregar_json()
    anterior     = dados_ant.get("comissoes", {})
    atual        = {}
    erros        = []

    print(f"  [comissoes] Verificando {len(COMISSOES_PERMANENTES)} comissões permanentes...")

    for c in COMISSOES_PERMANENTES:
        time.sleep(1)
        try:
            membros = _scraping_membros(c["id"])
            psd     = [m for m in membros
                       if any(dep in m["nome"].lower() for dep in bancada_psd)]
            atual[c["sigla"]] = {
                "id":      c["id"],
                "nome":    c["nome"],
                "membros": membros,
                "psd":     psd,
                "total":   len(membros),
            }
            status = f"✅ {c['sigla']} — {len(membros)} membros"
            if psd:
                status += f" | PSD: {', '.join(m['nome'] + ' (' + m['cargo'] + ')' for m in psd)}"
            print(f"    {status}")
        except Exception as e:
            erros.append(c["sigla"])
            print(f"    ⚠️  {c['sigla']} — erro: {e}")
            if c["sigla"] in anterior:
                atual[c["sigla"]] = anterior[c["sigla"]]

    mudancas = _detectar_mudancas(anterior, atual)

    if mudancas:
        print(f"\n  [comissoes] 🔔 MUDANÇAS em {len(mudancas)} comissão(ões):")
        for sigla, m in mudancas.items():
            for dep in m["entradas"]:
                print(f"    ✅ {sigla} Entrou: {dep['nome']} ({dep['cargo']})")
            for dep in m["saidas"]:
                print(f"    ❌ {sigla} Saiu:   {dep['nome']} ({dep['cargo']})")
    else:
        print(f"\n  [comissoes] ✅ Sem mudanças na composição das comissões.")

    if erros:
        print(f"  [comissoes] ⚠️  Erros em: {', '.join(erros)}")

    _salvar_json(atual)
    return atual, mudancas


def get_psd_por_comissao():
    """Retorna dict sigla → lista de membros PSD com cargo. Usa o JSON salvo."""
    dados = _carregar_json()
    return {
        sigla: info["psd"]
        for sigla, info in dados.get("comissoes", {}).items()
        if info.get("psd")
    }


if __name__ == "__main__":
    from coletor_bancada_psd import get_bancada_psd
    bancada  = get_bancada_psd()
    comissoes, mudancas = atualizar_membros_comissoes(bancada_psd=bancada)

    print(f"\n=== RESUMO PSD POR COMISSÃO ===")
    psd_map = get_psd_por_comissao()
    if psd_map:
        for sigla, membros in sorted(psd_map.items()):
            nome_com = comissoes.get(sigla, {}).get("nome", sigla)
            print(f"\n  {sigla} — {nome_com}")
            for m in membros:
                print(f"    • {m['nome']} | {m['cargo']} | {m['partido']}")
    else:
        print("  Nenhum deputado PSD encontrado nas comissões.")
