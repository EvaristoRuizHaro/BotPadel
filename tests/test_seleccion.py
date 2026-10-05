from __future__ import annotations

from decimal import Decimal

from conftest import producto
from padel_bot.models import Motivo, Oferta
from padel_bot.seleccion import repartir, seleccion_inicial


def oferta(i: int, categoria: str, pct: float) -> Oferta:
    p = producto(id_externo=str(i), categoria=categoria, precio=Decimal(10))
    return Oferta(producto_id=i, producto=p, motivos=[Motivo.DESCUENTO_ALTO], descuento_pct=pct)


def test_repartir_intercala_categorias() -> None:
    # Las palas tienen más descuento, pero la ropa no debe quedarse fuera
    ofertas = [oferta(i, "pala", 60 - i) for i in range(5)] + [
        oferta(10 + i, "ropa", 45 - i) for i in range(5)
    ]
    enviar, resto = repartir(ofertas, 4)
    assert [o.producto.categoria for o in enviar] == ["pala", "ropa", "pala", "ropa"]
    assert [o.descuento_pct for o in enviar] == [60, 45, 59, 44]
    assert len(resto) == 6


def test_seleccion_inicial_top_por_categoria() -> None:
    ofertas = [oferta(i, "pala", 60 - i) for i in range(20)] + [
        oferta(100 + i, "ropa", 50 - i) for i in range(3)
    ]
    enviar, vistas = seleccion_inicial(ofertas, por_categoria=5)
    assert sum(o.producto.categoria == "pala" for o in enviar) == 5
    assert sum(o.producto.categoria == "ropa" for o in enviar) == 3
    assert len(vistas) == 15
    assert max(o.descuento_pct for o in vistas) < min(
        o.descuento_pct for o in enviar if o.producto.categoria == "pala"
    )
