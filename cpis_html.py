#!/usr/bin/env python3
"""cpis_html.py — Seção CPIs com bloco PSD igual às Comissões."""
import json, os, re

def _carregar_cpis():
    if os.path.exists("cpis_membros.json"):
        with open("cpis_membros.json", encoding="utf-8") as f:
            return json.load(f)
    return {}

def _psd_na_cpi(titulo, cpis_membros):
    nome = re.sub(r"^Reuni[aoã]o da ", "", titulo.strip(), flags=re.IGNORECASE)
    for chave, dados in cpis_membros.items():
        if nome.lower().strip() == chave.lower().strip():
            return dados.get("psd", [])
    palavras = [p for p in nome.lower().split()
                if len(p) > 3 and p not in ("para","com","dos","das","que","uma")]
    melhor, score_max = None, 0
    for chave, dados in cpis_membros.items():
        sc = sum(1 for p in palavras if p in chave.lower())
        if sc > score_max and sc >= 3:
            score_max, melhor = sc, dados
    return melhor.get("psd", []) if melhor else []

def _badge_cargo(cargo):
    estilos = {
        "Presidente":      ("#FEF0E7","#C05621"),
        "Vice-Presidente": ("#FEF9E7","#B7791F"),
        "Efetivo":         ("#EBF2FF","#1A3A9C"),
        "Suplente":        ("#F7FAFC","#4A5568"),
    }
    bg, cor = estilos.get(cargo, ("#EEE","#333"))
    return ("<span style=\"display:inline-block;padding:1px 7px;border-radius:9px;"
            "font-size:10px;font-weight:700;background:{bg};color:{cor};\">"
            "{cargo}</span>").format(bg=bg, cor=cor, cargo=cargo)

def gerar_html_cpis(dias_cpis):
    """Bloco HTML CPIs com membros PSD."""
    cpis_membros = _carregar_cpis()
    SEC_OPEN  = (
        "\n<div class=\"section\">\n"
        "<div class=\"section-header\">"
        "<span class=\"section-icon\">&#128270;</span>"
        "<span class=\"section-title\">Reuni&otilde;es de CPIs</span>"
        "</div>\n<div class=\"section-body\">\n"
    )
    SEC_CLOSE = "</div>\n</div>\n"
    VAZIO = (SEC_OPEN
             + "<p style=\"color:#5A6A85;font-style:italic;font-size:12px\">"
             + "Nenhuma reuni&atilde;o de CPI nos pr&oacute;ximos dias.</p>\n"
             + SEC_CLOSE)
    if not dias_cpis:
        return VAZIO

    html = SEC_OPEN
    for d in dias_cpis:
        eh_hoje = d["estilo"] == "destaque"
        lbl = d["label"].replace("AMANHA","AMANH\u00c3")
        html += ("<div style=\"font-weight:700;font-size:11px;color:#C05621;"
                 "text-transform:uppercase;letter-spacing:.6px;"
                 "padding:8px 0 4px;border-bottom:1px solid #FCE0C8;"
                 "margin-bottom:6px;\">&mdash; {lbl} &mdash;</div>\n").format(lbl=lbl)
        for ev in d["eventos"]:
            titulo  = ev.get("titulo","")
            horario = ev.get("horario","")
            local   = ev.get("local","")
            membros = _psd_na_cpi(titulo, cpis_membros)
            if not eh_hoje:
                ist = "opacity:0.5;"
            elif membros:
                ist = ("background:linear-gradient(90deg,#FEF0E7 0%,#FFFFF8 100%);"
                       "border-left:3px solid #C05621;margin:0 -20px;padding:10px 20px;")
            else:
                ist = ""
            BADGE_CPI = ("<span style=\"display:inline-block;padding:1px 7px;"
                         "border-radius:9px;font-size:10.5px;font-weight:700;"
                         "background:#FEF0E7;color:#C05621;"
                         "border:1px solid #F6AD55;margin-right:6px;\">CPI</span>")
            html += "<div class=\"agenda-item\" style=\"{ist}\">\n".format(ist=ist)
            if horario:
                html += "  <div class=\"agenda-time\">{h}</div>\n".format(h=horario)
            html += "  <div class=\"agenda-content\">\n"
            html += "    <div class=\"agenda-name\">{b}{t}</div>\n".format(b=BADGE_CPI,t=titulo)
            if local:
                html += "    <div class=\"agenda-meta\">&#128205; {l}</div>\n".format(l=local)
            if membros and eh_hoje:
                html += ("    <div style=\"margin-top:8px;padding:8px 10px;"
                         "background:#FFFBEA;border-radius:6px;border:1px solid #F6E05E;\">\n"
                         "      <div style=\"font-size:10px;font-weight:800;color:#744210;"
                         "letter-spacing:.5px;margin-bottom:5px;\">"
                         "&#11088; PSD NA COMISS&Atilde;O</div>\n")
                for m in membros:
                    html += ("      <div style=\"display:flex;align-items:center;gap:4px;padding:3px 0;\">"
                             "&#128100; <span style=\"font-size:12px;font-weight:600;color:#2D3748;\">{n}</span>"
                             "{b}</div>\n").format(n=m.get("nome",""), b=_badge_cargo(m.get("cargo","Efetivo")))
                html += "    </div>\n"
            html += "  </div>\n</div>\n"
    html += SEC_CLOSE
    return html
