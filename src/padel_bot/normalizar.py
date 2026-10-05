"""Normalización de marcas, categorías, nombres y EAN."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

# clave normalizada -> nombre canónico
MARCAS: dict[str, str] = {
    "bullpadel": "Bullpadel",
    "nox": "Nox",
    "adidas": "Adidas",
    "siux": "Siux",
    "babolat": "Babolat",
    "head": "Head",
    "wilson": "Wilson",
    "starvie": "StarVie",
    "black crown": "Black Crown",
    "varlion": "Varlion",
    "drop shot": "Drop Shot",
    "dropshot": "Drop Shot",
    "dunlop": "Dunlop",
    "kuikma": "Kuikma",
    "royal padel": "Royal Padel",
    "vibor-a": "Vibor-A",
    "vibora": "Vibor-A",
    "asics": "Asics",
    "joma": "Joma",
    "lok": "Lok",
    "oxdog": "Oxdog",
    "puma": "Puma",
    "mizuno": "Mizuno",
    "enebe": "Enebe",
    "softee": "Softee",
    "j'hayber": "J'hayber",
    "jhayber": "J'hayber",
    "endless": "Endless",
    "kombat": "Kombat",
    "akkeron": "Akkeron",
    "tecnifibre": "Tecnifibre",
}

# Dentro de un texto gana la palabra clave que aparece antes ("Protector pala" → accesorio).
CATEGORIAS: dict[str, tuple[str, ...]] = {
    "pala": ("pala", "palas", "racket", "rackets", "raqueta"),
    "zapatilla": ("zapatilla", "zapatillas", "shoes", "shoe", "calzado"),
    "paletero": ("paletero", "paleteros", "mochila", "mochilas", "bolsa", "bag", "trolley"),
    "pelotas": ("pelota", "pelotas", "balls", "bote"),
    "ropa": (
        "ropa",
        "textil",
        "apparel",
        "clothing",
        "camiseta",
        "camisetas",
        "t-shirt",
        "tshirt",
        "tee",
        "polo",
        "polos",
        "pantalon",
        "pantalones",
        "bermuda",
        "bermudas",
        "short",
        "shorts",
        "falda",
        "faldas",
        "skort",
        "vestido",
        "vestidos",
        "dress",
        "skirt",
        "sudadera",
        "sudaderas",
        "hoodie",
        "sweatshirt",
        "chaqueta",
        "chaquetas",
        "cortavientos",
        "jacket",
        "chandal",
        "chandals",
        "mallas",
        "leggings",
        "top",
        "tops",
        "sujetador",
        "tirantes",
        "calcetin",
        "calcetines",
        "socks",
    ),
    "accesorio": (
        "overgrip",
        "overgrips",
        "grip",
        "protector",
        "munequera",
        "munequeras",
        "gorra",
        "visera",
        "antivibrador",
        "cinta",
        "funda",
    ),
}


def normalizar_texto(texto: str | None) -> str:
    """Minúsculas, sin tildes y con espacios colapsados."""
    if not texto:
        return ""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sin_tildes.lower()).strip()


def tokens(texto: str | None) -> list[str]:
    return re.findall(r"[a-z0-9][a-z0-9'\-]*", normalizar_texto(texto))


def limpiar_nombre(nombre: str) -> str:
    return re.sub(r"\s+", " ", nombre).strip()


def detectar_marca(*textos: str | None) -> str | None:
    """Devuelve la marca canónica. El primer texto (vendor/brand) tiene prioridad."""
    for texto in textos:
        norm = normalizar_texto(texto)
        if not norm:
            continue
        if norm in MARCAS:
            return MARCAS[norm]
        # Claves más largas primero ("black crown" antes que otras más cortas)
        for clave in sorted(MARCAS, key=len, reverse=True):
            if re.search(rf"(?<![a-z0-9]){re.escape(clave)}(?![a-z0-9])", norm):
                return MARCAS[clave]
    return None


def _categoria_en(texto: str | None) -> str | None:
    toks = tokens(texto)
    mejor: tuple[int, str] | None = None
    for categoria, claves in CATEGORIAS.items():
        for i, tok in enumerate(toks):
            if tok in claves and (mejor is None or i < mejor[0]):
                mejor = (i, categoria)
                break
    return mejor[1] if mejor else None


def detectar_categoria(*textos: str | None) -> str | None:
    """Prueba los textos en orden y devuelve la primera categoría encontrada.

    Los adaptadores pasan primero el NOMBRE del producto (lo más fiable: "Paletero Nox...")
    y después la categoría/etiquetas de la tienda, que a veces son genéricas
    ("Palas y paleteros").
    """
    for texto in textos:
        if categoria := _categoria_en(texto):
            return categoria
    return None


def coincide_seguimiento(nombre: str, termino: str) -> bool:
    """True si todas las palabras del término aparecen en el nombre del producto."""
    toks_nombre = set(tokens(nombre))
    toks_termino = tokens(termino)
    return bool(toks_termino) and all(t in toks_nombre for t in toks_termino)


def ean_valido(valor: object) -> str | None:
    """Devuelve el EAN/GTIN si tiene pinta de serlo (8, 12, 13 o 14 dígitos)."""
    if valor is None:
        return None
    texto = re.sub(r"\s", "", str(valor))
    return texto if re.fullmatch(r"\d{8}|\d{12,14}", texto) else None


def a_decimal(valor: object) -> Decimal | None:
    """Convierte '1.234,50', '1234.50', 1234.5... a Decimal con 2 decimales."""
    if valor is None or valor == "":
        return None
    texto = str(valor).strip().replace("€", "").replace("\xa0", "").replace(" ", "")
    if "," in texto and "." in texto:
        # El último separador es el decimal
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(",", ".")
    try:
        return Decimal(texto).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
