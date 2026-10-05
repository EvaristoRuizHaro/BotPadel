"""Busca tu TELEGRAM_CHAT_ID automáticamente.

Uso (desde la carpeta del proyecto):
    python scripts/obtener_chat_id.py

Te pedirá el token del bot (no lo guarda en ningún sitio). Después, escríbele cualquier
mensaje a tu bot en Telegram y el script te mostrará el chat ID y te mandará un mensaje
de prueba para confirmar que todo funciona.

Solo usa la librería estándar de Python: no hace falta instalar nada.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API = "https://api.telegram.org/bot{token}/{metodo}"
ESPERA_MAX_SEGUNDOS = 120


def llamar(token: str, metodo: str, **params: Any) -> Any:
    url = API.format(token=token, metodo=metodo)
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=35) as resp:
            datos = json.load(resp)
    except urllib.error.HTTPError as exc:
        datos = json.load(exc)
    if not datos.get("ok"):
        raise RuntimeError(datos.get("description", "error desconocido"))
    return datos["result"]


def chats_de(updates: list[dict[str, Any]]) -> dict[int, str]:
    chats: dict[int, str] = {}
    for u in updates:
        mensaje = u.get("message") or u.get("edited_message") or u.get("channel_post") or {}
        chat = mensaje.get("chat")
        if chat:
            nombre = chat.get("title") or " ".join(
                p for p in (chat.get("first_name"), chat.get("last_name")) if p
            )
            if chat.get("username"):
                nombre += f" (@{chat['username']})"
            chats[chat["id"]] = f"{nombre} [{chat.get('type')}]"
    return chats


def main() -> None:
    token = (
        sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TELEGRAM_BOT_TOKEN", "")
    ).strip() or input("Pega el token de tu bot (de @BotFather): ").strip()

    try:
        bot = llamar(token, "getMe")
    except RuntimeError as exc:
        sys.exit(f"❌ El token no es válido: {exc}")
    print(f"✅ Token correcto. Tu bot es @{bot['username']}")

    # Si el bot tuviera un webhook configurado, getUpdates no devolvería nada
    with contextlib.suppress(RuntimeError):
        llamar(token, "deleteWebhook")

    print(f"\n👉 Abre Telegram, busca @{bot['username']} y mándale cualquier mensaje (o /start).")
    print(f"   Esperando hasta {ESPERA_MAX_SEGUNDOS} s...\n")

    inicio = time.monotonic()
    chats: dict[int, str] = {}
    while not chats and time.monotonic() - inicio < ESPERA_MAX_SEGUNDOS:
        chats = chats_de(llamar(token, "getUpdates", timeout=30))
    if not chats:
        sys.exit("⏱️  No ha llegado ningún mensaje. Escríbele al bot y vuelve a ejecutar el script.")

    for chat_id, nombre in chats.items():
        print(f"🎯 TELEGRAM_CHAT_ID = {chat_id}   ← {nombre}")
        try:
            llamar(
                token,
                "sendMessage",
                chat_id=chat_id,
                text="✅ ¡Conectado! Aquí te llegarán las ofertas de pádel.",
            )
            print("   Te he mandado un mensaje de prueba por Telegram.")
        except RuntimeError as exc:
            print(f"   (No se pudo mandar el mensaje de prueba: {exc})")

    print("\nGuarda ese número en GitHub → Settings → Secrets and variables → Actions")
    print("como TELEGRAM_CHAT_ID (y el token como TELEGRAM_BOT_TOKEN).")


if __name__ == "__main__":
    main()
