"""Modelos de datos compartidos por adaptadores, detector y notificador."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class ProductoNormalizado(BaseModel):
    """Producto tal y como lo devuelve cualquier adaptador, ya limpio."""

    tienda: str
    id_externo: str  # SKU o id de la tienda
    nombre: str
    marca: str | None = None
    categoria: str | None = None  # pala | zapatilla | paletero | ropa | pelotas | accesorio
    url: str
    imagen: str | None = None
    precio: Decimal
    precio_original: Decimal | None = None  # precio tachado si existe
    disponible: bool = True
    ean: str | None = None  # clave para cruzar el mismo producto entre tiendas


class Motivo(StrEnum):
    BAJADA_HISTORICA = "bajada_historica"
    DESCUENTO_ALTO = "descuento_alto"
    MEJOR_PRECIO = "mejor_precio"
    VUELVE_STOCK = "vuelve_stock"


class EstadoPrevio(BaseModel):
    """Lo que sabemos de un producto ANTES de la observación actual."""

    minimo_historico: Decimal | None = None
    ultimo_disponible: bool | None = None
    num_observaciones: int = 0


class Oferta(BaseModel):
    producto_id: int
    producto: ProductoNormalizado
    motivos: list[Motivo]
    minimo_previo: Decimal | None = None
    siguiente_precio_otra_tienda: Decimal | None = None
    nombre_tienda: str | None = None
    descuento_pct: float = Field(default=0.0, description="Descuento frente a la referencia")
