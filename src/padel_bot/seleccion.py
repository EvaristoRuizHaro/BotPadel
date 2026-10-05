"""Qué ofertas se envían en cada ejecución.

Las tiendas tienen cientos de productos "rebajados" a la vez, así que no se puede mandar todo:
- Primera vez que se revisa una tienda: solo las N mejores de cada categoría; el resto se da
  por visto (se registra sin enviar) y a partir de ahí solo se avisa de cambios.
- Revisiones normales: hasta `max_total` avisos repartidos por turnos entre categorías,
  para que unas palas con mucho descuento no tapen a la ropa. Lo que no cabe se queda
  pendiente para la siguiente revisión.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import zip_longest

from padel_bot.models import Oferta


def _por_categoria(ofertas: list[Oferta]) -> list[list[Oferta]]:
    grupos: dict[str, list[Oferta]] = defaultdict(list)
    for o in sorted(ofertas, key=lambda o: o.descuento_pct, reverse=True):
        grupos[o.producto.categoria or "otros"].append(o)
    return list(grupos.values())


def repartir(ofertas: list[Oferta], max_total: int) -> tuple[list[Oferta], list[Oferta]]:
    """Intercala categorías (la mejor pala, la mejor prenda, la mejor zapatilla...)."""
    intercaladas = [
        o for ronda in zip_longest(*_por_categoria(ofertas)) for o in ronda if o is not None
    ]
    return intercaladas[:max_total], intercaladas[max_total:]


def seleccion_inicial(
    ofertas: list[Oferta], por_categoria: int
) -> tuple[list[Oferta], list[Oferta]]:
    """Devuelve (enviar, dar_por_vistas): las N mejores de cada categoría y el resto."""
    grupos = _por_categoria(ofertas)
    enviar = [o for g in grupos for o in g[:por_categoria]]
    resto = [o for g in grupos for o in g[por_categoria:]]
    enviar_intercaladas, _ = repartir(enviar, len(enviar))
    return enviar_intercaladas, resto
