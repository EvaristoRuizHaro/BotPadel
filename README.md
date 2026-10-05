# padel-bot

Bot que revisa tiendas de pádel españolas, detecta **ofertas reales** (bajadas frente al
histórico propio, descuentos altos, mejor precio entre tiendas, vuelta a stock) y avisa por
Telegram. Contexto completo y decisiones de diseño en [`CLAUDE.md`](CLAUDE.md).

## Puesta en marcha

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   ·   Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

## Uso

```bash
# Fase 1: averiguar la plataforma de cada tienda (Shopify, Woo, PrestaShop...)
python -m padel_bot.investigar > investigacion.md

# Ejecutar (sin token de Telegram los avisos salen por consola)
python -m padel_bot.main --dry-run
python -m padel_bot.main --tienda padelnuestro --dry-run   # una sola tienda
python -m padel_bot.main resumen                           # resumen de las últimas 24 h
```

Para activar una tienda: en `config.yaml` cambia `adaptador: pendiente` por el que toque
(`shopify`, `woocommerce`, `jsonld`…) y pon `activa: true`.

## Telegram

1. Crea el bot con [@BotFather](https://t.me/BotFather) → te da el `TELEGRAM_BOT_TOKEN`.
2. Escríbele cualquier cosa al bot y abre
   `https://api.telegram.org/bot<TOKEN>/getUpdates` → el `chat.id` es tu `TELEGRAM_CHAT_ID`.
3. En local: variables de entorno (ver `.env.example`). En GitHub: *Secrets* del repo.

## GitHub Actions

- `scrape.yml`: 2 revisiones al día (9:13 y 20:13 en Madrid, horario de verano). La base SQLite se guarda en la rama `data`.
- `tests.yml`: ruff + pytest en cada push.

## Estructura

```
src/padel_bot/
├── main.py           # orquesta: scrapear → guardar → detectar → notificar
├── investigar.py     # fase 1: detecta plataforma/endpoints de cada tienda
├── config.py         # carga config.yaml (con ${VARIABLES})
├── models.py         # ProductoNormalizado, Oferta...
├── db.py             # SQLite: productos, precios, avisos, ejecuciones
├── normalizar.py     # marcas, categorías, EAN, precios
├── detector.py       # reglas de oferta + deduplicación
├── notificador.py    # formato y envío a Telegram
├── http.py           # cliente con robots.txt y límite por dominio
└── adaptadores/      # shopify, woocommerce, jsonld + tiendas/ específicas
```
