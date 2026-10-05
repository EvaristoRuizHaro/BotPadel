"""Adaptador genérico para tiendas Shopify (endpoint público /products.json)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from padel_bot.adaptadores.base import Adaptador
from padel_bot.models import ProductoNormalizado
from padel_bot.normalizar import (
    a_decimal,
    detectar_categoria,
    detectar_marca,
    ean_valido,
    limpiar_nombre,
)

POR_PAGINA = 250


def parsear_productos(
    datos: dict[str, Any], tienda: str, url_base: str
) -> list[ProductoNormalizado]:
    """Convierte la respuesta de /products.json en productos normalizados.

    Un producto Shopify tiene varias variantes (tallas, pesos...). Se devuelve una entrada
    por producto con la variante disponible más barata.
    """
    resultado: list[ProductoNormalizado] = []
    for prod in datos.get("products", []):
        variantes = prod.get("variants") or []
        if not variantes:
            continue
        disponibles = [v for v in variantes if v.get("available", True)]
        candidatas = disponibles or variantes
        variante = min(candidatas, key=lambda v: a_decimal(v.get("price")) or Decimal("Infinity"))

        precio = a_decimal(variante.get("price"))
        if precio is None:
            continue
        original = a_decimal(variante.get("compare_at_price"))
        if original is not None and original <= precio:
            original = None

        tags = prod.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]
        imagenes = prod.get("images") or []

        resultado.append(
            ProductoNormalizado(
                tienda=tienda,
                id_externo=str(prod["id"]),
                nombre=limpiar_nombre(prod.get("title", "")),
                marca=detectar_marca(prod.get("vendor"), prod.get("title")),
                categoria=detectar_categoria(
                    prod.get("title"), prod.get("product_type"), " ".join(tags)
                ),
                url=f"{url_base}/products/{prod['handle']}",
                imagen=imagenes[0].get("src") if imagenes else None,
                precio=precio,
                precio_original=original,
                disponible=bool(disponibles),
                ean=ean_valido(variante.get("barcode")),
            )
        )
    return resultado


class AdaptadorShopify(Adaptador):
    def _url_listado(self, pagina: int) -> str:
        base = self.config.url_base
        if self.config.coleccion:
            base = f"{base}/collections/{self.config.coleccion}"
        return f"{base}/products.json?limit={POR_PAGINA}&page={pagina}"

    async def obtener_productos(self) -> list[ProductoNormalizado]:
        productos: list[ProductoNormalizado] = []
        for pagina in range(1, self.config.max_paginas + 1):
            datos = await self.cliente.get_json(self._url_listado(pagina))
            lote = parsear_productos(datos, self.tienda, self.config.url_base)
            productos.extend(lote)
            if len(datos.get("products", [])) < POR_PAGINA:
                break
        return productos
