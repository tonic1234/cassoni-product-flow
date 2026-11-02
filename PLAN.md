# PLAN — Puesta en marcha del agente SEO de Cassoni

**Fecha:** 2-nov-2026 · **Repo:** `tonic1234/cassoni-product-flow` · **Rama:** `agent/puesta-en-marcha`

## 1. Qué es esto

Un agente que optimiza fichas de producto de `cassoni.com` (muebles de lujo, 13.079
fichas publicadas). Lee Google Search Console (sólo lectura), decide qué ficha vale la
pena tocar, y edita **dos campos y sólo dos**: el H1 (`name`) y la descripción larga
(`description`), incorporando keywords con la regla del cliente (`docs/REGLA-SEO-FICHAS.md`).
El meta title/description y los ALT siguen siendo del n8n: un solo escritor por campo.

## 2. Estado real medido (2-nov-2026, no lo que dice el README viejo)

| Pieza | Estado verificado |
|---|---|
| Suite de tests | **120 verdes** (`venv/bin/python -m pytest tests/ -q`) |
| GSC | Responde. Propiedad `sc-domain:cassoni.com` visible. Service account OK |
| WooCommerce | HTTP 200 en `https://cassoni.com`, `X-WP-Total=13079` publicados |
| LLM | DeepSeek oficial, `deepseek-flash`, `/models` 200 |
| DataForSEO | Credenciales presentes (no se gastó en esta medición) |
| Selector de trabajo | **NO EXISTE**: `cli.py` exige `--urls archivo`; la lista que se pidió al equipo SEO nunca llegó |
| Lectura de GSC | Lee **al revés**: `days=365`, `rowLimit=10` y la API ordena por clics → las consultas con mucha impresión y 0 clics (justo las oportunidades) quedan afuera |
| Keyword principal | Sale de `candidates[0]` por **volumen de DataForSEO**, no por oportunidad |
| Medición del efecto | **NO EXISTE**: se guarda el texto, pero no la posición/impresiones de partida ni una revisión posterior |

Conclusión: el motor de edición está terminado y testeado; lo que falta es que el sistema
**elija el trabajo solo y demuestre el efecto**. Eso es "poner en marcha".

## 3. Definición operativa de "en marcha"

1. Un comando (`--seleccionar N`) devuelve las N fichas con más oportunidad real de GSC,
   sin que nadie escriba una lista a mano.
2. Cada ficha editada guarda su **punto de partida** (posición, impresiones, clics y CTR
   de la consulta objetivo).
3. Un comando (`--revisar`) compara a 14/28 días y dice si subió, quedó igual o bajó.
4. Todo lo anterior queda en una DB de trazas y en `evidencia/` del repo, reproducible.
5. El repo se puede auditar de punta a punta: plan, decisiones, tests, salidas crudas y
   el comando exacto que reproduce cada número.

## 4. Unidades de trabajo (cada una con test en ROJO antes del código)

| # | Unidad | Qué resuelve | Tests obligatorios |
|---|---|---|---|
| U1 | `cassoni/selector.py` (nuevo, puro) | Convierte las filas de GSC en un lote priorizado; descarta ruido (pos>30 sin clics) | `test_selector.py`: filtro de producto, umbrales, elección de keyword por oportunidad, orden del lote, tope N |
| U2 | `cassoni/gsc.py` | Pagina el listado de páginas; consulta por página con 90 días y 200 filas ordenadas por impresiones | `test_gsc.py`: paginación, cuerpo enviado (dims/days/rowLimit), orden por impresiones |
| U3 | `cassoni/opportunities.py` + orquestador | La keyword principal es la de mayor oportunidad; el volumen desempata | `test_opportunities.py::test_elegir_principal_*`, `test_pipeline.py` |
| U4 | `cassoni/db.py` + `cassoni/revisar.py` | Punto de partida y revisión a 14/28 días con veredicto | `test_db.py`, `test_revisar.py`: migración idempotente, deltas, veredicto con umbral |
| U5 | `cassoni/cli.py` | `--seleccionar`, `--revisar`, `--preflight`; `--urls` deja de ser obligatorio | `test_cli.py`: argumentos, salida JSON del lote, dry-run por defecto |
| U6 | Repo auditable | `README`, `docs/{ARQUITECTURA,DECISIONES,OPERACION,AUDITORIA}.md`, `scripts/verify.sh`, CI | `verify.sh` en verde + `tests/test_docs.py` (links y comandos citados existen) |
| U7 | Corrida en seco real | Primer lote de 20 fichas procesado con evidencia y costo medido | `evidencia/<fecha>-lote-*.json` + resumen legible |

## 5. Reglas que NO se tocan

- GSC es **sólo lectura** (no existe función de escritura).
- Dry-run es el default; escribir exige `--write` y que el validador haya aprobado.
- El agente edita **H1 y descripción larga**. Nada más.
- Anti-canibalización determinista antes del LLM; no se descarta "a ojo".
- Los tests no se cambian para que pase una implementación. Si un test contradice la spec,
  manda la spec y se anota el porqué.

## 6. Decisiones pendientes del cliente (no bloquean la puesta en marcha)

1. **Marca en el H1**: la página ya renderiza "by X for Y" aparte; si se suma la marca al
   `name` se duplica visualmente. Hoy el agente la incluye porque la spec lo pide.
2. **Regla de 60 caracteres**: el documento la mezcla con el meta title, que escribe el n8n.
3. **Volumen contra calidad**: el piloto se corre en seco; el lote grande se decide con el
   costo real medido por ficha.
4. **Visibilidad del repo**: privado por defecto (contiene la regla del cliente y prompts).
   Si el cliente quiere auditar desde afuera, se le da acceso de lectura al repo, no una copia.

## 7. Cómo se cierra

`scripts/verify.sh` en verde + el lote en seco con evidencia + los tres comandos
(`--preflight`, `--seleccionar`, `--revisar`) corridos de verdad sobre datos reales.

---

## Bitácora del 2-nov-2026 (hallazgos medidos, no supuestos)

La puesta en marcha se hizo por tramos con tests antes del código. El piloto se corrió
contra la ficha real `cas-rug-club-sofa-01` de producción, en dry-run.

| # | Hallazgo | Cómo se detectó | Estado |
|---|---|---|---|
| 1 | Un rechazo del validador se guardaba y reportaba como `processed` | primer piloto: la consola decía `processed` con `"aprobado": false` | corregido (`rejected`, D-007) |
| 2 | `keyword_principal=""` no caía al default | el checklist pedía "falta la keyword principal" con el H1 correcto | corregido |
| 3 | El JSON incompleto del editor se aceptaba a medias | captura de la respuesta cruda del modelo | corregido (reintento con el faltante explícito) |
| 4 | `_rework` devolvía sólo `h1` y `description` → la 2da pasada se auto-rechazaba | piloto v2 | corregido (D-009) |
| 5 | El validador marcaba como inventadas medidas y colección que son atributos REALES de WooCommerce | piloto v3 + inspección del producto | corregido (D-008) |
| 6 | Los `issues` del rechazo no llegaban al editor: rehacía a ciegas | lectura del código de `_rework` | corregido |
| 7 | JSON truncado (`Unterminated string`) mataba la corrida; la excepción del validador tumbaba el lote | piloto v5 | corregido (reintento + `failed` por ficha) |

Lección de método: los siete aparecieron **corriendo el producto contra datos reales**,
no leyendo el código. La suite estaba en verde (120 tests) mientras los siete estaban
vivos. Un test de integración contra el destino real vale más que veinte unitarios del
helper.
