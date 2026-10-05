from __future__ import annotations

from decimal import Decimal

import pytest

from padel_bot.normalizar import (
    a_decimal,
    coincide_seguimiento,
    detectar_categoria,
    detectar_marca,
    ean_valido,
)


@pytest.mark.parametrize(
    ("textos", "esperado"),
    [
        (("BULLPADEL",), "Bullpadel"),
        ((None, "Pala Black Crown Piton 2026"), "Black Crown"),
        (("", "Zapatillas Asics Gel"), "Asics"),
        (("Tienda X", "Pala Nox ML10"), "Nox"),
        ((None, "Pala genérica"), None),
        ((None, "Overhead clinic"), None),  # "head" dentro de otra palabra no cuenta
    ],
)
def test_detectar_marca(textos: tuple[str | None, ...], esperado: str | None) -> None:
    assert detectar_marca(*textos) == esperado


@pytest.mark.parametrize(
    ("textos", "esperado"),
    [
        (("Palas de pádel", "lo que sea"), "pala"),
        ((None, "Protector pala Bullpadel"), "accesorio"),
        ((None, "Pala Bullpadel Hack + overgrip de regalo"), "pala"),
        ((None, "Zapatillas Joma Slam"), "zapatilla"),
        ((None, "Bote 3 pelotas Head Pro"), "pelotas"),
        ((None, "Paletero Nox AT10"), "paletero"),
        ((None, "Camiseta técnica"), "ropa"),
        (("Paletero Nox AT10 Team", "Palas y paleteros"), "paletero"),
        (("Nox AT10 Genius 18K", "Palas"), "pala"),
        (("Falda Adidas Club", "Textil mujer"), "ropa"),
        (("Polo Bullpadel Liria", None), "ropa"),
        (("Sudadera Siux Hoodie", None), "ropa"),
        ((None, "Algo raro"), None),
    ],
)
def test_detectar_categoria(textos: tuple[str | None, ...], esperado: str | None) -> None:
    assert detectar_categoria(*textos) == esperado


def test_coincide_seguimiento() -> None:
    assert coincide_seguimiento("Pala NOX AT10 Genius 18K 2026", "Nox AT10")
    assert not coincide_seguimiento("Pala Nox ML10 Pro Cup", "Nox AT10")
    assert coincide_seguimiento("Bullpadel Vértex 04 Hybrid", "Bullpadel Vertex 04")


def test_ean_valido() -> None:
    assert ean_valido("8435541234567") == "8435541234567"
    assert ean_valido(" 84355412 ") == "84355412"
    assert ean_valido("SX-PAL-01") is None
    assert ean_valido(None) is None


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("189.95", "189.95"),
        ("1.234,50 €", "1234.50"),
        ("99,9", "99.90"),
        (120, "120.00"),
        ("", None),
        ("abc", None),
    ],
)
def test_a_decimal(valor: object, esperado: str | None) -> None:
    assert a_decimal(valor) == (Decimal(esperado) if esperado else None)
