# Operación

## Requisitos

```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
cp .env.staging.example .env.staging   # completar credenciales (nunca en git)
cp .env.staging.example .env.prod      # idem, con la base de la tienda real
```

El service account de GSC va en `creds/gsc-service-account.json` (0600). Tiene que
tener la propiedad `sc-domain:cassoni.com` compartida como **Restringido**. El prefijo
`https://cassoni.com/` da 403: usar sólo `sc-domain`.

Las rutas relativas del `.env` se resuelven contra la carpeta del `.env`, no contra
el directorio desde el que se corre el comando.

### Staging nunca apunta a producción

`--env staging` con `CASSONI_WC_BASE=https://cassoni.com` **se rechaza** (pasaba: el
preflight del 2-nov corrió así, y un `--write` habría escrito en la tienda real).
Para leer producción en seco se usa `--env prod`, que es dry-run por defecto. Los
hosts de producción se configuran con `CASSONI_PROD_HOSTS` (por defecto
`cassoni.com,www.cassoni.com`).

## El flujo del día

1. SEO agrega URLs al final de `lista.txt` (una por línea, `#` = comentario).
2. El agente toma las pendientes, **hasta 10 por día**, en horario hábil y con
   pausas aleatorias.
3. Cada ficha: H1 `{Nombre} by {Marca}` + 3 keywords que faltaban en la
   descripción larga. Si se escribió, no se vuelve a tocar.

```bash
# 1) ¿está todo conectado? No gasta LLM.
./venv/bin/python -m cassoni.cli --env prod --preflight

# 2) probar la lista en seco (no toca el sitio)
./venv/bin/python -m cassoni.cli --env prod --urls lista.txt --batch 10

# 3) el goteo diario, escribiendo de verdad
./venv/bin/python -m cassoni.cli --env prod --urls lista.txt --write --scheduler

# 4) medir el efecto de cada keyword
./venv/bin/python -m cassoni.cli --env prod --revisar --days 14
./venv/bin/python -m cassoni.cli --env prod --revisar --days 28

# rehacer una ficha ya escrita (por defecto se saltea)
./venv/bin/python -m cassoni.cli --env prod --urls una.txt --write --forzar
```

`--seleccionar N` sigue disponible para que el agente *proponga* fichas desde GSC,
pero la lista que manda es la de SEO.

## Cron (no instalado todavía)

Correrlo varias veces en el día es seguro: el cupo diario y el estado viven en
`cassoni_sched.json`. Ejemplo para el servidor:

```cron
# lun-vie, cada hora de 9 a 17: procesa lo que falte del cupo del día
0 9-17 * * 1-5  cd /root/cassoni-agent && ./venv/bin/python -m cassoni.cli --env prod --urls lista.txt --write --scheduler >> logs/agente.log 2>&1
# lunes 8:00: medición semanal a 14 y 28 días
0 8 * * 1       cd /root/cassoni-agent && ./venv/bin/python -m cassoni.cli --env prod --revisar --days 14 >> logs/revisar.log 2>&1
```

Recomendado: correrlo con un usuario sin privilegios en vez de `root`.

## Qué mirar en la salida

```
  ✓ processed https://cassoni.com/product/cas-cprn-pedro-sofa-01/
       H1 → Pedro Sofa by Cassoni
       keywords → leather chesterfield (1900), pedro modular (90), tufted back (s/d)
       (escrita)
Resultados: {'processed': 8, 'rejected': 1, 'skipped': 1}
Costo LLM: US$ 0.1600 · 24 llamadas · ...
Costo DataForSEO: US$ 0.0750
```

| Estado | Qué significa | Qué pasa mañana |
|---|---|---|
| `processed` | aprobada; escrita con `--write` (o lista para escribir en seco) | hecha |
| `rejected` | el validador la frenó; **no se escribe**; motivo en `reason` | se reintenta 1 vez más, después queda *abandonada* |
| `skipped` | no corresponde (draft, ya editada, URL que no es ficha) | hecha |
| `failed` | error técnico (WooCommerce, GSC, LLM); motivo en `reason` | se reintenta 1 vez más |

Las abandonadas quedan en `cassoni_sched.json` → `abandonadas` para que SEO las mire.

## Credenciales y variables

| Variable | Para qué | Por defecto |
|---|---|---|
| `CASSONI_WC_BASE/KEY/SECRET` | WooCommerce (lectura + escritura de productos) | — |
| `CASSONI_GSC_SERVICE_ACCOUNT_FILE`, `CASSONI_GSC_SITE` | GSC, sólo lectura | `sc-domain:cassoni.com` |
| `CASSONI_DFS_LOGIN/PASSWORD` | DataForSEO: volumen + resultados orgánicos | — |
| `CASSONI_DFS_LOCATION` / `CASSONI_DFS_LANGUAGE` | mercado de DataForSEO | `2840` (EE.UU.) / `en` |
| `CASSONI_DFS_MIN_VOLUMEN` | volumen mínimo de una keyword | `50` |
| `CASSONI_DFS_COMPETIDORES` | `siempre` o `si_faltan`: cuándo pedir lo que rankea la competencia | `siempre` |
| `CASSONI_DFS_PRESUPUESTO_USD` | tope de gasto de DataForSEO por corrida (`0` = sin tope) | `0` |
| `CASSONI_DFS_CACHE_DIAS` | vigencia de la caché de volumen | `30` |
| `CASSONI_FICHAS_POR_DIA` | cupo diario del scheduler | `10` |
| `CASSONI_PROD_HOSTS` | hosts que `--env staging` no puede usar | `cassoni.com,www.cassoni.com` |
| `CASSONI_LLM_*` | editor y validador | — |

`bash scripts/verify.sh` falla si aparece una credencial en texto plano en el repo.

## Costos

| Pedido a DataForSEO | Costo | Estado |
|---|---|---|
| Volumen (Google Ads), hasta 1.000 keywords | US$ 0,09 | medido |
| Búsqueda orgánica (competidores) | US$ 0,002 | medido |
| `ranked_keywords`, por página de competidor (3 por ficha) | ~US$ 0,03 | **estimado** |
| `keyword_ideas`, una por ficha | ~US$ 0,03 | **estimado** |

Por ficha, estimado: **US$ 0,06-0,12** → ~US$ 1 por día a 10 fichas. El costo real
lo da `tools/probar_dataforseo.py` antes de la primera corrida; si hace falta se
baja a 2 competidores o a menos resultados por pedido.

El LLM se mide por ficha (`llm_tokens_in/out`, `llm_cost`): ~US$ 0,01-0,02 por ficha
con `deepseek-flash`. La corrida imprime el total de los dos.

**Antes de cualquier corrida con DataForSEO**:

```bash
./venv/bin/python tools/probar_dataforseo.py --env prod --url https://cassoni.com/product/<slug>/
```

Muestra el saldo, hace una consulta de cada tipo con una ficha, el costo real de
cada una y una muestra de lo que devuelve. Si la cuenta no puede operar (sin
saldo, sin verificar, pausada) lo dice y no gasta.

## Cuando algo falla

| Síntoma | Causa más probable | Qué hacer |
|---|---|---|
| `Configuración inválida ... apunta a PRODUCCIÓN` | `.env.staging` con la base real | usar `--env prod` o una base de staging |
| `Configuración inválida ... CASSONI_*` | `.env` incompleto | completar y correr `--preflight` |
| GSC `403` | se usó `https://cassoni.com/` como sitio | usar `sc-domain:cassoni.com` |
| `skipped: ya editada` | la ficha ya se escribió | es lo esperado; `--forzar` si hay que rehacerla |
| Muchas `processed` con "solo H1" | ninguna keyword con volumen falta en la descripción | revisar `selection_reason` en la DB |
| `rejected` por HTML | la edición agregó un enlace, script o imagen | el gate funciona; no se escribe |
| `failed: LLM` | cuota, clave o timeout del proveedor | `--preflight` (ping a `/models`) |
| `failed: escritura WooCommerce` | clave sin permiso de escritura o caída | pedir clave read+write / reintentar |
| `ATENCIÓN: DataForSEO no pudo operar` | sin saldo (402), cuenta sin verificar (403) o pausada (40201) | revisar la cuenta en app.dataforseo.com |
| Muchas fichas "solo H1" | ninguna keyword nueva supera 50/mes | normal en productos de nicho; revisar `selection_reason` |

## Muestra para validar con el cliente

```bash
./venv/bin/python -m cassoni.cli --env prod --urls muestra.txt --batch 10 --db sqlite:///muestra.db
./venv/bin/python tools/exportar_muestra.py --db sqlite:///muestra.db --out muestra.json
./venv/bin/python tools/generar_muestra.py --json muestra.json --out index.html
```
