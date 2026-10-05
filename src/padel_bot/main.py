"""Orquestador: scrapear → guardar → detectar → notificar.

Uso:
    python -m padel_bot.main                 # ejecución normal
    python -m padel_bot.main --dry-run       # imprime los avisos, no envía ni los registra
    python -m padel_bot.main --tienda nox    # solo una tienda (aunque esté inactiva)
    python -m padel_bot.main resumen         # resumen diario de las últimas 24 h
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import UTC, datetime, timedelta

import httpx

from padel_bot.adaptadores import crear_adaptador
from padel_bot.config import Config, ConfigTienda, cargar_config
from padel_bot.db import BaseDatos
from padel_bot.detector import debe_avisar, descuento_pct, evaluar, pasa_filtros
from padel_bot.http import ClienteHttp
from padel_bot.models import Motivo, Oferta, ProductoNormalizado
from padel_bot.normalizar import coincide_seguimiento
from padel_bot.notificador import (
    Notificador,
    NotificadorConsola,
    NotificadorTelegram,
    formatear_oferta,
    formatear_resumen,
)

log = logging.getLogger("padel_bot")


def procesar_productos(
    productos: list[ProductoNormalizado],
    db: BaseDatos,
    config: Config,
    ahora: datetime,
    nombre_tienda: str | None = None,
) -> list[Oferta]:
    """Guarda precios y devuelve las ofertas nuevas que hay que avisar. Sin red."""
    ofertas: list[Oferta] = []
    for p in productos:
        producto_id = db.guardar_producto(p, ahora)
        previo = db.estado_previo(producto_id)
        otros = db.precios_otras_tiendas(p.ean, p.tienda) if p.ean else []
        db.registrar_precio(producto_id, p, ahora)

        en_seguimiento = any(coincide_seguimiento(p.nombre, t) for t in config.seguimiento)
        if not en_seguimiento and not pasa_filtros(p, config.filtros):
            continue

        motivos = evaluar(
            p, previo, config.filtros, en_seguimiento=en_seguimiento, precios_otras_tiendas=otros
        )
        if not debe_avisar(p.precio, db.ultimo_aviso(producto_id), motivos):
            continue

        if Motivo.BAJADA_HISTORICA in motivos:
            referencia = previo.minimo_historico
        elif Motivo.BAJADA_PRECIO in motivos:
            referencia = previo.ultimo_precio
        else:
            referencia = p.precio_original
        ofertas.append(
            Oferta(
                producto_id=producto_id,
                producto=p,
                motivos=motivos,
                minimo_previo=previo.minimo_historico,
                precio_anterior=previo.ultimo_precio,
                siguiente_precio_otra_tienda=min(otros) if otros else None,
                nombre_tienda=nombre_tienda,
                descuento_pct=descuento_pct(p.precio, referencia),
            )
        )
    db.commit()
    return sorted(ofertas, key=lambda o: o.descuento_pct, reverse=True)


async def _scrapear(
    tienda: ConfigTienda, cliente: ClienteHttp
) -> tuple[ConfigTienda, list[ProductoNormalizado] | Exception]:
    try:
        adaptador = crear_adaptador(tienda, cliente)
        return tienda, await adaptador.obtener_productos()
    except Exception as exc:  # un adaptador que falla no tumba la ejecución
        return tienda, exc


def _crear_notificador(config: Config, http: httpx.AsyncClient, dry_run: bool) -> Notificador:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = config.notificaciones.telegram_chat_id
    if dry_run or not token or not chat_id:
        if not dry_run:
            log.warning("Faltan TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID: los avisos van a consola")
        return NotificadorConsola()
    return NotificadorTelegram(token, chat_id, http)


async def ejecutar(config: Config, solo_tienda: str | None = None, dry_run: bool = False) -> int:
    ahora = datetime.now(UTC)
    if solo_tienda:
        tiendas = [t for t in config.tiendas if t.nombre == solo_tienda]
        if not tiendas:
            raise SystemExit(f"No existe la tienda '{solo_tienda}' en config.yaml")
    else:
        tiendas = [t for t in config.tiendas if t.activa and t.adaptador != "pendiente"]
    if not tiendas:
        log.warning("No hay tiendas activas. Completa la fase 1 y activa alguna en config.yaml")
        return 0

    s = config.scraping
    with BaseDatos(s.ruta_db) as db:
        async with (
            ClienteHttp(s.user_agent, s.delay_segundos, s.timeout_segundos) as cliente,
            httpx.AsyncClient(timeout=20) as http_telegram,
        ):
            notificador = _crear_notificador(config, http_telegram, dry_run)
            resultados = await asyncio.gather(*(_scrapear(t, cliente) for t in tiendas))

            total_avisos = 0
            pendientes = 0
            for tienda, resultado in resultados:
                if isinstance(resultado, Exception):
                    log.error("[%s] Error: %r", tienda.nombre, resultado)
                    db.registrar_ejecucion(tienda.nombre, 0, repr(resultado), ahora)
                    productos: list[ProductoNormalizado] = []
                else:
                    productos = resultado
                    db.registrar_ejecucion(tienda.nombre, len(productos), None, ahora)
                log.info("[%s] %d productos", tienda.nombre, len(productos))

                for oferta in procesar_productos(productos, db, config, ahora, tienda.titulo):
                    # Tope por ejecución para no saturar el chat (sobre todo la primera vez).
                    # Lo que no se envía no se registra, así que llegará en la siguiente.
                    if total_avisos >= s.max_avisos_por_ejecucion:
                        pendientes += 1
                        continue
                    await notificador.enviar(formatear_oferta(oferta))
                    if not dry_run:
                        db.registrar_aviso(oferta, ahora)
                    total_avisos += 1

                racha = db.ejecuciones_vacias_seguidas(tienda.nombre)
                if racha == s.max_ejecuciones_vacias:  # avisa una sola vez por racha
                    await notificador.enviar(
                        f"⚠️ {tienda.titulo} lleva {racha} ejecuciones seguidas sin productos. "
                        "Puede que haya cambiado la web o que nos esté bloqueando."
                    )
    log.info("Avisos enviados: %d · pendientes para la próxima: %d", total_avisos, pendientes)
    return total_avisos


async def enviar_resumen(config: Config, dry_run: bool = False) -> None:
    if not config.notificaciones.resumen_diario:
        log.info("Resumen diario desactivado en config.yaml")
        return
    desde = datetime.now(UTC) - timedelta(hours=24)
    with BaseDatos(config.scraping.ruta_db) as db:
        avisos = db.avisos_desde(desde)
    async with httpx.AsyncClient(timeout=20) as http:
        await _crear_notificador(config, http, dry_run).enviar(formatear_resumen(avisos))


def cli() -> None:
    parser = argparse.ArgumentParser(prog="padel-bot", description=__doc__.splitlines()[0])
    parser.add_argument("comando", nargs="?", default="scrape", choices=["scrape", "resumen"])
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--tienda", help="Ejecuta solo esta tienda")
    parser.add_argument("--dry-run", action="store_true", help="No envía ni registra avisos")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):  # emojis en la consola de Windows
        sys.stdout.reconfigure(encoding="utf-8")

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    config = cargar_config(args.config)

    if args.comando == "resumen":
        asyncio.run(enviar_resumen(config, args.dry_run))
    else:
        asyncio.run(ejecutar(config, args.tienda, args.dry_run))


if __name__ == "__main__":
    cli()
