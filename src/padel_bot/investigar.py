"""Fase 1: detecta la plataforma de cada tienda y si expone datos estructurados.

Para cada tienda de config.yaml comprueba:
- robots.txt (y si permite /products.json, /wp-json/...)
- Shopify:     /products.json?limit=1
- WooCommerce: /wp-json/wc/store/v1/products?per_page=1
- Huellas en el HTML de la portada (PrestaShop, Magento, Salesforce...)
- JSON-LD Product y sitemaps declarados en robots.txt

Uso:  python -m padel_bot.investigar [--tienda nombre] > investigacion.md
"""

from __future__ import annotations

import argparse
import asyncio
import re
from dataclasses import dataclass, field

import httpx

from padel_bot.config import ConfigTienda, cargar_config
from padel_bot.http import BloqueadoPorRobots, ClienteHttp

HUELLAS = {
    "shopify": ("cdn.shopify.com", "Shopify.theme"),
    "woocommerce": ("woocommerce", "wp-content/plugins/woocommerce"),
    "prestashop": ("prestashop", "/modules/ps_"),
    "magento": ("Magento_", "mage/cookies", "/static/version"),
    "salesforce": ("demandware", "dwanalytics"),
    "vtex": ("vtex",),
}


@dataclass
class Informe:
    tienda: str
    url: str
    plataforma: str = "?"
    shopify_json: bool = False
    woo_store_api: bool = False
    huellas: list[str] = field(default_factory=list)
    sitemaps: list[str] = field(default_factory=list)
    notas: list[str] = field(default_factory=list)


async def _ok_json(cliente: ClienteHttp, url: str, clave: str | None = None) -> bool:
    try:
        resp = await cliente.get(url, headers={"Accept": "application/json"})
        if resp.status_code != 200 or "json" not in resp.headers.get("content-type", ""):
            return False
        datos = resp.json()
        return clave in datos if clave and isinstance(datos, dict) else isinstance(datos, list)
    except BloqueadoPorRobots:
        return False
    except (httpx.HTTPError, ValueError):
        return False


async def investigar_tienda(t: ConfigTienda, cliente: ClienteHttp) -> Informe:
    inf = Informe(t.nombre, t.url_base)
    origen = re.match(r"https?://[^/]+", t.url_base)
    raiz = origen.group(0) if origen else t.url_base

    try:
        robots = await cliente.cliente.get(f"{raiz}/robots.txt")
        if robots.status_code == 200:
            inf.sitemaps = re.findall(r"(?im)^sitemap:\s*(\S+)", robots.text)[:3]
    except httpx.HTTPError as exc:
        inf.notas.append(f"robots.txt: {exc.__class__.__name__}")

    for ruta in ("/products.json", "/wp-json/wc/store/v1/products"):
        if not await cliente.permitido(raiz + ruta):
            inf.notas.append(f"robots prohíbe {ruta}")

    inf.shopify_json = await _ok_json(cliente, f"{raiz}/products.json?limit=1", "products")
    inf.woo_store_api = await _ok_json(cliente, f"{raiz}/wp-json/wc/store/v1/products?per_page=1")

    try:
        resp = await cliente.get(t.url_base)
        html = resp.text
        if resp.status_code in (403, 429, 503):
            inf.notas.append(f"portada HTTP {resp.status_code} (¿antibot?)")
        inf.huellas = [p for p, claves in HUELLAS.items() if any(c in html for c in claves)]
        if '"@type":"Product"' in html.replace(" ", ""):
            inf.notas.append("JSON-LD Product en portada")
    except BloqueadoPorRobots:
        inf.notas.append("robots prohíbe la portada")
    except httpx.HTTPError as exc:
        inf.notas.append(f"portada: {exc.__class__.__name__}")

    if inf.shopify_json:
        inf.plataforma = "shopify"
    elif inf.woo_store_api:
        inf.plataforma = "woocommerce"
    elif inf.huellas:
        inf.plataforma = inf.huellas[0]
    return inf


def a_markdown(informes: list[Informe]) -> str:
    lineas = [
        "| Tienda | Plataforma | Shopify JSON | Woo Store API | Huellas | Sitemaps | Notas |",
        "|---|---|---|---|---|---|---|",
    ]
    for i in informes:
        lineas.append(
            f"| {i.tienda} | {i.plataforma} | {'✅' if i.shopify_json else '—'} | "
            f"{'✅' if i.woo_store_api else '—'} | {', '.join(i.huellas) or '—'} | "
            f"{'<br>'.join(i.sitemaps) or '—'} | {'; '.join(i.notas) or ''} |"
        )
    return "\n".join(lineas)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--tienda")
    args = parser.parse_args()
    config = cargar_config(args.config)
    tiendas = [t for t in config.tiendas if not args.tienda or t.nombre == args.tienda]
    s = config.scraping
    async with ClienteHttp(s.user_agent, s.delay_segundos, s.timeout_segundos) as cliente:
        informes = await asyncio.gather(*(investigar_tienda(t, cliente) for t in tiendas))
    print(a_markdown(list(informes)))


if __name__ == "__main__":
    asyncio.run(main())
