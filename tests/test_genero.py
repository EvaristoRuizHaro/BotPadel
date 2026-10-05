from __future__ import annotations

from decimal import Decimal

import pytest

from conftest import producto
from padel_bot.config import Filtros
from padel_bot.detector import pasa_filtros
from padel_bot.normalizar import es_ropa_de_hombre

FILTROS = Filtros(categorias=["ropa", "zapatilla"], genero_ropa="hombre")


@pytest.mark.parametrize(
    ("nombre", "hombre"),
    [
        ("Polo hombre PRO turquesa", True),
        ("POLO SIUX ERICA AZUL", True),
        ("Camiseta Babolat Crew Neck Tee Black", True),
        ("CAMISETA SIN MANGAS SIUX MUJER NEGRO", False),
        ("BULLPADEL AEREA Mujer Blanco PREMIER PADEL (Sudadera)", False),
        ("Camiseta Nox Team Niño Azul", False),
        ("Pantalón Adidas Club Junior", False),
        ("Sudadera Head Kids", False),
        ("SUJETADOR DEPORTIVO SIUX DIABLO PAULA", False),
        ("Falda deportiva pádel TEAM blanco", False),
        ("LEGGING SIUX FERAN BREW", False),
        ("Camiseta Tank-Top Pro Elite PadelPRO Mujer Negro", False),
        ("ADIDAS CLUB TEE W Blanco", False),
    ],
)
def test_es_ropa_de_hombre(nombre: str, hombre: bool) -> None:
    assert es_ropa_de_hombre(nombre) is hombre


def test_filtro_solo_afecta_a_la_ropa() -> None:
    mujer = producto(nombre="Camiseta Nox Mujer", categoria="ropa", precio=Decimal(20))
    zapas_mujer = producto(nombre="Zapatillas Nox Mujer", categoria="zapatilla", precio=Decimal(60))
    assert not pasa_filtros(mujer, FILTROS)
    assert pasa_filtros(zapas_mujer, FILTROS)
    assert pasa_filtros(mujer, Filtros(categorias=["ropa"]))  # sin la regla, pasa
