"""Flujo completo sin red: guardar → detectar → deduplicar → resumen."""

from __future__ import annotations

from decimal import Decimal

from conftest import fecha, producto
from padel_bot.config import Config
from padel_bot.db import BaseDatos
from padel_bot.main import procesar_productos
from padel_bot.models import Motivo
from padel_bot.notificador import formatear_oferta, formatear_precio, formatear_resumen


def test_bajada_real_y_no_repetir(db: BaseDatos, config: Config) -> None:
    # Día 1: primera vez que lo vemos, sin tachado → nada que avisar
    assert procesar_productos([producto(precio=Decimal("215.00"))], db, config, fecha(1)) == []

    # Día 2: baja a 189,95 (−11,6 % frente al mínimo) → aviso
    ofertas = procesar_productos(
        [producto(precio=Decimal("189.95"), precio_original=Decimal("269.95"))],
        db,
        config,
        fecha(2),
        "Tienda A",
    )
    assert len(ofertas) == 1
    oferta = ofertas[0]
    assert Motivo.BAJADA_HISTORICA in oferta.motivos
    assert oferta.minimo_previo == Decimal("215.00")
    db.registrar_aviso(oferta, fecha(2))

    texto = formatear_oferta(oferta)
    assert texto.splitlines()[0] == (
        "🔥 Pala Bullpadel Vertex 04 2026 — 189,95 € (antes 269,95 €, −30 %)"
    )
    assert "📉 Mínimo histórico (antes 215 €)" in texto
    assert "🏪 Tienda A · ✅ En stock" in texto

    # Día 3: mismo precio → no se repite
    assert (
        procesar_productos(
            [producto(precio=Decimal("189.95"), precio_original=Decimal("269.95"))],
            db,
            config,
            fecha(3),
        )
        == []
    )

    # Resumen
    resumen = formatear_resumen(db.avisos_desde(fecha(1)))
    assert "Pala Bullpadel Vertex 04 2026 — 189,95 €" in resumen


def test_mejor_precio_cruzando_ean(db: BaseDatos, config: Config) -> None:
    procesar_productos([producto(tienda="tienda_b", precio=Decimal(240))], db, config, fecha(1))
    ofertas = procesar_productos([producto(precio=Decimal(200))], db, config, fecha(1))
    assert ofertas[0].motivos == [Motivo.MEJOR_PRECIO]
    assert ofertas[0].siguiente_precio_otra_tienda == Decimal(240)


def test_seguimiento_ignora_filtros(db: BaseDatos, config: Config) -> None:
    at10 = producto(
        nombre="Pala Nox AT10 Genius", marca="Nox", precio=Decimal(300), ean=None, id_externo="at10"
    )
    procesar_productos([at10.model_copy(update={"disponible": False})], db, config, fecha(1))
    ofertas = procesar_productos([at10], db, config, fecha(2))
    assert ofertas[0].motivos == [Motivo.VUELVE_STOCK]  # aunque supere precio_max


def test_racha_sin_productos(db: BaseDatos) -> None:
    db.registrar_ejecucion("t", 10, None, fecha(1))
    db.registrar_ejecucion("t", 0, "error", fecha(2))
    db.registrar_ejecucion("t", 0, None, fecha(3))
    assert db.ejecuciones_vacias_seguidas("t") == 2


def test_formatear_precio() -> None:
    assert formatear_precio(Decimal("189.95")) == "189,95 €"
    assert formatear_precio(Decimal("215")) == "215 €"
    assert formatear_precio(Decimal("1234.5")) == "1.234,50 €"
