"""Reglas que deciden si un producto es una oferta que merece aviso."""

from __future__ import annotations

from decimal import Decimal

from padel_bot.config import Filtros
from padel_bot.models import EstadoPrevio, Motivo, ProductoNormalizado
from padel_bot.normalizar import normalizar_texto


def pasa_filtros(p: ProductoNormalizado, filtros: Filtros) -> bool:
    """Filtros del usuario: categoría, marca y presupuesto. Solo productos en stock."""
    if not p.disponible:
        return False
    if filtros.categorias and p.categoria not in filtros.categorias:
        return False
    if filtros.marcas:
        marcas = {normalizar_texto(m) for m in filtros.marcas}
        if normalizar_texto(p.marca) not in marcas:
            return False
    return not (filtros.precio_max is not None and p.precio > filtros.precio_max)


def descuento_pct(precio: Decimal, referencia: Decimal | None) -> float:
    if not referencia or referencia <= 0 or precio >= referencia:
        return 0.0
    return float((referencia - precio) / referencia * 100)


def evaluar(
    p: ProductoNormalizado,
    previo: EstadoPrevio,
    filtros: Filtros,
    *,
    en_seguimiento: bool = False,
    precios_otras_tiendas: list[Decimal] | None = None,
) -> list[Motivo]:
    """Devuelve los motivos por los que el producto es oferta (lista vacía = no lo es)."""
    motivos: list[Motivo] = []
    minimo = previo.minimo_historico

    # 1) Bajada real frente a nuestro propio histórico
    if p.disponible and minimo is not None:
        umbral = minimo * (1 - Decimal(str(filtros.bajada_historica_min_pct)) / 100)
        if p.precio <= umbral:
            motivos.append(Motivo.BAJADA_HISTORICA)

    # 1b) Ha bajado respecto a la última vez que lo vimos (cambio de precio entre revisiones)
    ultimo = previo.ultimo_precio
    if (
        p.disponible
        and ultimo is not None
        and Motivo.BAJADA_HISTORICA not in motivos
        and p.precio <= ultimo * (1 - Decimal(str(filtros.bajada_min_pct)) / 100)
    ):
        motivos.append(Motivo.BAJADA_PRECIO)

    # 2) Descuento alto sobre el precio tachado. Si ya hay histórico y el precio actual
    #    está por encima del mínimo visto, el tachado probablemente está inflado: se ignora.
    if (
        p.disponible
        and descuento_pct(p.precio, p.precio_original) >= filtros.descuento_min_pct
        and (minimo is None or p.precio <= minimo)
    ):
        motivos.append(Motivo.DESCUENTO_ALTO)

    # 3) Mejor precio entre tiendas (mismo EAN)
    if p.disponible and precios_otras_tiendas:
        siguiente = min(precios_otras_tiendas)
        if siguiente - p.precio >= filtros.diferencia_min_eur_entre_tiendas:
            motivos.append(Motivo.MEJOR_PRECIO)

    # 4) Un producto vigilado vuelve a estar disponible
    if en_seguimiento and p.disponible and previo.ultimo_disponible is False:
        motivos.append(Motivo.VUELVE_STOCK)

    return motivos


def debe_avisar(precio: Decimal, ultimo_aviso: Decimal | None, motivos: list[Motivo]) -> bool:
    """No repetir avisos del mismo producto salvo que el precio baje otra vez."""
    if not motivos:
        return False
    if Motivo.VUELVE_STOCK in motivos:
        return True
    return ultimo_aviso is None or precio < ultimo_aviso
