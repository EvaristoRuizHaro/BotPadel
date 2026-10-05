from __future__ import annotations

from decimal import Decimal

from conftest import producto
from padel_bot.config import Filtros
from padel_bot.detector import debe_avisar, evaluar, pasa_filtros
from padel_bot.models import EstadoPrevio, Motivo

FILTROS = Filtros(categorias=["pala"], marcas=["Bullpadel"], precio_max=Decimal(200))


def test_filtros() -> None:
    assert pasa_filtros(producto(precio=Decimal(180)), FILTROS)
    assert not pasa_filtros(producto(precio=Decimal(210)), FILTROS)
    assert not pasa_filtros(producto(precio=Decimal(180), marca="Nox"), FILTROS)
    assert not pasa_filtros(producto(precio=Decimal(180), categoria="ropa"), FILTROS)
    assert not pasa_filtros(producto(precio=Decimal(180), disponible=False), FILTROS)
    assert pasa_filtros(producto(precio=Decimal(999), marca="X"), Filtros())  # sin filtros


def test_bajada_historica() -> None:
    previo = EstadoPrevio(minimo_historico=Decimal(200), num_observaciones=3)
    assert Motivo.BAJADA_HISTORICA in evaluar(producto(precio=Decimal(180)), previo, FILTROS)
    assert evaluar(producto(precio=Decimal(185)), previo, FILTROS) == []  # solo −7,5 %


def test_descuento_alto_sin_historico() -> None:
    p = producto(precio=Decimal(140), precio_original=Decimal(200))  # −30 %
    assert evaluar(p, EstadoPrevio(), FILTROS) == [Motivo.DESCUENTO_ALTO]


def test_descuento_alto_ignorado_si_tachado_inflado() -> None:
    # Ya lo vimos a 120 €: el "−30 %" sobre 200 € no es real
    previo = EstadoPrevio(minimo_historico=Decimal(120), num_observaciones=5)
    p = producto(precio=Decimal(140), precio_original=Decimal(200))
    assert evaluar(p, previo, FILTROS) == []


def test_mejor_precio_entre_tiendas() -> None:
    p = producto(precio=Decimal(150))
    motivos = evaluar(
        p, EstadoPrevio(), FILTROS, precios_otras_tiendas=[Decimal(170), Decimal(190)]
    )
    assert motivos == [Motivo.MEJOR_PRECIO]
    motivos = evaluar(p, EstadoPrevio(), FILTROS, precios_otras_tiendas=[Decimal(160)])
    assert motivos == []  # solo 10 € de diferencia


def test_vuelve_stock_solo_en_seguimiento() -> None:
    previo = EstadoPrevio(
        minimo_historico=Decimal(150), ultimo_disponible=False, num_observaciones=2
    )
    p = producto(precio=Decimal(150))
    assert evaluar(p, previo, FILTROS, en_seguimiento=True) == [Motivo.VUELVE_STOCK]
    assert evaluar(p, previo, FILTROS, en_seguimiento=False) == []


def test_deduplicacion() -> None:
    m = [Motivo.BAJADA_HISTORICA]
    assert debe_avisar(Decimal(150), None, m)
    assert not debe_avisar(Decimal(150), Decimal(150), m)
    assert not debe_avisar(Decimal(160), Decimal(150), m)
    assert debe_avisar(Decimal(140), Decimal(150), m)
    assert debe_avisar(Decimal(150), Decimal(150), [Motivo.VUELVE_STOCK])
    assert not debe_avisar(Decimal(100), None, [])
