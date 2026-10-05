"""Adaptadores + cliente HTTP con transporte simulado (sin red)."""

from __future__ import annotations

import asyncio
import json

import httpx

from conftest import cargar_fixture
from padel_bot.adaptadores import crear_adaptador
from padel_bot.config import ConfigTienda
from padel_bot.http import BloqueadoPorRobots, ClienteHttp

ROBOTS = "User-agent: *\nDisallow: /checkout\n"


def _cliente(manejador: httpx.MockTransport) -> ClienteHttp:
    return ClienteHttp("TestBot/1.0", delay_segundos=0, transport=manejador)


def test_shopify_pagina_y_respeta_robots() -> None:
    pedidas: list[str] = []
    productos = cargar_fixture("shopify_products.json")

    def manejar(req: httpx.Request) -> httpx.Response:
        pedidas.append(str(req.url))
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS)
        if req.url.path == "/collections/outlet/products.json":
            return httpx.Response(200, json=productos)
        return httpx.Response(404)

    cfg = ConfigTienda(
        nombre="s", adaptador="shopify", url_base="https://s.example/", coleccion="outlet"
    )

    async def correr() -> int:
        async with _cliente(httpx.MockTransport(manejar)) as cliente:
            return len(await crear_adaptador(cfg, cliente).obtener_productos())

    assert asyncio.run(correr()) == 3
    # 3 productos < 250 → una sola página
    assert pedidas == [
        "https://s.example/robots.txt",
        "https://s.example/collections/outlet/products.json?limit=250&page=1",
    ]


def test_woocommerce_solo_ofertas() -> None:
    def manejar(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        assert req.url.params["on_sale"] == "true"
        return httpx.Response(200, content=json.dumps(cargar_fixture("woocommerce_products.json")))

    cfg = ConfigTienda(nombre="w", adaptador="woocommerce", url_base="https://w.example")

    async def correr() -> int:
        async with _cliente(httpx.MockTransport(manejar)) as cliente:
            return len(await crear_adaptador(cfg, cliente).obtener_productos())

    assert asyncio.run(correr()) == 2


def test_robots_bloquea() -> None:
    def manejar(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="User-agent: *\nDisallow: /\n")

    async def correr() -> None:
        async with _cliente(httpx.MockTransport(manejar)) as cliente:
            await cliente.get("https://b.example/products.json")

    try:
        asyncio.run(correr())
    except BloqueadoPorRobots:
        pass
    else:
        raise AssertionError("debería haberse bloqueado")
