"""Adaptador genérico para WooCommerce (Store API pública /wp-json/wc/store/v1)."""

from __future__ import annotations

from decimal import Decimal
from html import unescape
from typing import Any

from padel_bot.adaptadores.base import Adaptador
from padel_bot.models import ProductoNormalizado
from padel_bot.normalizar import detectar_categoria, detectar_marca, ean_valido, limpiar_nombre

POR_PAGINA = 100


def _precio_minor(valor: str | None, minor_unit: int) -> Decimal | None:
    if valor in (None, ""):
        return None
    return (Decimal(str(valor)) / (10**minor_unit)).quantize(Decimal("0.01"))


def parsear_productos(datos: list[dict[str, Any]], tienda: str) -> list[ProductoNormalizado]:
    resultado: list[ProductoNormalizado] = []
    for prod in datos:
        precios = prod.get("prices") or {}
        minor = int(precios.get("currency_minor_unit", 2))
        precio = _precio_minor(precios.get("price"), minor)
        if precio is None:
            continue
        original = _precio_minor(precios.get("regular_price"), minor)
        if original is not None and original <= precio:
            original = None

        nombre = limpiar_nombre(unescape(prod.get("name", "")))
        categorias = " ".join(unescape(c.get("name", "")) for c in prod.get("categories") or [])
        marcas = " ".join(c.get("name", "") for c in prod.get("brands") or [])
        imagenes = prod.get("images") or []

        resultado.append(
            ProductoNormalizado(
                tienda=tienda,
                id_externo=str(prod.get("id")),
                nombre=nombre,
                marca=detectar_marca(marcas or None, nombre),
                categoria=detectar_categoria(nombre, categorias),
                url=prod.get("permalink", ""),
                imagen=imagenes[0].get("src") if imagenes else None,
                precio=precio,
                precio_original=original,
                disponible=bool(prod.get("is_in_stock", True)),
                ean=ean_valido(prod.get("sku")),
            )
        )
    return resultado


class AdaptadorWooCommerce(Adaptador):
    def _url_listado(self, pagina: int) -> str:
        url = (
            f"{self.config.url_base}/wp-json/wc/store/v1/products"
            f"?per_page={POR_PAGINA}&page={pagina}"
        )
        return url + ("&on_sale=true" if self.config.solo_ofertas else "")

    async def obtener_productos(self) -> list[ProductoNormalizado]:
        productos: list[ProductoNormalizado] = []
        for pagina in range(1, self.config.max_paginas + 1):
            datos = await self.cliente.get_json(self._url_listado(pagina))
            if not datos:
                break
            productos.extend(parsear_productos(datos, self.tienda))
            if len(datos) < POR_PAGINA:
                break
        return productos
