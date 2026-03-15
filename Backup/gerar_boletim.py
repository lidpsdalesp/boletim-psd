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

    # 2. Coleta a Agenda
    print("[1/1] Coletando Agenda da ALESP...")
    try:
        dias = dias_a_exibir(hoje)
        dias = buscar_agenda_completa(dias)
        agenda_html = '<div class="section">\n' + gerar_html_agenda(dias) + '\n  </div>'
        total_eventos = sum(len(d["eventos"]) for d in dias)
        print("      {} eventos coletados".format(total_eventos))
    except Exception as e:
        print("      AVISO: Erro ao coletar agenda — {}".format(e))
        agenda_html = '<div class="section"><div class="section-body"><p style="color:#C0392B">Erro ao carregar agenda. Verifique sua conexão.</p></div></div>'

    # 3. Injeta no template
    boletim = boletim.replace("<!-- AGENDA -->", agenda_html)

    # 4. Atualiza data e número no header
    num = numero_boletim()
    info = gerar_header_html(ref, num)
    boletim = boletim.replace("37º Boletim Matinal", info["boletim_num"])
    boletim = boletim.replace("Sexta-feira, 13 de março de 2026", info["data_header"])
    boletim = boletim.replace("Semana 11 · 2026", info["semana"])

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
