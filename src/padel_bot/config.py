"""Carga y validación de config.yaml."""

from __future__ import annotations

import os
import re
from decimal import Decimal
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, field_validator

TipoAdaptador = Literal["shopify", "woocommerce", "jsonld", "html", "playwright", "pendiente"]

_PATRON_ENV = re.compile(r"\$\{([A-Z0-9_]+)\}")


class Filtros(BaseModel):
    categorias: list[str] = []
    marcas: list[str] = []
    precio_max: Decimal | None = None
    descuento_min_pct: float = 30
    bajada_min_pct: float = 5
    bajada_historica_min_pct: float = 10
    diferencia_min_eur_entre_tiendas: Decimal = Decimal(15)


class Notificaciones(BaseModel):
    telegram_chat_id: str | None = None
    resumen_diario: bool = True

    @field_validator("telegram_chat_id", mode="before")
    @classmethod
    def _normalizar_chat_id(cls, v: object) -> str | None:
        # YAML convierte "12345" en int; el chat_id de Telegram se trata como texto
        return str(v) if v not in (None, "") else None


class Scraping(BaseModel):
    user_agent: str = "PadelOfertasBot/0.1"
    delay_segundos: float = 2.5
    timeout_segundos: float = 20
    ruta_db: str = "data/padel.db"
    max_ejecuciones_vacias: int = 3
    max_avisos_por_ejecucion: int = 40


class ConfigTienda(BaseModel):
    nombre: str
    nombre_visible: str | None = None
    adaptador: TipoAdaptador
    url_base: str
    activa: bool = True
    # Shopify
    coleccion: str | None = None
    # WooCommerce
    solo_ofertas: bool = True
    # JSON-LD
    sitemap: str | None = None
    filtro_urls: str | None = None
    urls_productos: list[str] = []
    # Comunes
    max_paginas: int = 20
    max_productos: int = 200

    @field_validator("url_base")
    @classmethod
    def _sin_barra_final(cls, v: str) -> str:
        return v.rstrip("/")

    @property
    def titulo(self) -> str:
        return self.nombre_visible or self.nombre


class Config(BaseModel):
    filtros: Filtros = Filtros()
    seguimiento: list[str] = []
    notificaciones: Notificaciones = Notificaciones()
    scraping: Scraping = Scraping()
    tiendas: list[ConfigTienda] = []

    def tienda(self, nombre: str) -> ConfigTienda | None:
        return next((t for t in self.tiendas if t.nombre == nombre), None)


def expandir_variables(texto: str) -> str:
    """Sustituye ${VAR} por su valor en el entorno (cadena vacía si no existe)."""
    return _PATRON_ENV.sub(lambda m: os.environ.get(m.group(1), ""), texto)


def cargar_config(ruta: str | Path = "config.yaml") -> Config:
    texto = expandir_variables(Path(ruta).read_text(encoding="utf-8"))
    return Config.model_validate(yaml.safe_load(texto) or {})
