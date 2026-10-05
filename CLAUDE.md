# Bot de ofertas de pádel — Contexto del proyecto

## Objetivo
Bot que revisa periódicamente las ~20 tiendas de pádel más relevantes (mercado España), detecta **ofertas reales** (bajadas de precio, descuentos altos, outlets) y me las **notifica** (Telegram como canal principal).

El valor no está en "listar productos rebajados" (todas las tiendas tienen 500 rebajados siempre), sino en:
1. Detectar **bajadas de precio reales** respecto al histórico propio.
2. Filtrar según **mis intereses** (palas, zapatillas, marcas, presupuesto).
3. **No repetir** avisos del mismo producto/precio.

## Stack
- **Python 3.12**
- `httpx` (async) para peticiones; `selectolax` o `BeautifulSoup` para HTML
- `playwright` solo como fallback para webs que renderizan con JS
- **SQLite** (vía `sqlite3` o SQLModel) para productos e histórico de precios
- `pydantic` + `pyyaml` para configuración
- `python-telegram-bot` (o llamada directa a la API HTTP de Telegram) para avisos
- Programación: **GitHub Actions cron** (gratis) o cron en un VPS
- Tests: `pytest` con HTML/JSON de ejemplo guardados en `tests/fixtures/`

## Tiendas objetivo (v1)
> Las URLs y la plataforma de cada tienda **hay que verificarlas en la fase 1** (inspeccionar el HTML, `robots.txt` y si exponen endpoints JSON). Rellenar la columna "Plataforma" al hacerlo.

| # | Tienda | URL | Tipo | Plataforma |
|---|--------|-----|------|------------|
| 1 | Padel Nuestro | https://www.padelnuestro.com | Tienda especializada | Magento (sitemap_product.xml) |
| 2 | Zona de Padel | https://www.zonadepadel.es | Tienda especializada | PrestaShop |
| 3 | Time2Padel | https://www.time2padel.com/es/ | Tienda especializada | 403 antibot |
| 4 | Padel Market | https://www.padelmarket.com | Tienda especializada | Shopify ✅ activa |
| 5 | Padel Proshop | https://www.padelproshop.com | Tienda especializada | Shopify ✅ activa |
| 6 | StreetPadel | https://www.streetpadel.com | Tienda especializada | Shopify ✅ activa |
| 7 | Pádel Ibérico | https://www.padeliberico.es | Tienda especializada | 403 antibot |
| 8 | M1 Padel | https://www.m1padel.com | Tienda especializada | PrestaShop |
| 9 | Stock Padel | https://www.stockpadel.com/es/ | Tienda especializada (outlet) | PrestaShop |
| 10 | Area Padel | https://areapadel.com | Tienda especializada | PrestaShop |
| 11 | Keepadel | https://keepadel.com/es/ | Tienda especializada | PrestaShop (JSON-LD) |
| 12 | Padel Directo | (verificar) | Tienda especializada | ? |
| 13 | Decathlon (sección pádel) | https://www.decathlon.es | Gran superficie | 403 antibot |
| 14 | El Corte Inglés (pádel) | https://www.elcorteingles.es | Gran superficie | 403 antibot |
| 15 | Bullpadel (oficial/outlet) | https://www.bullpadel.com | Marca | 403 antibot |
| 16 | NOX (oficial/outlet) | https://www.noxsport.com | Marca | Shopify ✅ activa |
| 17 | Siux (oficial) | (verificar) | Marca | ? |
| 18 | Adidas Padel | (verificar) | Marca | ? |
| 19 | Head Padel | (verificar) | Marca | ? |
| 20 | Babolat Padel | (verificar) | Marca | ? |

Fuera de v1: **Amazon** (scraping contra sus términos; si se quiere, usar su API de afiliados) y **Wallapop** (otra lógica, segunda mano).

## Estrategia de extracción (de menos a más costosa)
Antes de escribir un scraper HTML, comprobar si la tienda expone datos estructurados:
1. **Shopify** → `/products.json?limit=250&page=N` y `/collections/<sale>/products.json`
2. **WooCommerce** → Store API `/wp-json/wc/store/v1/products?on_sale=true`
3. **PrestaShop / Magento / otros** → JSON-LD `schema.org/Product` en la ficha, o sitemap de productos
4. **HTML del listado de ofertas/outlet** con selectores CSS
5. **Playwright** solo si nada de lo anterior funciona

Cada tienda = un **adaptador** que implementa la misma interfaz y devuelve `ProductoNormalizado`. Los adaptadores genéricos (Shopify, Woo) se reutilizan configurando solo la URL.

## Modelo de datos
```python
class ProductoNormalizado(BaseModel):
    tienda: str
    id_externo: str          # SKU o id de la tienda
    nombre: str
    marca: str | None
    categoria: str | None    # pala | zapatilla | paletero | ropa | pelotas | accesorio
    url: str
    imagen: str | None
    precio: Decimal
    precio_original: Decimal | None   # precio tachado si existe
    disponible: bool
    ean: str | None          # clave para cruzar el mismo producto entre tiendas
```
Tablas SQLite:
- `productos` (tienda, id_externo, nombre, marca, categoria, url, ean, primera_vez_visto)
- `precios` (producto_id, precio, precio_original, disponible, fecha)
- `avisos_enviados` (producto_id, precio, fecha) → evita repetir avisos

## Qué cuenta como "oferta" (reglas configurables)
Se avisa si se cumple alguna, **y** pasa los filtros del usuario:
- **Bajada real**: precio actual ≤ mínimo histórico propio − X % (por defecto 10 %)
- **Ha bajado desde la última revisión**: precio actual ≤ último precio visto − X % (por defecto 5 %)
- **Descuento alto**: `(precio_original - precio) / precio_original ≥ 30 %` (desconfiar de precios tachados inflados: preferir la regla anterior cuando haya histórico)
- **Mejor precio entre tiendas**: mismo EAN/modelo, la tienda más barata con diferencia ≥ X €
- **Vuelve a estar disponible** un producto de la lista de seguimiento

No avisar de nuevo del mismo producto salvo que el precio baje otra vez.

**Funcionamiento acordado**: los avisos llegan **uno a uno** (un mensaje por oferta). La primera ejecución envía las ofertas que ya existen (descuento alto) y crea la base de precios; a partir de ahí el bot revisa las tiendas **2 veces al día** y solo avisa de novedades (bajadas, vuelta a stock, productos nuevos rebajados). Tope de `max_avisos_por_ejecucion` (40): lo que no cabe se envía en la siguiente revisión. Resumen diario desactivado por defecto.

## Configuración (`config.yaml`)
```yaml
filtros:
  categorias: [pala, zapatilla]
  marcas: [Bullpadel, Nox, Adidas, Siux, Babolat, Head]   # vacío = todas
  precio_max: 200
  descuento_min_pct: 30
  bajada_historica_min_pct: 10
seguimiento:            # productos concretos que quiero vigilar
  - "Nox AT10"
  - "Bullpadel Vertex 04"
notificaciones:
  telegram_chat_id: ${TELEGRAM_CHAT_ID}
  resumen_diario: true  # además de avisos instantáneos para ofertas top
tiendas:
  - nombre: padelnuestro
    adaptador: shopify     # o woocommerce | jsonld | html | playwright
    url_base: https://www.padelnuestro.com
    url_ofertas: ...
```
Secretos (`TELEGRAM_BOT_TOKEN`, etc.) solo por variables de entorno / GitHub Secrets, **nunca** en el repo.

## Estructura del repositorio
```
padel-bot/
├── CLAUDE.md
├── config.yaml
├── pyproject.toml
├── src/padel_bot/
│   ├── main.py              # orquesta: scrapear → guardar → detectar → notificar
│   ├── models.py
│   ├── db.py
│   ├── normalizar.py        # marcas, categorías, limpieza de nombres
│   ├── detector.py          # reglas de oferta
│   ├── notificador.py       # Telegram (formato del mensaje)
│   └── adaptadores/
│       ├── base.py          # interfaz Adaptador
│       ├── shopify.py
│       ├── woocommerce.py
│       ├── jsonld.py
│       └── tiendas/         # adaptadores HTML específicos
├── tests/
│   └── fixtures/
└── .github/workflows/scrape.yml
```

## Buenas prácticas de scraping (obligatorias)
- Respetar `robots.txt` y los términos de cada web.
- Máx. 1 petición cada 2–3 s por dominio; ejecución cada 6–12 h, no más.
- User-Agent identificable con un contacto.
- Sin login, sin saltarse captchas ni protecciones antibot: si una web bloquea, se desactiva esa tienda y se registra.
- Un adaptador que falla **no** tumba la ejecución: se registra el error y se sigue.
- Avisarme por Telegram si una tienda devuelve 0 productos varias ejecuciones seguidas (señal de que cambió el HTML).

## Formato del aviso en Telegram
```
🔥 Bullpadel Vertex 04 2026 — 189,95 € (antes 269,95 €, −30 %)
📉 Mínimo histórico (antes 215 €)
🏪 Padel Nuestro · ✅ En stock
🔗 <url>
```
Resumen diario: top 10 ofertas agrupadas por categoría.

## Fases
1. **Investigación**: para cada tienda, identificar plataforma, endpoint/selectores y `robots.txt`. Rellenar la tabla.
2. **MVP**: modelo + SQLite + adaptadores Shopify/Woo + 3 tiendas + aviso por Telegram. Ejecución manual.
3. **Detector** con histórico y deduplicación de avisos.
4. Ampliar a las 20 tiendas (adaptadores HTML/JSON-LD).
5. **GitHub Actions** 2 veces al día (9:13 y 20:13 hora de Madrid en verano) (la base SQLite se persiste como artifact o en una rama `data`).
6. Extras: cruce por EAN entre tiendas, comandos del bot (`/seguir <modelo>`, `/top`), mini web con gráfico de precios.

## Instrucciones para el asistente de código
- Responde y comenta el código en español; nombres de variables en español o inglés, pero consistentes.
- Antes de crear un adaptador, inspecciona la web real y guarda una muestra en `tests/fixtures/`.
- Cada adaptador con su test usando el fixture (sin peticiones reales en los tests).
- Cambios pequeños e incrementales; no reescribir módulos enteros sin pedirlo.
- Tipado completo y `ruff` para formato.
