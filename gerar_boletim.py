#!/usr/bin/env python3
"""
gerar_boletim.py
Gera o Boletim Matinal do PSD com dados reais da ALESP.
Uso: python gerar_boletim.py
"""

import sys
import os
from datetime import date

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
    enriquecer_cpis_com_membros,
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

TEMPLATE_FILE = "boletim_template_base.html"
OUTPUT_DIR    = "boletins"

MESES_EXTENSO = [
    "janeiro","fevereiro","marco","abril","maio","junho",
    "julho","agosto","setembro","outubro","novembro","dezembro"
]

def numero_boletim():
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
    dias_semana = ["Segunda-Feira","Terca-Feira","Quarta-Feira",
                   "Quinta-Feira","Sexta-Feira","Sabado","Domingo"]
    meses = ["janeiro","fevereiro","marco","abril","maio","junho",
             "julho","agosto","setembro","outubro","novembro","dezembro"]
    semana   = ref.isocalendar()[1]
    dia_nome = dias_semana[ref.weekday()]
    mes_nome = meses[ref.month - 1]
    return {
        "boletim_num": u"{}\u00ba Boletim Matinal".format(num_boletim),
        "data_header": u"{}, {} de {} de {}".format(dia_nome, ref.day, mes_nome, ref.year),
        "semana":      u"Semana {} \u00b7 {}".format(semana, ref.year),
    }


def main():
    hoje = date.today()
    ref  = dia_do_boletim(hoje)

    print("=" * 55)
    print(" BOLETIM MATINAL PSD - GERADOR AUTOMATICO")
    print("=" * 55)
    print("Executando em: {}".format(formatar_data_br(hoje)))
    print("Boletim para: {}".format(formatar_data_br(ref)))
    print("")

    if not os.path.exists(TEMPLATE_FILE):
        print("ERRO: Arquivo '{}' nao encontrado!".format(TEMPLATE_FILE))
        sys.exit(1)
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        boletim = f.read()

    # 1. Agenda
    print("[1/5] Coletando Agenda da ALESP...")
    try:
        dias = dias_a_exibir(hoje)
        dias = buscar_agenda_completa(dias)
        agenda_html = gerar_html_agenda(dias)
        print("  OK")
    except Exception as e:
        print("  ERRO: {}".format(e))
        agenda_html = u'<p style="color:red">Erro ao carregar agenda.</p>'

    # 2. Comissoes + membros CPIs
    print("[2/5] Coletando Reunioes de Comissoes...")
    try:
        dias_com = extrair_comissoes(dias)
        dias_com = enriquecer_cpis_com_membros(dias_com)
        comissoes_html = gerar_html_comissoes(dias_com)
        print("  OK")
    except Exception as e:
        print("  ERRO: {}".format(e))
        comissoes_html = u'<p style="color:red">Erro ao carregar comissoes.</p>'

    # 3. Proposituras
    print("[3/5] Coletando Proposituras...")
    try:
        prop = buscar_proposituras()
        proposituras_html = gerar_html_proposituras(prop)
        print("  OK")
    except Exception as e:
        print("  ERRO: {}".format(e))
        proposituras_html = u'<p style="color:red">Pauta nao divulgada para o dia {}.</p>'.format(
            ref.strftime("%d/%m/%Y"))

    # 4. Diario Legislativo
    print("[4/5] Coletando Diario Legislativo...")
    try:
        diario_leg      = buscar_diario_legislativo(ref)
        diario_leg_html = gerar_html_diario_legislativo(diario_leg)
        print("  OK")
    except Exception as e:
        print("  ERRO: {}".format(e))
        diario_leg_html = u'<p style="color:red">Nao existem materias para o dia {}.</p>'.format(
            ref.strftime("%d/%m/%Y"))

    # 5. Diario Executivo
    print("[5/5] Coletando Diario Executivo...")
    try:
        diario_exe      = buscar_diario_executivo(ref)
        diario_exe_html = gerar_html_diario_executivo(diario_exe)
        print("  OK")
    except Exception as e:
        print("  ERRO: {}".format(e))
        diario_exe_html = u'<p style="color:red">Nao existem materias para o dia {}.</p>'.format(
            ref.strftime("%d/%m/%Y"))

    # 6. Header
    num  = numero_boletim()
    info = gerar_header_html(ref, num)

    # 7. Substituicoes — template usa <!-- PLACEHOLDER --> em maiusculas
    boletim = boletim.replace("<!-- BOLETIM_NUM -->", info["boletim_num"])
    boletim = boletim.replace("<!-- DATA_HEADER -->",  info["data_header"])
    boletim = boletim.replace("<!-- SEMANA -->",        info["semana"])
    boletim = boletim.replace("<!-- AGENDA -->",        agenda_html)
    boletim = boletim.replace("<!-- COMISSOES -->",     comissoes_html)
    boletim = boletim.replace("<!-- PROPOSITURAS -->",  proposituras_html)
    boletim = boletim.replace("<!-- DIARIO_LEG -->",    diario_leg_html)
    boletim = boletim.replace("<!-- DIARIO_EXE -->",    diario_exe_html)

    # 8. Salva
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    nome_arquivo = "boletim_{:02d}{:02d}{}.html".format(ref.day, ref.month, ref.year)
    caminho = os.path.join(OUTPUT_DIR, nome_arquivo)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(boletim)

    print("")
    print("=" * 55)
    print("  Boletim gerado: {}".format(caminho))
    print("=" * 55)


if __name__ == "__main__":
    main()
