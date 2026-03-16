#!/usr/bin/env python3
"""
coletor_comissoes.py
Extrai Convocacoes para Comissoes a partir dos eventos ja coletados da Agenda.
Cruza com comissoes_membros.json para destacar deputados do PSD.
"""

import json
import os
import re

COMISSAO_KEYWORDS = [
    "Reuniao da Comissao", "Reunião da Comissão",
    "Reuniao do Conselho",  "Reunião do Conselho",
    "Reuniao da Frente",    "Reunião da Frente",
    "Audiencia Publica",    "Sessao Tematica",      "Seminario",            "Forum",            ]
NAO_COMISSAO = ["Montagem", "Desmontagem", "Apoio ao Evento"]

MEMBROS_FILE = "comissoes_membros.json"

# ── Helpers ───────────────────────────────────────────────────────────────────

def is_comissao(ev):
    titulo = ev.get("titulo", "")
    # CPIs ficam na seção própria — excluir daqui
    if any(k in titulo.lower() for k in ["cpi", "cpmi"]):
        return False
    if any(nc.lower() in titulo.lower() for nc in NAO_COMISSAO):
        return False
    return any(kw.lower() in titulo.lower() for kw in COMISSAO_KEYWORDS)

def extrair_comissoes(dias):
    resultado = []
    for d in dias:
        comissoes = [ev for ev in d.get("eventos", []) if is_comissao(ev)]
        if comissoes:
            resultado.append({
                "label":  d["label"],
                "data":   d["data"],
                "estilo": d["estilo"],
                "eventos": comissoes,
            })
    return resultado

def _carregar_membros():
    """
    Carrega comissoes_membros.json.
    Retorna lista de dicts: [{sigla, nome, palavras_chave, psd}]
    para cruzamento por nome completo (os títulos não contêm siglas).
    """
    if not os.path.exists(MEMBROS_FILE):
        return []
    try:
        with open(MEMBROS_FILE, encoding="utf-8") as f:
            dados = json.load(f)
        resultado = []
        for sigla, info in dados.get("comissoes", {}).items():
            nome = info.get("nome", "")
            # Palavras significativas do nome (>3 letras) para busca parcial
            palavras = [p.lower().strip(".,") for p in nome.split() if len(p) > 3]
            resultado.append({
                "sigla":    sigla,
                "nome":     nome,
                "palavras": palavras,
                "psd":      info.get("psd", []),
            })
        return resultado
    except Exception:
        return []

def _sigla_do_titulo(titulo):
    """Tenta extrair a sigla da comissão do título do evento."""
    t = titulo.upper()
    # Padrão: "Reunião da Comissão de XXX - SIGLA" ou "Reunião da CCJR"
    m = re.search(r'\b([A-Z]{2,6})\b', titulo)
    return m.group(1) if m else ""

def _psd_na_comissao(titulo, comissoes_list):
    """
    Encontra membros PSD da comissão mencionada no título do evento.
    Busca primeiro por sigla, depois por palavras do nome completo.
    """
    if not comissoes_list:
        return "", []
    titulo_u = titulo.upper()
    titulo_l = titulo.lower()

    # 1. Busca exata por sigla no título
    for c in comissoes_list:
        if c["sigla"] in titulo_u and c["psd"]:
            return c["sigla"], c["psd"]

    # 2. Busca por palavras-chave do nome completo (mínimo 3 palavras em comum)
    melhor_sigla, melhor_membros, melhor_score = "", [], 0
    for c in comissoes_list:
        score = sum(1 for p in c["palavras"] if p in titulo_l)
        if score >= 2 and score > melhor_score:
            melhor_score = score
            melhor_sigla = c["sigla"]
            melhor_membros = c["psd"]

    return melhor_sigla, melhor_membros

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
        'font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px;'
        'letter-spacing:0.3px;text-transform:uppercase;">{txt}</span>'
    ).format(bg=bg, cor=cor, borda=borda, txt=txt)

def _badge_cargo(cargo):
    """Badge colorido por cargo do deputado PSD."""
    c = cargo.lower()
    if "presidente" in c and "vice" not in c:
        bg, cor = "#1A3A9C", "#FFFFFF"       # azul escuro
    elif "vice" in c:
        bg, cor = "#2B6CB0", "#FFFFFF"       # azul médio
    elif "efetivo" in c:
        bg, cor = "#F5C800", "#1A3A9C"       # amarelo PSD
    else:
        bg, cor = "#F0F4F9", "#5A6A85"       # cinza (suplente)
    return (
        '<span style="background:{bg};color:{cor};font-size:10px;font-weight:700;'
        'padding:2px 8px;border-radius:10px;white-space:nowrap;">{cargo}</span>'
    ).format(bg=bg, cor=cor, cargo=cargo)

def _html_membros_psd(membros):
    """Gera bloco HTML com os membros PSD da comissão."""
    if not membros:
        return ""
    itens = ""
    # Ordena: Presidente > Vice > Efetivo > Suplente
    ordem = {"Presidente": 0, "Vice-Presidente": 1, "Efetivo": 2, "Suplente": 3}
    membros_ord = sorted(membros, key=lambda m: ordem.get(m.get("cargo", ""), 9))
    for m in membros_ord:
        itens += (
            '<div style="display:flex;align-items:center;gap:8px;'
            'padding:3px 0;font-size:12px;">'
            '<span style="font-size:13px;">👤</span>'
            '<span style="font-weight:600;color:#1A1A2E;">{nome}</span>'
            '{badge}'
            '</div>'
        ).format(nome=m["nome"], badge=_badge_cargo(m.get("cargo", "")))
    return (
        '<div style="margin-top:8px;padding:8px 10px;'
        'background:rgba(245,200,0,0.08);border-radius:6px;'
        'border-left:3px solid #F5C800;">'
        '<div style="font-size:10px;font-weight:700;color:#C8960A;'
        'text-transform:uppercase;letter-spacing:0.5px;margin-bottom:4px;">'
        '⭐ PSD na Comissão</div>'
        '{itens}'
        '</div>'
    ).format(itens=itens)

# ── Geração do HTML ───────────────────────────────────────────────────────────

def gerar_html_comissoes(dias_comissoes):
    """Gera o bloco HTML completo da seção Convocações para Comissões."""
    membros_psd = _carregar_membros()

    header = (
        '\n<div class="section">\n'
        '<div class="section-header">'
        '<span class="section-icon">🏛️</span>'
        '<span class="section-title">Convocações para Comissões</span>'
        '</div>\n'
        '<div class="section-body">\n'
    )

    if not dias_comissoes:
        return (
            header +
            '<p style="color:#5A6A85;font-style:italic;font-size:12.5px;padding:6px 0">'
            'Nenhuma convocação de comissão divulgada para os próximos dias.</p>\n'
            '</div>\n</div>\n'
        )

    corpo = ""
    for i, d in enumerate(dias_comissoes):
        cor = "#1A3A9C" if d["estilo"] == "destaque" else "#8A9AB5"
        bt  = "border-top:none;padding-top:0" if i == 0 else "margin-top:16px"

        corpo += (
            '<div class="sub-label" style="color:{cor};{bt}">'
            '&mdash; {label} &middot; {data_br} &mdash;</div>'
        ).format(
            cor=cor, bt=bt,
            label=d["label"],
            data_br="{:02d}/{:02d}".format(d["data"].day, d["data"].month)
        )

        for ev in d["eventos"]:
            titulo    = ev.get("titulo", "")
            horario   = ev.get("horario", "")
            local     = ev.get("local", "")
            solicit   = ev.get("solicitante", "")

            # Cruza com membros PSD
            sigla, membros = _psd_na_comissao(titulo, membros_psd)
            tem_psd = bool(membros)
            eh_hoje = d["estilo"] == "destaque"

            # Fundo amarelo apenas para HOJE com PSD
            # Amanhã/demais: item mais claro, sem destaque
            if not eh_hoje:
                item_style = "opacity:0.55;filter:grayscale(10%);"
            elif tem_psd:
                item_style = (
                    "background:linear-gradient(90deg,#FFFBEA 0%,#FFFFF8 100%);"
                    "border-left:3px solid #F5C800;"
                    "margin:0 -20px;padding:10px 20px;"
                )
            else:
                item_style = ""

            meta_parts = []
            if horario: meta_parts.append(
                '<span style="font-size:11px;">🕐 {}</span>'.format(horario))
            if local:   meta_parts.append(
                '<span>📍 {}</span>'.format(local))
            if solicit: meta_parts.append(
                '<span>👤 {}</span>'.format(solicit))
            meta_html = (
                '<div style="font-size:12px;color:#5A6A85;margin-top:3px;'
                'display:flex;gap:12px;flex-wrap:wrap;">' +
                "".join(meta_parts) + "</div>"
            ) if meta_parts else ""

            membros_html = _html_membros_psd(membros) if tem_psd else ""

            corpo += (
                '<div class="comissao-item" style="{item_style}">'
                '<div class="comissao-body">'
                '<div class="comissao-nome">{badge} {titulo}</div>'
                '{meta}'
                '{membros}'
                '</div>'
                '</div>'
            ).format(
                item_style=item_style,
                badge=_badge_tipo(titulo),
                titulo=titulo,
                meta=meta_html,
                membros=membros_html,
            )

    return header + corpo + '</div>\n</div>\n'


def _debug_cruzamento(titulos):
    """Testa o cruzamento de títulos com o JSON de membros."""
    comissoes = _carregar_membros()
    print(f"\n[DEBUG] {len(comissoes)} comissões carregadas do JSON")
    if comissoes:
        c = comissoes[0]
        print(f"[DEBUG] Exemplo: {c['sigla']} | palavras={c['palavras'][:5]} | psd={len(c['psd'])} membros")
    print()
    for titulo in titulos:
        sigla, membros = _psd_na_comissao(titulo, comissoes)
        psd = [m["nome"] for m in membros]
        print(f"  '{titulo[:55]}'")
        print(f"   → {sigla or 'NÃO ACHADO'} | PSD: {psd or 'nenhum'}\n")


if __name__ == "__main__":
    import sys
    if "--debug" in sys.argv:
        _debug_cruzamento([
            "Reunião do Conselho de Ética e Decoro Parlamentar com a finalidade",
            "Reunião da Comissão de Finanças, Orçamento e Planejamento com a f",
            "Reunião da Comissão de Educação e Cultura com a finalidade",
            "Reunião da Comissão de Defesa dos Direitos das Pessoas com Defici",
            "Reunião da Comissão de Defesa dos Direitos do Consumidor",
        ])
        exit()
    from datetime import date, timedelta
    from coletor_agenda_alesp import buscar_agenda_completa, dias_a_exibir

    dias  = dias_a_exibir()
    dias  = buscar_agenda_completa(dias)
    comis = extrair_comissoes(dias)
    html  = gerar_html_comissoes(comis)

    with open("comissoes_bloco.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Salvo em comissoes_bloco.html")
    for d in comis:
        print(f"\n{d['label']} {d['data']:%d/%m}")
        for ev in d["eventos"]:
            sigla, membros = _psd_na_comissao(ev["titulo"], _carregar_membros())
            psd_txt = f" | PSD: {', '.join(m['nome'] for m in membros)}" if membros else ""
            print(f"  {ev['horario']} {ev['titulo'][:60]}{psd_txt}")

# ── Funções para seção CPI separada ─────────────────────────────────────────

def extrair_cpis(dias):
    """Filtra apenas eventos de CPI/CPMI da agenda."""
    resultado = []
    for d in dias:
        cpis = [ev for ev in d.get("eventos", [])
                if any(k in ev.get("titulo", "").lower()
                       for k in ["cpi", "cpmi"])]
        if cpis:
            resultado.append({
                "label":  d["label"],
                "data":   d["data"],
                "estilo": d["estilo"],
                "eventos": cpis,
            })
    return resultado


def _psd_na_cpi(titulo, cpis_membros):
    """Cruza título do evento com membros PSD da CPI correspondente."""
    titulo_l = titulo.lower()
    for nome_cpi, dados in cpis_membros.items():
        palavras = [p for p in nome_cpi.lower().split() if len(p) > 3
                    and p not in ("para", "com", "dos", "das", "que")]
        if sum(1 for p in palavras if p in titulo_l) >= 2:
            return [m["nome"] for m in dados.get("psd", [])]
    return []


def gerar_html_cpis(dias_cpis):
    """Gera bloco HTML da seção CPIs — mesmo padrão das comissões."""
    import json, os

    cpis_membros = {}
    if os.path.exists("cpis_membros.json"):
        with open("cpis_membros.json", encoding="utf-8") as f:
            cpis_membros = json.load(f)

    header = (
        '\n<div class="section-header">'
        '<span class="section-icon">&#128270;</span>'
        '<span class="section-title">Reuni&otilde;es de CPIs</span>'
        '</div>\n<div class="section-body">\n'
    )
    footer = '</div>\n'
    vazio  = header + '<p style="color:#5A6A85;font-style:italic;font-size:12px;padding:6px 0;">Nenhuma reuni&atilde;o de CPI divulgada para os pr&oacute;ximos dias.</p>\n' + footer

    if not dias_cpis:
        return vazio

    html = header
    for d in dias_cpis:
        eh_hoje = d["estilo"] == "destaque"
        html += (
            f'<div class="day-label" style="font-weight:700;font-size:12px;'
            f'color:#C05621;text-transform:uppercase;letter-spacing:.6px;'
            f'padding:8px 0 4px;">{d["label"]}</div>\n'
        )
        for ev in d["eventos"]:
            titulo  = ev.get("titulo", "")
            horario = ev.get("horario", "")
            local   = ev.get("local", "")
            membros = _psd_na_cpi(titulo, cpis_membros)

            if not eh_hoje:
                item_style = "opacity:0.55;"
            elif membros:
                item_style = (
                    "background:linear-gradient(90deg,#FEF0E7 0%,#FFFFF8 100%);"
                    "border-left:3px solid #C05621;"
                    "margin:0 -20px;padding:10px 20px;"
                )
            else:
                item_style = ""

            html += f'<div class="agenda-item" style="{item_style}">\n'
            if horario:
                html += f'  <div class="agenda-time">{horario}</div>\n'
            html += f'  <div class="agenda-content">\n'
            html += f'    <div class="agenda-name">{titulo}</div>\n'
            if local:
                html += f'    <div class="agenda-meta">📍 {local}</div>\n'
            if membros:
                nomes = ", ".join(membros)
                html += (
                    f'    <div style="margin-top:5px;font-size:11.5px;'
                    f'color:#C05621;font-weight:600;">'
                    f'🔶 PSD: {nomes}</div>\n'
                )
            html += '  </div>\n</div>\n'
    html += footer
    return html
