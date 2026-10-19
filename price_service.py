"""HTTP API for comparing product prices on Amazon.in and Flipkart."""
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus

import requests
from fastapi import FastAPI, Query

from price_compare import price_value, search_amazon, search_flipkart

app = FastAPI(title="Product Price Comparison API", version="1.0.0")
SEARCHERS = {
    "amazon": search_amazon,
    "flipkart": search_flipkart,
}


@app.get("/")
def index():
    return {
        "service": "Product Price Comparison API",
        "docs": "/docs",
        "search_endpoint": "/api/search?item=iphone%2015",
    }


@app.get("/api/search")
def search(
    item: str = Query(min_length=1, max_length=200),
    limit: int = Query(default=3, ge=1, le=10),
):
    query = item.strip()
    if not query:
        return {"query": item, "results": {}, "errors": {"request": "Item name is required."}}

    results = {}
    errors = {}
    with ThreadPoolExecutor(max_workers=len(SEARCHERS)) as executor:
        futures = {
            site: executor.submit(searcher, query, limit)
            for site, searcher in SEARCHERS.items()
        }
        for site, future in futures.items():
            try:
                results[site] = future.result()
            except requests.RequestException as exc:
                error = {"message": str(exc)}
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                if status_code is not None:
                    error["status_code"] = status_code
                if site == "amazon" and status_code == 503:
                    error["browser_search_url"] = (
                        f"https://www.amazon.in/s?k={quote_plus(query)}"
                    )
                results[site] = []
                errors[site] = error

    comparison = None
    amazon_results = results.get("amazon", [])
    flipkart_results = results.get("flipkart", [])
    if amazon_results and flipkart_results:
        amazon_price = price_value(amazon_results[0]["price"])
        flipkart_price = price_value(flipkart_results[0]["price"])
        cheaper = (
            "amazon" if amazon_price < flipkart_price
            else "flipkart" if flipkart_price < amazon_price
            else "tie"
        )
        comparison = {
            "cheaper_site": cheaper,
            "amazon_price": amazon_results[0]["price"],
            "flipkart_price": flipkart_results[0]["price"],
            "note": "Compares the first result from each site; product variants may differ.",
        }

    return {
        "query": query,
        "results": results,
        "errors": errors,
        "comparison": comparison,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("price_service:app", host="127.0.0.1", port=8000, reload=True)