#!/usr/bin/env python3
"""
Monitor de preços Pokémon TCG — versão GitHub Actions + GitHub Pages.

Mesma lógica de busca por nome (com validação de número de carta) do
script original, mas agora grava um docs/data.json que o painel estático
(docs/index.html) consome direto — sem backend, sem banco de dados.

Rodado automaticamente pelo GitHub Actions (.github/workflows/scrape.yml),
que também faz commit do resultado de volta pro repositório.
"""

import json
import re
import time
import sys
import urllib.parse
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "products.json"
DATA_PATH = BASE_DIR / "docs" / "data.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}
REQUEST_DELAY_SECONDS = 3


def to_float(price_str):
    if not price_str:
        return None
    cleaned = re.sub(r"[^\d,\.]", "", price_str)
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


def fetch(url):
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def result_matches_card_number(item_text, card_number):
    if not card_number:
        return True
    number_part = card_number.split("/")[0].strip()
    return number_part in re.sub(r"\s+", "", item_text)


def search_woocommerce(search_url_template, query, card_number=None):
    url = search_url_template.format(query=urllib.parse.quote_plus(query))
    soup = fetch(url)
    candidates = soup.select("ul.products li.product") or soup.select(".product")
    if not candidates:
        return None, None, "sem_resultado"

    chosen = None
    for item in candidates[:5]:
        if result_matches_card_number(item.get_text(" ", strip=True), card_number):
            chosen = item
            break
    if chosen is None:
        fallback = candidates[0].select_one("a")
        return None, fallback["href"] if fallback else None, "numero_nao_confere"

    link_tag = chosen.select_one("a")
    product_url = link_tag["href"] if link_tag and link_tag.has_attr("href") else url
    price_box = chosen.select_one("ins .woocommerce-Price-amount bdi") \
        or chosen.select_one(".woocommerce-Price-amount bdi") \
        or chosen.select_one(".price")
    price = to_float(price_box.get_text()) if price_box else None

    if price is None and product_url:
        try:
            product_soup = fetch(product_url)
            price_box = product_soup.select_one("p.price ins .woocommerce-Price-amount bdi") \
                or product_soup.select_one(".woocommerce-Price-amount bdi")
            price = to_float(price_box.get_text()) if price_box else None
        except requests.RequestException:
            pass

    return price, product_url, "ok" if price is not None else "preco_nao_encontrado"


def search_mercadolivre(search_url_template, query, card_number=None):
    url = search_url_template.format(query=urllib.parse.quote_plus(query.replace(" ", "-")))
    soup = fetch(url)
    candidates = soup.select(".ui-search-layout__item") or soup.select(".ui-search-result")
    if not candidates:
        return None, None, "sem_resultado"

    chosen = None
    for item in candidates[:5]:
        if result_matches_card_number(item.get_text(" ", strip=True), card_number):
            chosen = item
            break
    if chosen is None:
        fallback = candidates[0].select_one("a")
        return None, fallback["href"] if fallback else None, "numero_nao_confere"

    link_tag = chosen.select_one("a")
    product_url = link_tag["href"] if link_tag and link_tag.has_attr("href") else url
    price_box = chosen.select_one(".andes-money-amount__fraction")
    price = to_float(price_box.get_text()) if price_box else None
    return price, product_url, "ok" if price is not None else "preco_nao_encontrado"


def search_amazon(search_url_template, query, card_number=None):
    url = search_url_template.format(query=urllib.parse.quote_plus(query))
    soup = fetch(url)
    candidates = soup.select('div[data-component-type="s-search-result"]')
    if not candidates:
        return None, None, "sem_resultado"

    chosen = None
    for item in candidates[:5]:
        if result_matches_card_number(item.get_text(" ", strip=True), card_number):
            chosen = item
            break
    if chosen is None:
        link = candidates[0].select_one("h2 a")
        fallback_url = "https://www.amazon.com.br" + link["href"] if link and link.has_attr("href") else None
        return None, fallback_url, "numero_nao_confere"

    link_tag = chosen.select_one("h2 a")
    product_url = "https://www.amazon.com.br" + link_tag["href"] if link_tag and link_tag.has_attr("href") else url
    price_box = chosen.select_one("span.a-price span.a-offscreen")
    price = to_float(price_box.get_text()) if price_box else None
    return price, product_url, "ok" if price is not None else "preco_nao_encontrado"


def search_generic(search_url_template, query, card_number=None):
    url = search_url_template.format(query=urllib.parse.quote_plus(query))
    soup = fetch(url)
    text = soup.get_text(" ", strip=True)
    if not result_matches_card_number(text, card_number):
        return None, url, "numero_nao_confere"
    match = re.search(r"R\$\s?\d{1,3}(?:\.\d{3})*,\d{2}", text)
    price = to_float(match.group()) if match else None
    return price, url, "ok" if price is not None else "preco_nao_encontrado"


def search_mypcards(search_url_template, query, card_number=None):
    """MyP Cards não tem um formulário de busca livre público confirmado — cada
    carta vive numa página própria por edição/número. Como estratégia prática,
    buscamos a listagem geral de Pokémon (que mostra vários anúncios recentes
    com nome, número e preço no próprio texto) e procuramos por um card cujo
    texto bata com a query E o número informado. Cobertura parcial: só pega
    o que estiver nessa listagem no momento — não é uma busca completa do
    catálogo. Precisa de card_number pra ser confiável."""
    if not card_number:
        return None, None, "requer_numero_de_carta"

    url = search_url_template.format(query=urllib.parse.quote_plus(query))
    soup = fetch(url)
    number_part = card_number.split("/")[0].strip()

    candidates = soup.select("li, article, div.produto, div[class*=produto]")
    for item in candidates:
        text = item.get_text(" ", strip=True)
        if number_part in re.sub(r"\s+", "", text) and any(w.lower() in text.lower() for w in query.split()[:2]):
            link_tag = item.select_one("a[href*='/produto/']")
            product_url = link_tag["href"] if link_tag and link_tag.has_attr("href") else None
            if product_url and not product_url.startswith("http"):
                product_url = "https://mypcards.com" + product_url
            match = re.search(r"R\$\s?\d{1,3}(?:\.\d{3})*[,.]\d{2}", text)
            price = to_float(match.group()) if match else None
            if price is not None:
                return price, product_url, "ok"

    return None, url, "nao_encontrado_na_listagem_atual"


def search_cardtrader(search_url_template, query, card_number=None):
    """CardTrader é uma plataforma internacional (cardtrader.com) — preços
    aparecem na moeda padrão do site (geralmente EUR ou USD), não R$.
    Trate como referência de preço internacional, não brasileira."""
    url = search_url_template.format(query=urllib.parse.quote_plus(query))
    soup = fetch(url)
    candidates = soup.select("a[href*='/cards/'], div[class*=product], li[class*=product]")
    if not candidates:
        return None, None, "sem_resultado"

    chosen = None
    for item in candidates[:8]:
        text = item.get_text(" ", strip=True)
        if result_matches_card_number(text, card_number):
            chosen = item
            break
    if not chosen:
        return None, None, "numero_nao_confere"

    text = chosen.get_text(" ", strip=True)
    href = chosen.get("href") if chosen.name == "a" else (chosen.select_one("a")["href"] if chosen.select_one("a") else None)
    product_url = ("https://www.cardtrader.com" + href) if href and not href.startswith("http") else href
    match = re.search(r"[\$€£]\s?\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?", text)
    price = to_float(match.group()) if match else None

    return price, product_url, "ok" if price is not None else "preco_nao_encontrado"


STRATEGIES = {
    "woocommerce_search": search_woocommerce,
    "mypcards_search": search_mypcards,
    "cardtrader_search": search_cardtrader,
    "mercadolivre_search": search_mercadolivre,
    "amazon_search": search_amazon,
    "generic_search": search_generic,
}


def run():
    if not CONFIG_PATH.exists():
        print(f"Não encontrei {CONFIG_PATH}.")
        sys.exit(1)

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    existing = {"history": [], "latest": {}}
    if DATA_PATH.exists():
        try:
            existing = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    history = existing.get("history", [])
    latest = existing.get("latest", {})
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    timestamp = now.isoformat(timespec="minutes")  # UTC — o painel converte pra horário de Brasília
    ok_count = 0

    for product in config.get("products", []):
        name = product["name"]
        card_number = product.get("card_number")
        query = product.get("search_query") or f"{name} {card_number or ''}".strip()
        latest.setdefault(name, {})

        for site in config.get("sites", []):
            site_name = site["site"]
            strategy_fn = STRATEGIES.get(site.get("strategy", "generic_search"), search_generic)

            try:
                price, matched_url, status = strategy_fn(site["search_url"], query, card_number)
            except requests.RequestException as e:
                print(f"[erro] {name} / {site_name}: falha ao acessar o site ({e})")
                price, matched_url, status = None, None, "erro_rede"
            except Exception as e:
                print(f"[erro] {name} / {site_name}: falha ao ler o preço ({e})")
                price, matched_url, status = None, None, "erro_leitura"

            if status == "numero_nao_confere":
                print(f"[divergente] {name} / {site_name}: número '{card_number}' não bateu — pulei. {matched_url}")
            elif price is None:
                print(f"[sem preço] {name} / {site_name}: {status}")
            else:
                print(f"[ok] {name} / {site_name}: R$ {price:.2f} → {matched_url}")
                ok_count += 1
                history.append({
                    "date": today, "timestamp": timestamp, "item": name, "type": product.get("type", ""),
                    "market": product.get("market", "BR"), "site": site_name,
                    "price": price, "matchedUrl": matched_url,
                })
                latest[name][site_name] = {"price": price, "date": today, "timestamp": timestamp, "url": matched_url}

            time.sleep(REQUEST_DELAY_SECONDS)

    DATA_PATH.parent.mkdir(exist_ok=True)
    DATA_PATH.write_text(
        json.dumps({
            "history": history, "latest": latest,
            "lastRun": {"date": today, "timestamp": timestamp, "okCount": ok_count},
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nConcluído. {ok_count} preço(s) registrados. Dados salvos em {DATA_PATH}.")


if __name__ == "__main__":
    run()
