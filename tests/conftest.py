from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from padel_bot.config import Config, Filtros
from padel_bot.db import BaseDatos
from padel_bot.models import ProductoNormalizado

FIXTURES = Path(__file__).parent / "fixtures"


def cargar_fixture(nombre: str) -> Any:
    ruta = FIXTURES / nombre
    texto = ruta.read_text(encoding="utf-8")
    return json.loads(texto) if ruta.suffix == ".json" else texto


@pytest.fixture
def db() -> BaseDatos:
    return BaseDatos(":memory:")


@pytest.fixture
def config() -> Config:
    return Config(
        filtros=Filtros(categorias=["pala"], marcas=["Bullpadel", "Nox"], precio_max=Decimal(250)),
        seguimiento=["Nox AT10"],
    )


def fecha(dia: int) -> datetime:
    return datetime(2026, 10, dia, 8, 0, tzinfo=UTC)


def producto(**cambios: Any) -> ProductoNormalizado:
    base: dict[str, Any] = {
        "tienda": "tienda_a",
        "id_externo": "1",
        "nombre": "Pala Bullpadel Vertex 04 2026",
        "marca": "Bullpadel",
        "categoria": "pala",
        "url": "https://tienda-a.example/vertex",
        "precio": Decimal("250.00"),
        "precio_original": None,
        "disponible": True,
        "ean": "8435541234567",
    }
    base.update(cambios)
    return ProductoNormalizado(**base)
