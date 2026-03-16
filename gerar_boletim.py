#!/usr/bin/env python3
"""
gerar_boletim.py
Gera o Boletim Matinal do PSD com dados reais da ALESP.
Uso: python gerar_boletim.py
"""

import sys
import os
from datetime import date

# Importa o coletor da agenda
from coletor_agenda_alesp import (
    dias_a_exibir,
    buscar_agenda_completa,
    gerar_html_agenda,
    dia_do_boletim,
    formatar_data_br,
)
from coletor_comissoes import (
    extrair_comissoes,
    gerar_html_comissoes,
)
from coletor_proposituras import (
    buscar_proposituras,
    gerar_html_proposituras,
)
from coletor_diarios import (
    buscar_diario_legislativo,
    buscar_diario_executivo,
    gerar_html_diario_legislativo,
    gerar_html_diario_executivo,
)

TEMPLATE_FILE  = "boletim_template_base.html"
OUTPUT_DIR     = "boletins"

MESES_EXTENSO = [
    "janeiro","fevereiro","marco","abril","maio","junho",
    "julho","agosto","setembro","outubro","novembro","dezembro"
]

def numero_boletim():
    """Lê/incrementa o contador de boletins."""
    contador_file = "contador_boletim.txt"
    if os.path.exists(contador_file):
        with open(contador_file) as f:
            num = int(f.read().strip()) + 1
    else:
        num = 1
    with open(contador_file, "w") as f:
        f.write(str(num))
    return num


def gerar_header_html(ref, num_boletim):
    """Gera o bloco do header com data e número do boletim atualizados."""
    dias_semana = ["Segunda-Feira","Terca-Feira","Quarta-Feira",
                   "Quinta-Feira","Sexta-Feira","Sabado","Domingo"]
    meses = ["janeiro","fevereiro","marco","abril","maio","junho",
             "julho","agosto","setembro","outubro","novembro","dezembro"]
    semana = (ref.isocalendar()[1])
    dia_nome = dias_semana[ref.weekday()]
    mes_nome = meses[ref.month - 1]

    return {
        "boletim_num": "{}º Boletim Matinal".format(num_boletim),
        "data_header": "{}, {} de {} de {}".format(dia_nome, ref.day, mes_nome, ref.year),
        "semana":      "Semana {} · {}".format(semana, ref.year),
    }


def main():
    hoje = date.today()
    ref  = dia_do_boletim(hoje)

    print("=" * 55)
    print("  BOLETIM MATINAL PSD — GERADOR AUTOMÁTICO")
    print("=" * 55)
    print("Executando em:  {}".format(formatar_data_br(hoje)))
    print("Boletim para:   {}".format(formatar_data_br(ref)))
    print("")

    # 1. Carrega o template
    if not os.path.exists(TEMPLATE_FILE):
        print("ERRO: Arquivo '{}' não encontrado!".format(TEMPLATE_FILE))
        sys.exit(1)

    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        boletim = f.read()

    # 2. Coleta a Agenda (uma única requisição, reutilizada por ambas as seções)
    print("[1/5] Coletando Agenda da ALESP...")
    try:
        dias = dias_a_exibir(hoje)
        dias = buscar_agenda_completa(dias)
        agenda_html    = '<div class="section">\n' + gerar_html_agenda(dias) + '\n  </div>'
        total_eventos  = sum(len(d["eventos"]) for d in dias)
        print("      {} eventos coletados".format(total_eventos))
    except Exception as e:
        print("      AVISO: Erro ao coletar agenda — {}".format(e))
        agenda_html = '<div class="section"><div class="section-body"><p style="color:#C0392B">Erro ao carregar agenda.</p></div></div>'
        dias = []

    # 2b. Extrai Comissões dos mesmos dados (sem nova requisição)
    print("[2/5] Extraindo Convocações para Comissões...")
    try:
        dias_comissoes  = extrair_comissoes(dias)
        comissoes_html  = '<div class="section">\n' + gerar_html_comissoes(dias_comissoes) + '\n  </div>'
        total_comissoes = sum(len(d["eventos"]) for d in dias_comissoes)
        print("      {} convocações encontradas".format(total_comissoes))
    except Exception as e:
        print("      AVISO: Erro ao extrair comissões — {}".format(e))
        comissoes_html = '<div class="section"><div class="section-body"><p style="color:#C0392B">Erro ao carregar comissões.</p></div></div>'

    # 3. Proposituras em Pauta
    print("[3/5] Coletando Proposituras em Pauta...")
    try:
        props          = buscar_proposituras()
        props_html     = '<div class="section">\n' + gerar_html_proposituras(props, ref_date=ref) + '\n  </div>'
        print("      {} proposituras encontradas".format(len(props)))
    except Exception as e:
        print("      AVISO: {}".format(e))
        data_fmt   = ref.strftime("%d/%m/%Y")
        props_html = (
            '<div class="section">\n  <div class="section-header">'
            '<span class="section-icon">&#128196;</span>'
            '<span class="section-title">Proposituras em Pauta</span></div>'
            '\n  <div class="section-body"><p style="color:#5A6A85;font-style:italic;'
            'font-size:12px;padding:6px 0;">Pauta não divulgada para o dia {data}.</p>'
            '</div>\n</div>'
        ).format(data=data_fmt)

    # 4. Diário Legislativo (DOE — mesma data do boletim)
    print("[4/5] Coletando Diário Legislativo ({})...".format(ref.strftime("%d/%m/%Y")))
    try:
        r_leg      = buscar_diario_legislativo(ref)
        leg_html   = '<div class="section">\n' + gerar_html_diario_legislativo(r_leg) + '\n  </div>'
        print("      {} atos encontrados".format(len(r_leg["items"])))
    except Exception as e:
        print("      AVISO: {}".format(e))
        from coletor_diarios import DIARIO_LEG, _url_sumario
        data_fmt = ref.strftime("%d/%m/%Y")
        leg_html = (
            '<div class="section">\n  <div class="section-header">'
            '<span class="section-icon">&#128218;</span>'
            '<span class="section-title">Diário Legislativo — Atos da ALESP</span></div>'
            '\n  <div class="section-body"><p style="color:#5A6A85;font-style:italic;'
            'font-size:12px;padding:6px 0;">Não existem matérias para o dia {data}.</p>'
            '</div>\n</div>'
        ).format(data=data_fmt)

    # 5. Diário Executivo (DOE — mesma data do boletim)
    print("[5/5] Coletando Diário Executivo ({})...".format(ref.strftime("%d/%m/%Y")))
    try:
        r_exe      = buscar_diario_executivo(ref)
        exe_html   = '<div class="section">\n' + gerar_html_diario_executivo(r_exe) + '\n  </div>'
        print("      {} atos encontrados".format(len(r_exe["items"])))
    except Exception as e:
        print("      AVISO: {}".format(e))
        data_fmt = ref.strftime("%d/%m/%Y")
        exe_html = (
            '<div class="section">\n  <div class="section-header">'
            '<span class="section-icon">&#127963;</span>'
            '<span class="section-title">Diário Executivo — Atos do Governo</span></div>'
            '\n  <div class="section-body"><p style="color:#5A6A85;font-style:italic;'
            'font-size:12px;padding:6px 0;">Não existem matérias para o dia {data}.</p>'
            '</div>\n</div>'
        ).format(data=data_fmt)

    # 6. Injeta tudo no template
    boletim = boletim.replace("<!-- AGENDA -->",         agenda_html)
    boletim = boletim.replace("<!-- COMISSOES -->",      comissoes_html)
    boletim = boletim.replace("<!-- PROPOSITURAS -->",   props_html)
    boletim = boletim.replace("<!-- DIARIO_LEG -->",     leg_html)
    boletim = boletim.replace("<!-- DIARIO_EXE -->",     exe_html)

    # 4. Injeta data e número no header via placeholders
    num = numero_boletim()
    info = gerar_header_html(ref, num)
    boletim = boletim.replace("<!-- BOLETIM_NUM -->", info["boletim_num"])
    boletim = boletim.replace("<!-- DATA_HEADER -->", info["data_header"])
    boletim = boletim.replace("<!-- SEMANA -->",      info["semana"])

    # 5. Salva o boletim
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    nome_arquivo = os.path.join(
        OUTPUT_DIR,
        "boletim_{}.html".format(ref.strftime("%d%m%Y"))
    )
    with open(nome_arquivo, "w", encoding="utf-8") as f:
        f.write(boletim)

    print("")
    print("Boletim gerado com sucesso!")
    print("Arquivo: {}".format(nome_arquivo))
    print("")
    print("Abra o arquivo no navegador para visualizar.")


if __name__ == "__main__":
    main()
