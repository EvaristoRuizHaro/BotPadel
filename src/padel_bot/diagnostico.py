"""Diagnóstico: qué ve el bot en cada tienda y por qué descarta productos.

Uso:  python -m padel_bot.diagnostico [--tienda nombre]   (escribe diagnostico.md)

No guarda nada en la base de datos ni envía avisos.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path

from padel_bot.adaptadores import crear_adaptador
from padel_bot.config import Config, Filtros, cargar_config
from padel_bot.detector import descuento_pct
from padel_bot.http import ClienteHttp
from padel_bot.models import ProductoNormalizado
from padel_bot.normalizar import es_ropa_de_hombre, normalizar_texto


def motivo_descarte(p: ProductoNormalizado, f: Filtros) -> str:
    """Por qué este producto no pasaría los filtros ("" = sí pasa)."""
    if not p.disponible:
        return "sin stock"
    if f.categorias and p.categoria not in f.categorias:
        return "categoría"
    if f.marcas and normalizar_texto(p.marca) not in {normalizar_texto(m) for m in f.marcas}:
        return f"marca ({p.marca or '?'})"
    if f.genero_ropa == "hombre" and p.categoria == "ropa" and not es_ropa_de_hombre(p.nombre):
        return "mujer/niño"
    if f.precio_max is not None and p.precio > f.precio_max:
        return "precio > máx."
    if descuento_pct(p.precio, p.precio_original) < f.descuento_min_pct:
        return "descuento bajo"
    return ""


def informe_tienda(nombre: str, productos: list[ProductoNormalizado], config: Config) -> str:
    f = config.filtros
    lineas = [f"## {nombre} — {len(productos)} productos", ""]

    por_cat = Counter(p.categoria or "sin categoría" for p in productos)
    lineas.append("Por categoría: " + ", ".join(f"{c}: {n}" for c, n in por_cat.most_common()))

    sin_cat = [p.nombre for p in productos if not p.categoria][:10]
    if sin_cat:
        lineas.append("\nEjemplos sin categoría: " + " · ".join(sin_cat))

    for cat in f.categorias or sorted({p.categoria for p in productos if p.categoria}):
        del_tipo = [p for p in productos if p.categoria == cat]
        motivos = Counter(motivo_descarte(p, f) or "✅ PASA" for p in del_tipo)
        lineas += [
            f"\n### {cat} ({len(del_tipo)})",
            "Resultado: " + ", ".join(f"{m}: {n}" for m, n in motivos.most_common()),
            "",
            "| Producto | Marca | Precio | Antes | Dto. | Descarte |",
            "|---|---|---|---|---|---|",
        ]
        top = sorted(
            del_tipo, key=lambda p: descuento_pct(p.precio, p.precio_original), reverse=True
        )
        for p in top[:12]:
            pct = descuento_pct(p.precio, p.precio_original)
            lineas.append(
                f"| {p.nombre} | {p.marca or '?'} | {p.precio} | {p.precio_original or '—'} "
                f"| {pct:.1f} % | {motivo_descarte(p, f) or '✅'} |"
            )
    return "\n".join(lineas)


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--tienda")
    parser.add_argument("--salida", default="diagnostico.md")
    args = parser.parse_args()
    config = cargar_config(args.config)

    if args.tienda:
        tiendas = [t for t in config.tiendas if t.nombre == args.tienda]
    else:
        tiendas = [t for t in config.tiendas if t.activa and t.adaptador != "pendiente"]
    s = config.scraping
    partes = [
        "# Diagnóstico",
        f"Filtros: categorías {config.filtros.categorias}, marcas {config.filtros.marcas}, "
        f"precio máx. {config.filtros.precio_max}, descuento mín. "
        f"{config.filtros.descuento_min_pct} %",
    ]
    async with ClienteHttp(s.user_agent, s.delay_segundos, s.timeout_segundos) as cliente:
        for t in tiendas:
            print(f"Leyendo {t.titulo}...", flush=True)
            try:
                productos = await crear_adaptador(t, cliente).obtener_productos()
            except Exception as exc:
                partes.append(f"## {t.titulo}\n❌ Error: {exc!r}")
                continue
            partes.append(informe_tienda(t.titulo, productos, config))

    Path(args.salida).write_text("\n\n".join(partes) + "\n", encoding="utf-8")
    print(f"Guardado en {args.salida}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
