"""Adaptador genérico basado en JSON-LD schema.org/Product (PrestaShop, Magento...).

Obtiene las URLs de producto de un sitemap (o de la config) y lee el JSON-LD de cada ficha.
Es el más lento (1 petición por producto), así que conviene acotar con `filtro_urls`
y `max_productos`.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from selectolax.lexbor import LexborHTMLParser

from padel_bot.adaptadores.base import Adaptador
from padel_bot.models import ProductoNormalizado
from padel_bot.normalizar import (
    a_decimal,
    detectar_categoria,
    detectar_marca,
    ean_valido,
    limpiar_nombre,
)

log = logging.getLogger(__name__)


def _nodos(dato: Any) -> list[dict[str, Any]]:
    """Aplana listas y @graph para recorrer todos los objetos JSON-LD."""
    if isinstance(dato, list):
        return [n for d in dato for n in _nodos(d)]
    if isinstance(dato, dict):
        return [dato, *_nodos(dato.get("@graph", []))]
    return []


def _es_producto(nodo: dict[str, Any]) -> bool:
    tipo = nodo.get("@type")
    tipos = tipo if isinstance(tipo, list) else [tipo]
    return "Product" in tipos


def _texto(valor: Any) -> str | None:
    if isinstance(valor, dict):
        return valor.get("name")
    if isinstance(valor, list):
        return _texto(valor[0]) if valor else None
    return str(valor) if valor else None


def parsear_jsonld(html: str, tienda: str, url: str) -> ProductoNormalizado | None:
    arbol = LexborHTMLParser(html)
    for script in arbol.css('script[type="application/ld+json"]'):
        try:
            dato = json.loads(script.text(strip=True) or "null")
        except json.JSONDecodeError:
            continue
        for nodo in _nodos(dato):
            if _es_producto(nodo):
                return _producto_desde_nodo(nodo, tienda, url)
    return None


def _producto_desde_nodo(nodo: dict[str, Any], tienda: str, url: str) -> ProductoNormalizado | None:
    ofertas = nodo.get("offers") or {}
    if isinstance(ofertas, list):
        ofertas = ofertas[0] if ofertas else {}
    precio = a_decimal(ofertas.get("price") or ofertas.get("lowPrice"))
    if precio is None:
        return None
    original = None
    spec = ofertas.get("priceSpecification")
    if isinstance(spec, list):  # algunas tiendas publican el precio tachado aquí
        tachados = [a_decimal(s.get("price")) for s in spec if "ListPrice" in str(s)]
        original = next((t for t in tachados if t and t > precio), None)

    disponibilidad = str(ofertas.get("availability", "InStock"))
    nombre = limpiar_nombre(nodo.get("name", ""))
    imagen = nodo.get("image")
    if isinstance(imagen, list):
        imagen = imagen[0] if imagen else None
    if isinstance(imagen, dict):
        imagen = imagen.get("url")

    ean = next(
        (
            e
            for k in ("gtin13", "gtin", "gtin14", "gtin12", "gtin8", "ean")
            if (e := ean_valido(nodo.get(k)))
        ),
        None,
    )
    return ProductoNormalizado(
        tienda=tienda,
        id_externo=str(nodo.get("sku") or nodo.get("productID") or url),
        nombre=nombre,
        marca=detectar_marca(_texto(nodo.get("brand")), nombre),
        categoria=detectar_categoria(_texto(nodo.get("category")), nombre),
        url=nodo.get("url") or url,
        imagen=imagen,
        precio=precio,
        precio_original=original,
        disponible="InStock" in disponibilidad or "LimitedAvailability" in disponibilidad,
        ean=ean,
    )


def urls_de_sitemap(xml: str) -> list[str]:
    return re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)


class AdaptadorJsonLd(Adaptador):
    async def _urls(self) -> list[str]:
        urls = list(self.config.urls_productos)
        if self.config.sitemap:
            urls += urls_de_sitemap(await self.cliente.get_texto(self.config.sitemap))
        if self.config.filtro_urls:
            urls = [u for u in urls if self.config.filtro_urls in u]
        return urls[: self.config.max_productos]

    async def obtener_productos(self) -> list[ProductoNormalizado]:
        productos: list[ProductoNormalizado] = []
        for url in await self._urls():
            try:
                html = await self.cliente.get_texto(url)
            except Exception as exc:  # una ficha rota no tumba la tienda
                log.warning("[%s] Error en %s: %s", self.tienda, url, exc)
                continue
            if producto := parsear_jsonld(html, self.tienda, url):
                productos.append(producto)
        return productos
