"""Cliente HTTP "educado": respeta robots.txt y limita la frecuencia por dominio."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

log = logging.getLogger(__name__)


class BloqueadoPorRobots(Exception):
    """robots.txt no permite acceder a la URL."""


class ClienteHttp:
    def __init__(
        self,
        user_agent: str,
        delay_segundos: float = 2.5,
        timeout_segundos: float = 20,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.user_agent = user_agent
        self.delay = delay_segundos
        self.cliente = httpx.AsyncClient(
            headers={"User-Agent": user_agent, "Accept-Language": "es-ES,es;q=0.9"},
            timeout=timeout_segundos,
            follow_redirects=True,
            transport=transport,
        )
        self._locks: dict[str, asyncio.Lock] = {}
        self._ultima: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}

    async def __aenter__(self) -> ClienteHttp:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.cliente.aclose()

    async def _esperar_turno(self, dominio: str) -> None:
        espera = self._ultima.get(dominio, 0) + self.delay - time.monotonic()
        if espera > 0:
            await asyncio.sleep(espera)
        self._ultima[dominio] = time.monotonic()

    async def _robots_para(self, url: str) -> RobotFileParser | None:
        partes = urlsplit(url)
        origen = f"{partes.scheme}://{partes.netloc}"
        if origen not in self._robots:
            parser: RobotFileParser | None = RobotFileParser()
            try:
                await self._esperar_turno(partes.netloc)
                resp = await self.cliente.get(f"{origen}/robots.txt")
                if resp.status_code == 200:
                    parser.parse(resp.text.splitlines())  # type: ignore[union-attr]
                else:
                    parser = None  # sin robots.txt -> se permite todo
            except httpx.HTTPError as exc:
                log.warning("No se pudo leer robots.txt de %s: %s", origen, exc)
                parser = None
            self._robots[origen] = parser
        return self._robots[origen]

    async def permitido(self, url: str) -> bool:
        robots = await self._robots_para(url)
        return robots is None or robots.can_fetch(self.user_agent, url)

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        if not await self.permitido(url):
            raise BloqueadoPorRobots(url)
        dominio = urlsplit(url).netloc
        lock = self._locks.setdefault(dominio, asyncio.Lock())
        async with lock:
            for intento in range(2):
                await self._esperar_turno(dominio)
                try:
                    resp = await self.cliente.get(url, **kwargs)
                except httpx.TransportError:
                    if intento == 1:
                        raise
                    continue
                if resp.status_code >= 500 and intento == 0:
                    continue
                return resp
        raise RuntimeError("inalcanzable")

    async def get_json(self, url: str, **kwargs: Any) -> Any:
        resp = await self.get(url, headers={"Accept": "application/json"}, **kwargs)
        resp.raise_for_status()
        return resp.json()

    async def get_texto(self, url: str, **kwargs: Any) -> str:
        resp = await self.get(url, **kwargs)
        resp.raise_for_status()
        return resp.text
