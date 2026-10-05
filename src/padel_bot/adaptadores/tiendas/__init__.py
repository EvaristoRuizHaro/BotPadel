"""Adaptadores HTML/Playwright específicos de cada tienda.

Para añadir uno:
1. Guarda una muestra real del listado en tests/fixtures/<tienda>_listado.html
2. Crea adaptadores/tiendas/<tienda>.py con una clase que herede de Adaptador
3. Regístrala aquí:  ADAPTADORES_TIENDA["<tienda>"] = MiAdaptador
4. Añade su test en tests/ usando el fixture
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from padel_bot.adaptadores.base import Adaptador

ADAPTADORES_TIENDA: dict[str, type[Adaptador]] = {}
