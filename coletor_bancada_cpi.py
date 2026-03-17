#!/usr/bin/env python3
"""
coletor_bancada_cpi.py
Busca dinamicamente da ALESP:
  - Lista de deputados do PSD (bancada atualizada)
  - Membros de cada CPI ativa
Estrategia: requests (leve) -> Selenium headless (fallback) -> JSON local (emergencia)
Cache diario em .cache_bancada_DDMMYYYY.json para nao repetir requisicoes.
"""

import os
import json
import time
import unicodedata
import requests
from datetime import date

ALESP_BASE   = "https://www.al.sp.gov.br"
LEGISLATURA  = "20"
PARTIDO_PSD  = "13"   # filtroPartido=13 na ALESP

CPIS_ATIVAS = {
    "questoes_impactantes":  "1000001276",
    "vazamento_dados":       "1000001274",
    "descarte_materiais":    "1000001275",
    "lixoes":                "1000001273",
}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept":     "application/json, text/html, */*",
    "Referer":    "https://www.al.sp.gov.br/",
}

# ── Cache diario ──────────────────────────────────────────────────────────────

def _cache_path():
    hoje = date.today().strftime("%d%m%Y")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        ".cache_bancada_{}.json".format(hoje))


def _ler_cache():
    p = _cache_path()
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _salvar_cache(dados):
    with open(_cache_path(), "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


# ── Utilitario ────────────────────────────────────────────────────────────────

def _normalizar(texto):
    return "".join(
        c for c in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(c) != "Mn"
    )


def _selenium_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,900")
    return webdriver.Chrome(options=opts)


# ── Deputados PSD ─────────────────────────────────────────────────────────────

def _deputados_psd_requests():
    """Tenta endpoints JSON/XML da ALESP para deputados do PSD."""
    endpoints = [
        "{base}/repositorioDados/legislativo/deputados.xml".format(base=ALESP_BASE),
        "{base}/WS/deputados?partido={p}".format(base=ALESP_BASE, p=PARTIDO_PSD),
        "{base}/spl/api/deputado/lista?partido={p}&legislatura={l}".format(
            base=ALESP_BASE, p=PARTIDO_PSD, l=LEGISLATURA),
    ]
    for url in endpoints:
        try:
            r = requests.get(url, headers=_HEADERS, timeout=8)
            if r.status_code == 200 and len(r.text) > 100:
                # Tenta JSON
                if r.text.strip().startswith("[") or r.text.strip().startswith("{"):
                    dados = r.json()
                    nomes = []
                    lista = dados if isinstance(dados, list) else dados.get("deputados", [])
                    for d in lista:
                        n = d.get("nomeDeputado") or d.get("nome") or ""
                        if n:
                            nomes.append(n)
                    if nomes:
                        return nomes
        except Exception:
            continue
    return []


def _deputados_psd_selenium():
    """Selenium: acessa pagina de deputados filtrada por PSD."""
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        driver = _selenium_driver()
        url = "{base}/deputado/lista/?filtroPartido={p}".format(
            base=ALESP_BASE, p=PARTIDO_PSD)
        driver.get(url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".deputado-nome, .nome-deputado, h3, li"))
        )
        time.sleep(2)

        nomes = []
        # Tenta seletores comuns do site da ALESP
        for sel in [".deputado-nome", ".nome-deputado", ".dep-nome",
                    "li.deputado a", "td.nome a", "h3.nome"]:
            els = driver.find_elements(By.CSS_SELECTOR, sel)
            if els:
                nomes = [e.text.strip() for e in els if e.text.strip()]
                break

        if not nomes:
            # Fallback: pega todos os links da lista principal
            els = driver.find_elements(By.CSS_SELECTOR, "ul.lista-deputados li, .lista-itens li")
            nomes = [e.text.strip().split("\n")[0] for e in els if e.text.strip()]

        driver.quit()
        return [n for n in nomes if len(n) > 3]

    except Exception as e:
        print("  [bancada] Selenium erro: {}".format(e))
        return []


def buscar_deputados_psd():
    """Retorna lista de nomes dos deputados do PSD. Cache diario."""
    cache = _ler_cache()
    if "bancada_psd" in cache:
        print("  [bancada] PSD do cache: {} deputados".format(len(cache["bancada_psd"])))
        return cache["bancada_psd"]

    print("  [bancada] Buscando deputados PSD na ALESP...")
    nomes = _deputados_psd_requests()
    if not nomes:
        print("  [bancada] requests falhou, tentando Selenium...")
        nomes = _deputados_psd_selenium()

    if not nomes:
        print("  [bancada] ALERTA: usando lista local de emergencia!")
        nomes = ["Oseias de Madureira", "Marta Costa", "Marcio Nakashima",
                 "Paulo Correa Jr", "Rafael Silva"]
    else:
        print("  [bancada] PSD encontrado: {}".format(", ".join(nomes)))

    cache["bancada_psd"] = nomes
    _salvar_cache(cache)
    return nomes


# ── Membros das CPIs ──────────────────────────────────────────────────────────

def _membros_cpi_requests(id_comissao):
    endpoints = [
        "{base}/WS/membrosComissao?idComissao={id}".format(base=ALESP_BASE, id=id_comissao),
        "{base}/spl/api/comissao/membros?idComissao={id}&idLegislatura={l}".format(
            base=ALESP_BASE, id=id_comissao, l=LEGISLATURA),
        "{base}/alesp/comissao/membros?idComissao={id}".format(base=ALESP_BASE, id=id_comissao),
    ]
    for url in endpoints:
        try:
            r = requests.get(url, headers=_HEADERS, timeout=8)
            if r.status_code == 200 and r.text.strip().startswith("["):
                dados = r.json()
                membros = []
                for d in dados:
                    n = d.get("nomeDeputado") or d.get("nome") or ""
                    if n:
                        membros.append({
                            "nome":    n,
                            "partido": d.get("siglaPartido") or d.get("partido") or "",
                            "tipo":    d.get("tipoMembro") or "Titular",
                        })
                if membros:
                    return membros
        except Exception:
            continue
    return []


def _membros_cpi_selenium(id_comissao):
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        driver = _selenium_driver()
        url = "{base}/comissao/cpi/?idLegislatura={l}&idComissao={id}".format(
            base=ALESP_BASE, l=LEGISLATURA, id=id_comissao)
        driver.get(url)

        # Clica na aba Membros
        try:
            aba = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//a[contains(translate(text(),'MEMBROS','membros'),'membros')]")
                )
            )
            aba.click()
            time.sleep(2)
        except Exception:
            time.sleep(3)

        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table tr td"))
        )

        membros = []
        rows = driver.find_elements(By.CSS_SELECTOR, "table tr")
        for row in rows:
            cols = row.find_elements(By.TAG_NAME, "td")
            if len(cols) >= 2:
                nome    = cols[0].text.strip()
                partido = cols[1].text.strip() if len(cols) > 1 else ""
                tipo    = cols[2].text.strip() if len(cols) > 2 else "Titular"
                if nome and _normalizar(nome) not in ("deputado", "nome", ""):
                    membros.append({"nome": nome, "partido": partido, "tipo": tipo})

        driver.quit()
        return membros

    except Exception as e:
        print("  [membros_cpi] Selenium erro: {}".format(e))
        return []


def _membros_cpi_json_local(chave):
    """Fallback: le membros_cpis.json local."""
    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)), "membros_cpis.json")
    if os.path.exists(caminho):
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
        if chave in dados:
            return dados[chave].get("membros", [])
    return []


def buscar_membros_cpi(chave, id_comissao):
    """Retorna membros de uma CPI. Cache diario."""
    cache = _ler_cache()
    cache_key = "cpi_{}".format(chave)

    if cache_key in cache:
        print("  [membros_cpi] {} do cache: {} membros".format(chave, len(cache[cache_key])))
        return cache[cache_key]

    print("  [membros_cpi] Buscando {} (id={})...".format(chave, id_comissao))
    membros = _membros_cpi_requests(id_comissao)

    if not membros:
        print("  [membros_cpi] requests falhou, tentando Selenium...")
        membros = _membros_cpi_selenium(id_comissao)

    if not membros:
        print("  [membros_cpi] ALERTA: usando JSON local de emergencia!")
        membros = _membros_cpi_json_local(chave)
    else:
        print("  [membros_cpi] {} membros encontrados.".format(len(membros)))

    cache[cache_key] = membros
    _salvar_cache(cache)
    return membros


def buscar_todas_cpis():
    """Busca membros de todas as CPIs ativas de uma vez."""
    resultado = {}
    for chave, id_cpi in CPIS_ATIVAS.items():
        resultado[chave] = buscar_membros_cpi(chave, id_cpi)
    return resultado
