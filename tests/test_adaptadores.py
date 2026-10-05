from __future__ import annotations

from decimal import Decimal

from conftest import cargar_fixture
from padel_bot.adaptadores import shopify, woocommerce
from padel_bot.adaptadores.jsonld import parsear_jsonld, urls_de_sitemap


def test_shopify_parsea_productos() -> None:
    productos = shopify.parsear_productos(
        cargar_fixture("shopify_products.json"), "tienda_s", "https://tienda-s.example"
    )
    assert len(productos) == 3
    vertex, asics, grip = productos

    assert vertex.nombre == "Pala Bullpadel Vertex 04 2026"
    assert vertex.marca == "Bullpadel"
    assert vertex.categoria == "pala"
    assert vertex.precio == Decimal("189.95")
    assert vertex.precio_original == Decimal("269.95")
    assert vertex.ean == "8435541234567"
    assert vertex.url == "https://tienda-s.example/products/pala-bullpadel-vertex-04-2026"
    assert vertex.imagen == "https://cdn.shopify.com/vertex04.jpg"

    # Se elige la variante DISPONIBLE más barata, no la más barata a secas
    assert asics.precio == Decimal("105.00")
    assert asics.disponible is True
    assert asics.categoria == "zapatilla"
    assert asics.ean is None

    assert grip.categoria == "accesorio"
    assert grip.precio_original is None
    assert grip.ean is None  # "123" no es un EAN válido


def test_woocommerce_parsea_productos() -> None:
    productos = woocommerce.parsear_productos(
        cargar_fixture("woocommerce_products.json"), "tienda_w"
    )
    at10, paletero = productos

    assert at10.nombre == "Pala NOX AT10 Genius 18K Alum 2026 – Agustín Tapia"
    assert at10.marca == "Nox"
    assert at10.categoria == "pala"
    assert at10.precio == Decimal("179.95")
    assert at10.precio_original == Decimal("279.95")
    assert at10.ean == "8436043712345"

    assert paletero.categoria == "paletero"
    assert paletero.marca == "Siux"
    assert paletero.disponible is False
    assert paletero.precio_original is None  # regular == price → sin tachado


def test_jsonld_parsea_ficha() -> None:
    p = parsear_jsonld(cargar_fixture("jsonld_producto.html"), "tienda_j", "https://x/y")
    assert p is not None
    assert p.nombre == "Pala Head Extreme Pro 2025"
    assert p.marca == "Head"
    assert p.categoria == "pala"
    assert p.precio == Decimal("159.90")
    assert p.precio_original == Decimal("229.90")
    assert p.ean == "0726424999999"
    assert p.id_externo == "HD-225"
    assert p.imagen == "https://tienda.example/head.jpg"
    assert p.disponible is True


def test_jsonld_sin_producto_devuelve_none() -> None:
    assert parsear_jsonld("<html><body>nada</body></html>", "t", "u") is None


def test_urls_de_sitemap() -> None:
    assert urls_de_sitemap(cargar_fixture("sitemap_productos.xml")) == [
        "https://tienda.example/pala-head-extreme-pro-2025",
        "https://tienda.example/camiseta-head",
    ]
