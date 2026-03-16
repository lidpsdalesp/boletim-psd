#!/usr/bin/env python3
"""
gerar_boletim.py
Gera a Assessoria PSD · Agenda & Comissões.
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
    extrair_cpis,
    gerar_html_cpis,
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
        "boletim_num": "{}ª Edição".format(num_boletim),
        "data_header": "{}, {} de {} de {}".format(dia_nome, ref.day, mes_nome, ref.year),
        "semana":      "Semana {} · {}".format(semana, ref.year),
    }


def main():
    hoje = date.today()
    ref  = dia_do_boletim(hoje)

    print("=" * 55)
    print("  🏛️  ASSESSORIA PSD · AGENDA & COMISSÕES")
    print("=" * 55)
    print("Executando em:  {}".format(formatar_data_br(hoje)))
    print("Edição para:    {}".format(formatar_data_br(ref)))
    print("")

    # 1. Carrega o template
    if not os.path.exists(TEMPLATE_FILE):
        print("ERRO: Arquivo '{}' não encontrado!".format(TEMPLATE_FILE))
        sys.exit(1)

    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        boletim = f.read()

    # 2. Coleta a Agenda (uma única requisição, reutilizada por ambas as seções)
    print("[1/3] Coletando Agenda da ALESP...")
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
    print("[2/3] Extraindo Convocações para Comissões...")
    try:
        dias_comissoes  = extrair_comissoes(dias)
        comissoes_html  = '<div class="section">\n' + gerar_html_comissoes(dias_comissoes) + '\n  </div>'
        total_comissoes = sum(len(d["eventos"]) for d in dias_comissoes)
        print("      {} convocações encontradas".format(total_comissoes))
    except Exception as e:
        print("      AVISO: Erro ao extrair comissões — {}".format(e))
        comissoes_html = '<div class="section"><div class="section-body"><p style="color:#C0392B">Erro ao carregar comissões.</p></div></div>'


    # 3. Extrai CPIs da mesma agenda
    print("[3/3] Extraindo Reuniões de CPIs...")
    try:
        dias_cpis    = extrair_cpis(dias)
        cpis_html    = '<div class="section">\n' + gerar_html_cpis(dias_cpis) + '\n  </div>'
        total_cpis   = sum(len(d["eventos"]) for d in dias_cpis)
        print("      {} reuniões de CPI encontradas".format(total_cpis))
    except Exception as e:
        print("      AVISO: Erro ao extrair CPIs — {}".format(e))
        cpis_html = '<div class="section"><div class="section-body"><p style="color:#C0392B">Erro ao carregar CPIs.</p></div></div>'

    # 4. Injeta tudo no template
    boletim = boletim.replace("<!-- AGENDA -->",         agenda_html)
    boletim = boletim.replace("<!-- COMISSOES -->",      comissoes_html)
    boletim = boletim.replace("<!-- CPIS -->",           cpis_html)

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
    print("Assessoria PSD gerada com sucesso!")
    print("Arquivo: {}".format(nome_arquivo))
    print("")
    print("Abra o arquivo no navegador para visualizar.")


if __name__ == "__main__":
    main()
