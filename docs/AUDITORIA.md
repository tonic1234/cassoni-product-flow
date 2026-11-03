# Auditoría

Cada afirmación del repo con **el comando que la reproduce** y la salida guardada.
Si un número no coincide al correrlo, el repo está mal, no este documento.

Convención: todo se corre desde la raíz, con el venv del proyecto.

> **Antes de auditar el código, leer la promesa.**
> El informe técnico que se le entregó al cliente —objetivo, flujo paso a paso y las
> siete piezas explicadas— está en [`docs/landing-cliente/`](landing-cliente/LANDING.md)
> (con el `index.html` y el PDF tal como se enviaron) y vive en
> https://tarsterminal.duckdns.org/cassoni-report/.
> Ese documento es de julio de 2026: lo que cambió desde entonces está listado en
> `landing-cliente/LANDING.md` §"Lo que el documento promete y hoy está distinto".

---

## 1. El terreno está conectado

```bash
./venv/bin/python -m cassoni.cli --env prod --preflight
```

Salida real: `evidencia/2026-11-02-preflight.txt`

```json
{"gsc": {"ok": true, "sitios": ["sc-domain:cassoni.com"]},
 "woo": {"ok": true, "base": "https://cassoni.com"},
 "llm": {"ok": true, "http": 200, "modelo": "deepseek-flash"},
 "dataforseo": {"ok": true},
 "ok": true}
```

`--preflight` no gasta tokens: el LLM se prueba con `GET /models`.

## 2. El catálogo real

```bash
curl -s -u "$KEY:$SECRET" "https://cassoni.com/wp-json/wc/v3/products?per_page=1&status=publish" -D -
```

Salida real: `evidencia/2026-11-02-conteo-woo.txt`

- Publicados: **13.079**
- Totales (incluye drafts): **14.495**

## 3. La suite pasa

```bash
bash scripts/verify.sh
```

Cuatro pasos: sintaxis, tests, secretos, documentación ejecutable.
`VERIFY: VERDE` es la única prueba de "terminado" que vale en este repo.

## 4. El agente elige el trabajo solo (y rápido)

```bash
./venv/bin/python -m cassoni.cli --env prod --seleccionar 20 --days 90 --pausa 1
```

Salida real: `evidencia/2026-11-02-seleccion-20.txt` · lote: `evidencia/2026-11-02-lote-20.json`

- 20 fichas en **1m21s** (60 consultas a GSC de 90 días).
- Primera del lote: `club sofa`, posición 7,5, 1.360 impresiones, score 80,
  `https://cassoni.com/product/cas-rug-club-sofa-01/`.
- Criterio: sólo `/product/`, impresiones ≥ 50, se descarta posición > 30 sin clics.

## 5. La keyword principal es por oportunidad, no por volumen

```bash
./venv/bin/python -m pytest tests/test_opportunities.py -q -k ElegirPrincipal
./venv/bin/python -m pytest tests/test_pipeline.py -q -k oportunidad
```

- Caso de prueba: una consulta con 5.000 impresiones en posición 2 (ya rankea) vs
  otra con 300 en posición 12. Gana la segunda.
- RED/GREEN: `evidencia/2026-11-02-u3-principal-por-oportunidad-RED.txt` y `-GREEN.txt`.

## 6. La lectura de GSC está corregida

```bash
./venv/bin/python -m pytest tests/test_gsc.py -q
```

- Pide 90 días (no 365) y 200 filas (no 10).
- Ordena por impresiones antes de devolver (la API ordena por clics).
- RED/GREEN: `evidencia/2026-11-02-u1u2-selector-gsc-RED.txt` y `-GREEN.txt`.

## 7. Hay línea base y revisión

```bash
./venv/bin/python -m pytest tests/test_revisar.py -q
```

- Al editar se guardan `baseline_keyword/position/impressions/clicks/ctr/window/at`.
- `--revisar --days 14` compara la misma consulta y guarda el veredicto
  (`subio` / `igual` / `bajo` / `sin_datos` / `sin_baseline`).
- RED/GREEN: `evidencia/2026-11-02-u4-baseline-revision-RED.txt` y `-GREEN.txt`.

## 8. Un rechazo no se reporta como éxito

```bash
./venv/bin/python -m pytest tests/test_pipeline.py -q -k rechazada
```

Salida real del piloto (antes del fix): `evidencia/2026-11-02-piloto-1-ficha.txt`
mostraba `processed` con `"aprobado": false`. Después del fix:
`evidencia/2026-11-02-piloto-1-ficha-v3.txt` muestra `rejected` y el motivo.

## 9. El validador no inventa falsos positivos

```bash
./venv/bin/python -m pytest tests/test_validator.py -q
```

El piloto v2 marcó como "inventadas" las medidas `62"3/8` y `122"W` y la colección
`New Glamour Collection`: son atributos reales de WooCommerce (`Size`, `Collection`).
El validador ahora los recibe. Comparar `evidencia/2026-11-02-piloto-1-ficha-v3.txt`
(con los falsos positivos) contra `evidencia/2026-11-02-piloto-1-ficha-v4.txt`.

## 10. El re-trabajo conserva la ficha y dice por qué rechazó

```bash
./venv/bin/python -m pytest tests/test_validator.py -q -k "rework or rechaz"
```

Antes, `_rework` devolvía sólo `h1` y `description` (la segunda pasada se
auto-rechazaba) y los `issues` se descartaban sin llegar al editor.

---

## Lo que este repo NO demuestra

- **Que escribir en producción sea seguro**: no se ejecutó `--write` contra
  cassoni.com. El gate está probado con fakes, no con una escritura real aprobada.
- **Que el efecto sea positivo**: no hay revisión a 14/28 días con datos posteriores
  a una edición real. El mecanismo existe y está testeado; la medición, todavía no.
- **Que corra solo**: no hay cron ni timer instalado.
- ~~**El costo por ficha**: `llm_cost` no se llena; el número hay que tomarlo del
  panel del proveedor.~~ **Corregido el 3-nov-2026**: desde el commit `5591479`
  `orchestrator.py` llena `llm_cost` / `llm_tokens_in` / `llm_tokens_out` por ficha
  con los precios de `cassoni/costos.py`, y el total sale al final de la corrida.

---

## 11. El piloto de punta a punta (ficha real, dry-run)

```bash
echo "https://cassoni.com/product/cas-rug-club-sofa-01/" > piloto.txt
./venv/bin/python -m cassoni.cli --env prod --urls piloto.txt --batch 1 --db sqlite:///piloto.db
```

Salida real: `evidencia/2026-11-02-piloto-1-ficha-v7.txt` · registro: `evidencia/2026-11-02-piloto-1-ficha-v7.json`

| Campo | Antes | Después |
|---|---|---|
| H1 (`name`) | `Club Sofa` | `Rugiano Club Sofa` (17 car.) |
| Descripción larga | 54 palabras | 211 palabras, 2 H2 |
| Conservación del original | — | **1.0** (todas las oraciones intactas) |
| Keywords | — | principal `club sofa` + 2 secundarias |
| Validación | — | aprobada en 1 pase |
| Línea base | — | `club sofa`, pos 7,47, 1.360 impresiones, ventana 2026-08-04..2026-11-02 |

Y las corridas anteriores del mismo piloto quedan como evidencia de los siete defectos
corregidos: `-v1` (rechazo reportado como `processed`), `-v3` (falsos positivos de
datos inventados), `-v5` (JSON truncado que mató el proceso), `-v6` (conservación
medida mal).

## 12. La puerta

```bash
PY=./venv/bin/python bash scripts/verify.sh
# 198 passed
# ok: sin credenciales en lo versionado
# VERIFY: VERDE
```

---

## 13. Antes y después del filtro de relevancia (medido, misma ficha)

Con el lote de 3 (2-nov):

| Ficha | Antes (sin filtro) | Después (con filtro) |
|---|---|---|
| `cas-oak-sc_1019_chair-01` | rechazada: la principal era **`liberator lounger`** (otro mueble) | ✅ aprobada; descartó 1 consulta ajena |
| `cas-tal-cruise-teak-sofa-01` | ✅ aprobada | ✅ (sigue) |
| `cas-mor-pebble-rubble-sofa-01` | rechazada: la principal era **`geef foto`** (basura de GSC) | ✅ aprobada; descartó 3 consultas ajenas |

Salidas: `evidencia/2026-11-02-piloto-lote-3.txt` (antes) y
`evidencia/2026-11-02-piloto-lote-2-filtrado.txt` (después).
Registros: `evidencia/2026-11-02-piloto-lote-2-filtrado.json`.

Medición del después:

| Ficha | H1 | Palabras | Conservación |
|---|---|---|---|
| Cleopatra Chair | sin cambio (ya cumplía) | 10 → 163 | 1.0 |
| Pebble Sofa | `Pebble Rubble Sofa` → `Pebble Sofa by Moroso` | 190 → 249 | 0.89 |

Y el lote de 20 cambió su composición: `geef foto` desapareció y en esa ficha entró
`pebble sofa` (`evidencia/2026-11-02-seleccion-20-filtrada.txt`).
