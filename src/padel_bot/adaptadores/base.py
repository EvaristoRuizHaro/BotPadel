"""Interfaz común de todos los adaptadores de tienda."""

from __future__ import annotations

from abc import ABC, abstractmethod

from padel_bot.config import ConfigTienda
from padel_bot.http import ClienteHttp
from padel_bot.models import ProductoNormalizado


class Adaptador(ABC):
    """Cada tienda = un adaptador que devuelve productos ya normalizados."""

    def __init__(self, config: ConfigTienda, cliente: ClienteHttp) -> None:
        self.config = config
        self.cliente = cliente

    @property
    def tienda(self) -> str:
        return self.config.nombre

    @abstractmethod
    async def obtener_productos(self) -> list[ProductoNormalizado]:
        """Descarga y normaliza los productos (normalmente los de ofertas/outlet)."""
