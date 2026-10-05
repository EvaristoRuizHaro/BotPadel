"""Registro de adaptadores: traduce `adaptador:` de config.yaml a una clase."""

from __future__ import annotations

from padel_bot.adaptadores.base import Adaptador
from padel_bot.adaptadores.jsonld import AdaptadorJsonLd
from padel_bot.adaptadores.shopify import AdaptadorShopify
from padel_bot.adaptadores.tiendas import ADAPTADORES_TIENDA
from padel_bot.adaptadores.woocommerce import AdaptadorWooCommerce
from padel_bot.config import ConfigTienda
from padel_bot.http import ClienteHttp

GENERICOS: dict[str, type[Adaptador]] = {
    "shopify": AdaptadorShopify,
    "woocommerce": AdaptadorWooCommerce,
    "jsonld": AdaptadorJsonLd,
}


def crear_adaptador(config: ConfigTienda, cliente: ClienteHttp) -> Adaptador:
    """Para `html`/`playwright` se busca un adaptador específico con el nombre de la tienda."""
    if config.adaptador in GENERICOS:
        return GENERICOS[config.adaptador](config, cliente)
    if config.nombre in ADAPTADORES_TIENDA:
        return ADAPTADORES_TIENDA[config.nombre](config, cliente)
    raise ValueError(
        f"La tienda '{config.nombre}' usa el adaptador '{config.adaptador}' pero no hay "
        f"implementación en adaptadores/tiendas/"
    )


__all__ = ["Adaptador", "crear_adaptador"]
