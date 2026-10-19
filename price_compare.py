"""Compare product prices on Amazon.in and Flipkart.

Usage:
    pip install requests beautifulsoup4
    python price_compare.py "iphone 15"
    python price_compare.py            # prompts for the item name
"""
import argparse
import re
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
}
PRICE_RE = re.compile(r"₹\s?[\d,]+(?:\.\d+)?")


def fetch(url):
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def price_value(price):
    return float(re.sub(r"[^\d.]", "", price) or 0)


def search_amazon(query, limit):
    base = "https://www.amazon.in"
    soup = fetch(f"{base}/s?k={quote_plus(query)}")
    results = []
    for item in soup.select('div[data-component-type="s-search-result"]'):
        title_el = item.select_one("h2")
        price_el = item.select_one("span.a-price span.a-offscreen")
        link_el = item.select_one("a.a-link-normal[href]")
        if not (title_el and price_el):
            continue
        results.append({
            "title": title_el.get_text(" ", strip=True),
            "price": price_el.get_text(strip=True),
            "url": urljoin(base, link_el["href"].split("?")[0]) if link_el else "",
        })
        if len(results) >= limit:
            break
    return results


def search_flipkart(query, limit):
    base = "https://www.flipkart.com"
    soup = fetch(f"{base}/search?q={quote_plus(query)}")
    results, seen = [], set()
    # Flipkart class names are obfuscated and change often, so match on product links instead.
    for a in soup.select('a[href*="/p/"]'):
        href = a["href"].split("?")[0]
        if href in seen:
            continue
        img = a.find("img")
        title = a.get("title") or (img.get("alt") if img else "") or a.get_text(" ", strip=True)
        node, price = a, None
        for _ in range(4):
            match = PRICE_RE.search(node.get_text(" ", strip=True))
            if match:
                price = match.group(0)
                break
            node = node.parent
            if node is None:
                break
        if not (title and price):
            continue
        seen.add(href)
        results.append({"title": title[:120], "price": price, "url": urljoin(base, href)})
        if len(results) >= limit:
            break
    return results


def print_results(site, results):
    print(f"\n=== {site} ===")
    if not results:
        print("  No results found.")
        return
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r['title']}\n     Price: {r['price']}\n     Link:  {r['url']}")


def main():
    parser = argparse.ArgumentParser(description="Compare prices on Amazon and Flipkart")
    parser.add_argument("item", nargs="*", help="Product name to search")
    parser.add_argument("-n", "--limit", type=int, default=3, help="Results per site (default 3)")
    args = parser.parse_args()

    query = " ".join(args.item).strip() or input("Enter product name: ").strip()
    if not query:
        print("No product name given.")
        return

    print(f"Searching for '{query}'...")
    best = {}
    for site, func in (("Amazon", search_amazon), ("Flipkart", search_flipkart)):
        try:
            results = func(query, args.limit)
        except requests.RequestException as exc:
            print(f"\n=== {site} ===\n  Error fetching results: {exc}")
            continue
        print_results(site, results)
        if results:
            best[site] = results[0]

    if len(best) == 2:
        a, f = price_value(best["Amazon"]["price"]), price_value(best["Flipkart"]["price"])
        cheaper = "Amazon" if a < f else "Flipkart" if f < a else "Both (same price)"
        print(f"\nTop result: Amazon {best['Amazon']['price']} vs Flipkart {best['Flipkart']['price']}"
              f" -> Cheaper: {cheaper}")


if __name__ == "__main__":
    main()
