"""Formato de los avisos y envío por Telegram (o consola si no hay token)."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from decimal import Decimal
from typing import Protocol

import httpx

from padel_bot.db import AvisoResumen
from padel_bot.models import Motivo, Oferta

log = logging.getLogger(__name__)

API_TELEGRAM = "https://api.telegram.org/bot{token}/sendMessage"
LIMITE_MENSAJE = 4096


def formatear_precio(valor: Decimal) -> str:
    """189.95 -> '189,95 €'; 215.00 -> '215 €'; 1234.5 -> '1.234,50 €'."""
    valor = valor.quantize(Decimal("0.01"))
    if valor == valor.to_integral_value():
        texto = f"{int(valor):,}".replace(",", ".")
    else:
        texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{texto} €"


def formatear_oferta(oferta: Oferta) -> str:
    p = oferta.producto
    cabecera = f"🔥 {p.nombre} — {formatear_precio(p.precio)}"
    if p.precio_original and p.precio_original > p.precio:
        pct = round((p.precio_original - p.precio) / p.precio_original * 100)
        cabecera += f" (antes {formatear_precio(p.precio_original)}, −{pct} %)"

    lineas = [cabecera]
    if Motivo.BAJADA_HISTORICA in oferta.motivos and oferta.minimo_previo is not None:
        lineas.append(f"📉 Mínimo histórico (antes {formatear_precio(oferta.minimo_previo)})")
    if Motivo.MEJOR_PRECIO in oferta.motivos and oferta.siguiente_precio_otra_tienda:
        sig = formatear_precio(oferta.siguiente_precio_otra_tienda)
        lineas.append(f"🏆 Más barato que en otras tiendas (siguiente: {sig})")
    if Motivo.VUELVE_STOCK in oferta.motivos:
        lineas.append("🔔 Producto vigilado de nuevo disponible")

    stock = "✅ En stock" if p.disponible else "❌ Sin stock"
    lineas.append(f"🏪 {oferta.nombre_tienda or p.tienda} · {stock}")
    lineas.append(f"🔗 {p.url}")
    return "\n".join(lineas)


def formatear_resumen(avisos: list[AvisoResumen], top: int = 10) -> str:
    if not avisos:
        return "📋 Resumen diario: hoy no ha habido ofertas que cumplan tus filtros."
    por_categoria: dict[str, list[AvisoResumen]] = defaultdict(list)
    for a in sorted(avisos, key=lambda a: a.descuento_pct, reverse=True)[:top]:
        por_categoria[a.categoria or "otros"].append(a)

    lineas = [f"📋 Resumen diario — top {min(top, len(avisos))} ofertas"]
    for categoria, lista in por_categoria.items():
        lineas.append(f"\n▫️ {categoria.capitalize()}")
        for a in lista:
            pct = f" (−{round(a.descuento_pct)} %)" if a.descuento_pct else ""
            lineas.append(
                f"• {a.nombre} — {formatear_precio(a.precio)}{pct} · {a.tienda}\n  {a.url}"
            )
    return "\n".join(lineas)


class Notificador(Protocol):
    async def enviar(self, texto: str) -> None: ...


class NotificadorConsola:
    """Se usa en --dry-run o cuando faltan las credenciales de Telegram."""

    async def enviar(self, texto: str) -> None:
        print(texto, end="\n\n", flush=True)


class NotificadorTelegram:
    def __init__(self, token: str, chat_id: str, cliente: httpx.AsyncClient) -> None:
        self._url = API_TELEGRAM.format(token=token)
        self._chat_id = chat_id
        self._cliente = cliente

    async def enviar(self, texto: str) -> None:
        for trozo in _trocear(texto):
            resp = await self._cliente.post(
                self._url, json={"chat_id": self._chat_id, "text": trozo}
            )
            if resp.status_code == 429:  # rate limit de Telegram
                espera = resp.json().get("parameters", {}).get("retry_after", 5)
                await asyncio.sleep(float(espera))
                resp = await self._cliente.post(
                    self._url, json={"chat_id": self._chat_id, "text": trozo}
                )
            resp.raise_for_status()
            await asyncio.sleep(1.1)  # ~1 mensaje/s por chat


def _trocear(texto: str) -> list[str]:
    if len(texto) <= LIMITE_MENSAJE:
        return [texto]
    trozos, actual = [], ""
    for linea in texto.split("\n"):
        if len(actual) + len(linea) + 1 > LIMITE_MENSAJE:
            trozos.append(actual)
            actual = ""
        actual += linea + "\n"
    if actual:
        trozos.append(actual)
    return trozos
