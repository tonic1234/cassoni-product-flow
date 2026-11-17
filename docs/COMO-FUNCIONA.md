# Cómo funciona el agente (v5, 17-nov-2026)

Este documento es para quien lo instala o lo mantiene. Lo que pidió el SEO y por qué
está en [SEO-DEVOLUCIONES.md](SEO-DEVOLUCIONES.md); las decisiones una por una, en
[DECISIONES.md](DECISIONES.md) (D-023 a D-025 son las de esta versión).

## El worker

`tools/agente_diario.py` es lo único que corre el cron. Cada corrida:

```
lista.txt (SEO) ──┐
                  ├─► pendientes ─► Scheduler (cupo 10/día, 9-18 lun-vie, pausas) ─► Pipeline.process(url)
lista-propuestas ─┘        ▲                                                            │
  (si la lista se vacía,   │                                                            ▼
   propone desde GSC)      └──────── estado: cassoni_sched.json / _seco.json ◄── resultado
                                                                                         │
                     evidencia/diario/AAAA-MM-DD.json + .html  ◄────────────────────────┤
                     publico/index.html (panel)                ◄────────────────────────┘
                     lunes: medición a 14 y 28 días
```

- **Idempotente**: una ficha procesada no se vuelve a tocar; una rechazada o fallida se
  reintenta otro día y, al segundo intento, queda «abandonada» para que la mire el SEO.
- **En seco y escribiendo llevan estados separados**: probar en seco no marca nada como
  hecho para la corrida que escribe.
- **Nunca se cae por una ficha**: cualquier error queda registrado con su motivo y el
  lote sigue. Si DeepSeek tarda, se reintenta una vez.

## Una ficha (`cassoni/orchestrator.py`, modo `reglas`)

| Paso | Dónde | LLM |
|---|---|---|
| Leer la ficha de WooCommerce | `woo.py` | no |
| Tipo de producto en inglés de EE. UU. | `h1.tipo_ee_uu` | no |
| Búsquedas de Search Console de la ficha | `gsc.py` | no |
| Volumen del nombre, de las genéricas y de cada material | `dataforseo.py` (un solo pedido por lote, caché 30 días) | no |
| H1: nombre solo si ≥ 1.000/mes; si no, rasgos candidatos con volumen | `reglas_seo.h1_por_datos` | no |
| Keywords: Search Console + marca y tipo | `reglas_seo.elegir_keywords` | no |
| Redacción (H1 con rasgo + descripción) con las fichas del SEO como ejemplo | `redactor.py` | DeepSeek |
| Controles: números contra la ficha, keyword exacta, 1-2 secciones, un enlace, frases vacías, genérica = material del H1 | `redactor.controles`, `checklist.py` | no |
| Juez: datos inventados, keywords forzadas, tono | `validator.py` | DeepSeek |
| Escribir `name` (sin marca) y `description` | `woo.update_product` | no |

Las fichas del SEO que usa el redactor como ejemplo están en
`evidencia/referencia-seo.json`. **Ese archivo tiene que estar en el servidor.** Se
rearma con `tools/armar_referencia_seo.py` cuando el SEO resuelva fichas nuevas, y
cuantas más haya, mejor elige.

## Configuración (`.env.prod`)

| Variable | Valor | Para qué |
|---|---|---|
| `CASSONI_WC_BASE`, `CASSONI_WC_KEY`, `CASSONI_WC_SECRET` | — | WooCommerce |
| `CASSONI_GSC_SERVICE_ACCOUNT_FILE`, `CASSONI_GSC_SITE` | `sc-domain:cassoni.com` | Search Console (solo lectura) |
| `CASSONI_DFS_LOGIN`, `CASSONI_DFS_PASSWORD` | — | DataForSEO |
| `CASSONI_DFS_PRESUPUESTO_USD` | **1.50** | tope por corrida; con 0.30 la corrida se queda sin keywords |
| `CASSONI_LLM_BASE_URL`, `CASSONI_LLM_API_KEY` | DeepSeek | redacción y juez |
| `CASSONI_LLM_EDITOR_MODEL`, `CASSONI_LLM_VALIDATOR_MODEL` | `deepseek-flash` | con `claude-…` usa el SDK de Anthropic |
| `CASSONI_ANTHROPIC_API_KEY` | (opcional) | solo si se usa un modelo `claude-…` |
| `CASSONI_MODO_KEYWORDS` | `reglas` | `seo` = elige el LLM con ejemplos; `filtros` = v3.2 |
| `CASSONI_MODO_DESCRIPCION` | `reescritura` | `quirurgica` = v2 (una oración por keyword) |
| `CASSONI_H1_UMBRAL_NOMBRE` | `1000` | búsquedas/mes para que el nombre solo alcance |
| `CASSONI_FICHAS_POR_DIA` | `10` | cupo diario |
| `CASSONI_DB_URL` | `sqlite:///./cassoni.db` | estado, historial y caché de volúmenes |

## Costos medidos

Por ficha, en la prueba del 17-nov: **~US$ 0,005 de DeepSeek** (redacción + juez) y
**~US$ 0,04-0,05 de DataForSEO** (volúmenes en un pedido por lote, Search Console
gratis). Diez fichas por día: ~US$ 0,50/día.

## Herramientas para medir y mostrar

| Comando | Qué hace |
|---|---|
| `tools/correr_lote.py --urls X --out Y.json` | un lote en seco con todo el detalle |
| `tools/evaluar_vs_seo.py --lote Y.json` | parecido con las fichas que resolvió el SEO |
| `tools/panel.py --out publico --salud` | panel de observabilidad |
| `tools/pagina_revision_seo.py --lote "Nombre=Y.json" --out Z.html` | página para que el SEO califique |
| `tools/landing_v3.py ...` | la landing v3 (ver su docstring) |
| `tools/simulacion_exportar.py` / `simulacion_validar.py` | probar otro modelo con las mismas entradas y los mismos controles |
