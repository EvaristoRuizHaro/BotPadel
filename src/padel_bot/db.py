"""Persistencia en SQLite: productos, histórico de precios y avisos enviados.

Los precios se guardan en céntimos (INTEGER) para poder comparar en SQL sin errores
de coma flotante.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from padel_bot.models import EstadoPrevio, Oferta, ProductoNormalizado

ESQUEMA = """
CREATE TABLE IF NOT EXISTS productos (
    id                INTEGER PRIMARY KEY,
    tienda            TEXT NOT NULL,
    id_externo        TEXT NOT NULL,
    nombre            TEXT NOT NULL,
    marca             TEXT,
    categoria         TEXT,
    url               TEXT NOT NULL,
    imagen            TEXT,
    ean               TEXT,
    primera_vez_visto TEXT NOT NULL,
    UNIQUE (tienda, id_externo)
);
CREATE INDEX IF NOT EXISTS idx_productos_ean ON productos (ean);

CREATE TABLE IF NOT EXISTS precios (
    id                   INTEGER PRIMARY KEY,
    producto_id          INTEGER NOT NULL REFERENCES productos (id),
    precio_cent          INTEGER NOT NULL,
    precio_original_cent INTEGER,
    disponible           INTEGER NOT NULL,
    fecha                TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_precios_producto ON precios (producto_id, fecha);

CREATE TABLE IF NOT EXISTS avisos_enviados (
    id            INTEGER PRIMARY KEY,
    producto_id   INTEGER NOT NULL REFERENCES productos (id),
    precio_cent   INTEGER NOT NULL,
    descuento_pct REAL NOT NULL DEFAULT 0,
    motivos       TEXT NOT NULL DEFAULT '',
    fecha         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_avisos_producto ON avisos_enviados (producto_id, fecha);

CREATE TABLE IF NOT EXISTS ejecuciones_tienda (
    id            INTEGER PRIMARY KEY,
    tienda        TEXT NOT NULL,
    num_productos INTEGER NOT NULL,
    error         TEXT,
    fecha         TEXT NOT NULL
);
"""


def a_cent(valor: Decimal | None) -> int | None:
    return None if valor is None else int((valor * 100).to_integral_value())


def de_cent(valor: int | None) -> Decimal | None:
    return None if valor is None else (Decimal(valor) / 100).quantize(Decimal("0.01"))


@dataclass(frozen=True)
class AvisoResumen:
    nombre: str
    tienda: str
    categoria: str | None
    url: str
    precio: Decimal
    descuento_pct: float


class BaseDatos:
    def __init__(self, ruta: str | Path) -> None:
        if str(ruta) != ":memory:":
            Path(ruta).parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(ruta)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        self.con.executescript(ESQUEMA)

    def cerrar(self) -> None:
        self.con.commit()
        self.con.close()

    def __enter__(self) -> BaseDatos:
        return self

    def __exit__(self, *_: object) -> None:
        self.cerrar()

    # --- Productos y precios -------------------------------------------------

    def guardar_producto(self, p: ProductoNormalizado, ahora: datetime) -> int:
        """Inserta o actualiza el producto y devuelve su id interno."""
        fila = self.con.execute(
            """
            INSERT INTO productos
                (tienda, id_externo, nombre, marca, categoria, url, imagen, ean, primera_vez_visto)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (tienda, id_externo) DO UPDATE SET
                nombre = excluded.nombre,
                marca = COALESCE(excluded.marca, productos.marca),
                categoria = COALESCE(excluded.categoria, productos.categoria),
                url = excluded.url,
                imagen = COALESCE(excluded.imagen, productos.imagen),
                ean = COALESCE(excluded.ean, productos.ean)
            RETURNING id
            """,
            (
                p.tienda,
                p.id_externo,
                p.nombre,
                p.marca,
                p.categoria,
                p.url,
                p.imagen,
                p.ean,
                ahora.isoformat(),
            ),
        ).fetchone()
        return int(fila["id"])

    def estado_previo(self, producto_id: int) -> EstadoPrevio:
        """Mínimo histórico, última disponibilidad y nº de observaciones hasta ahora."""
        agg = self.con.execute(
            "SELECT MIN(precio_cent) AS minimo, COUNT(*) AS n FROM precios WHERE producto_id = ?",
            (producto_id,),
        ).fetchone()
        ultimo = self.con.execute(
            "SELECT precio_cent, disponible FROM precios WHERE producto_id = ? "
            "ORDER BY fecha DESC, id DESC LIMIT 1",
            (producto_id,),
        ).fetchone()
        return EstadoPrevio(
            minimo_historico=de_cent(agg["minimo"]),
            ultimo_precio=None if ultimo is None else de_cent(ultimo["precio_cent"]),
            ultimo_disponible=None if ultimo is None else bool(ultimo["disponible"]),
            num_observaciones=int(agg["n"]),
        )

    def registrar_precio(self, producto_id: int, p: ProductoNormalizado, ahora: datetime) -> None:
        self.con.execute(
            "INSERT INTO precios (producto_id, precio_cent, precio_original_cent, disponible, "
            "fecha) VALUES (?, ?, ?, ?, ?)",
            (
                producto_id,
                a_cent(p.precio),
                a_cent(p.precio_original),
                int(p.disponible),
                ahora.isoformat(),
            ),
        )

    def precios_otras_tiendas(self, ean: str, tienda_excluida: str) -> list[Decimal]:
        """Último precio (disponible) del mismo EAN en el resto de tiendas."""
        filas = self.con.execute(
            """
            SELECT pr.precio_cent
            FROM productos p
            JOIN precios pr ON pr.id = (
                SELECT id FROM precios WHERE producto_id = p.id ORDER BY fecha DESC, id DESC LIMIT 1
            )
            WHERE p.ean = ? AND p.tienda <> ? AND pr.disponible = 1
            """,
            (ean, tienda_excluida),
        ).fetchall()
        return [de_cent(f["precio_cent"]) for f in filas]  # type: ignore[misc]

    # --- Avisos ----------------------------------------------------------------

    def ultimo_aviso(self, producto_id: int) -> Decimal | None:
        fila = self.con.execute(
            "SELECT precio_cent FROM avisos_enviados WHERE producto_id = ? "
            "ORDER BY fecha DESC, id DESC LIMIT 1",
            (producto_id,),
        ).fetchone()
        return None if fila is None else de_cent(fila["precio_cent"])

    def registrar_aviso(self, oferta: Oferta, ahora: datetime) -> None:
        self.con.execute(
            "INSERT INTO avisos_enviados (producto_id, precio_cent, descuento_pct, motivos, fecha) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                oferta.producto_id,
                a_cent(oferta.producto.precio),
                oferta.descuento_pct,
                ",".join(oferta.motivos),
                ahora.isoformat(),
            ),
        )
        self.con.commit()

    def avisos_desde(self, desde: datetime) -> list[AvisoResumen]:
        filas = self.con.execute(
            """
            SELECT p.nombre, p.tienda, p.categoria, p.url, a.precio_cent, a.descuento_pct
            FROM avisos_enviados a JOIN productos p ON p.id = a.producto_id
            WHERE a.fecha >= ?
            ORDER BY a.descuento_pct DESC
            """,
            (desde.isoformat(),),
        ).fetchall()
        return [
            AvisoResumen(
                f["nombre"],
                f["tienda"],
                f["categoria"],
                f["url"],
                de_cent(f["precio_cent"]),
                f["descuento_pct"],
            )  # type: ignore[arg-type]
            for f in filas
        ]

    # --- Salud de las tiendas ----------------------------------------------------

    def registrar_ejecucion(
        self, tienda: str, num_productos: int, error: str | None, ahora: datetime
    ) -> None:
        self.con.execute(
            "INSERT INTO ejecuciones_tienda (tienda, num_productos, error, fecha) "
            "VALUES (?, ?, ?, ?)",
            (tienda, num_productos, error, ahora.isoformat()),
        )
        self.con.commit()

    def tiene_historial(self, tienda: str) -> bool:
        """True si la tienda ya se revisó alguna vez con éxito (antes de esta ejecución)."""
        fila = self.con.execute(
            "SELECT 1 FROM ejecuciones_tienda WHERE tienda = ? AND num_productos > 0 LIMIT 1",
            (tienda,),
        ).fetchone()
        return fila is not None

    def ejecuciones_vacias_seguidas(self, tienda: str) -> int:
        """Cuántas de las últimas ejecuciones consecutivas devolvieron 0 productos."""
        filas = self.con.execute(
            "SELECT num_productos FROM ejecuciones_tienda WHERE tienda = ? "
            "ORDER BY fecha DESC, id DESC LIMIT 50",
            (tienda,),
        ).fetchall()
        racha = 0
        for f in filas:
            if f["num_productos"] > 0:
                break
            racha += 1
        return racha

    def commit(self) -> None:
        self.con.commit()
