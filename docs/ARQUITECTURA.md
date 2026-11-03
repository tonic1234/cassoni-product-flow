# Arquitectura (flujo v2 · 3-nov-2026)

## La cadena

```
  lista.txt (SEO, crece día a día)
        │  hasta 10 fichas/día · 9-18 lun-vie · pausas aleatorias   scheduler.py
        ▼
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ precarga del lote: GSC por ficha → UN pedido de volumen a DataForSEO     │
  │                    (caché 30 días en la base)            volumen.py      │
  └───────────────────────────────┬──────────────────────────────────────────┘
                                  ▼  por ficha                orchestrator.py
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ ¿ya escrita? → skipped (salvo --forzar)                                  │
  │ WooCommerce: nombre, marca, categorías, atributos, descripción           │
  │ H1 = "{Nombre} by {Marca}"                                h1.py (sin LLM)│
  │ candidatas de tres fuentes, todas con volumen de DataForSEO:             │
  │   GSC (la ficha ya aparece, pos 4-30)                                    │
  │   competencia: SERP "{Nombre} {Marca}" → 3 páginas por encima nuestro    │
  │     → ranked_keywords (top 20 de cada una)              competidores.py  │
  │   investigación: tipo × atributos → keyword_ideas      investigacion.py  │
  │ filtros: no cubierta por el H1 · de este producto · no informativa ·     │
  │   dificultad ≤ 60 · ≥ 50/mes · anti-canibalización → hasta 3 por         │
  │   potencial de clics                                     keywords.py     │
  │ editor LLM: UNA oración por keyword, anclada en la ficha    editor.py    │
  │ validador: reglas en código (keyword exacta, una oración por keyword,    │
  │   ≤ 4 palabras fuera de la ficha, sin medidas ni frases vacías, 80%      │
  │   conservado, HTML seguro) + LLM (tono, datos inventados)                │
  │            → hasta 2 pases                                validator.py   │
  └───────────────────────────────┬──────────────────────────────────────────┘
                                  ▼  solo con --write y aprobada
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ WooCommerce: name + description                               woo.py     │
  │ base: 3 keywords objetivo con línea base · applied · edited_at   db.py   │
  └───────────────────────────────┬──────────────────────────────────────────┘
                                  ▼  a 14 / 28 días
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ cada keyword: N días antes vs N días después (mismo largo)  revisar.py   │
  │ subió / igual / bajó / apareció                                          │
  └──────────────────────────────────────────────────────────────────────────┘
```

## Módulos y contratos

| Módulo | Qué hace | Toca la red |
|---|---|---|
| `cassoni/config.py` | Lee `.env.<env>`; rechaza `staging` apuntando a producción | no |
| `cassoni/gsc.py` | `queries_for_page(url, days | start/end)`, `pages()` | GSC, lectura |
| `cassoni/h1.py` | `h1_plantilla(nombre, marca)`: idempotente | no (puro) |
| `cassoni/keywords.py` | `elegir_keywords(...)`: la regla de las 3 keywords | no (puro) |
| `cassoni/volumen.py` | Volumen con caché; un pedido por lote | DataForSEO |
| `cassoni/competidores.py` | SERP → 3 competidores → lo que rankean (`ranked_keywords`); respaldo: leer sus títulos | DataForSEO (+ sitios públicos, robots.txt) |
| `cassoni/investigacion.py` | Semillas tipo × atributos para `keyword_ideas` | no (puro) |
| `cassoni/dataforseo.py` | volumen, SERP, `ranked_keywords`, `keyword_ideas`; costo, tope y errores de cuenta | DataForSEO |
| `cassoni/checklist.py` | Gate mecánico + `html_inseguro` + anti-canibalización + diversidad | no (puro) |
| `cassoni/editor.py` | Prompt del editor: solo la descripción larga | LLM |
| `cassoni/validator.py` | Mecánico + LLM; re-trabajo hasta 2 pases | LLM |
| `cassoni/woo.py` | Lectura de fichas y `update_product` con gate; errores → `WooError` | WooCommerce |
| `cassoni/db.py` | Trazas, keywords objetivo, caché de volumen, revisiones | SQLite/PostgreSQL |
| `cassoni/revisar.py` | Medición por keyword con ventanas iguales | GSC |
| `cassoni/scheduler.py` | Cupo diario, horario, reintentos con tope | orquesta |
| `cassoni/cli.py` | `--preflight`, `--urls`, `--scheduler`, `--revisar`, `--forzar` | orquesta |

## Estados de una ficha

| Estado | Significado |
|---|---|
| `in_queue` | encolada; solo existe mientras se procesa |
| `processed` | aprobada; `applied=1` si se escribió, `0` si fue en seco |
| `rejected` | el gate la frenó; **no se escribe**; motivo en `reason` |
| `skipped` | no corresponde (draft, ya editada, URL que no es ficha) |
| `failed` | error técnico; motivo en `reason` |

Toda salida del ciclo deja status y motivo: ninguna ficha queda colgada en `in_queue`.

## Dónde vive cada dato

| Dato | Dónde | Se versiona |
|---|---|---|
| Credenciales | `.env.<env>` + `creds/` | **no** (gitignore) |
| Trazas de cada ficha | `cassoni_processed_products` | no |
| Keywords objetivo + línea base | `cassoni_keyword_objetivo` | no |
| Caché de volumen | `cassoni_keyword_volume` | no |
| Revisiones | `cassoni_reviews` (una fila por keyword y por N) | no |
| Estado del goteo | `cassoni_sched.json` | no |

## Decisiones de seguridad

- GSC es sólo lectura: `gsc.py` no tiene ninguna función de escritura.
- `--env staging` no puede apuntar a la tienda real (`Config.validate`).
- Gate de escritura doble: `--write` **y** aprobación del validador.
- Idempotencia: una ficha escrita no se reescribe salvo `--forzar`.
- HTML seguro: la edición no puede agregar scripts, iframes, estilos, formularios,
  atributos de evento, URLs `javascript:`, ni enlaces o imágenes nuevas. El texto
  se escribe con claves de admin y WordPress no lo filtra.
- Competidores: se respeta `robots.txt`, se identifica el bot, y al LLM nunca le
  llega texto ajeno, solo keywords.
- Un campo, un escritor: el agente toca `name` y `description`. `short_description`,
  meta title/description y ALT son del n8n.
