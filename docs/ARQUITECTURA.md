# Arquitectura

## La cadena

```
                     ┌──────────────────────────────────────────────┐
                     │ GSC (sólo lectura, sc-domain:cassoni.com)    │
                     │  90 días · queries por página · 200 filas    │
                     └───────────────┬──────────────────────────────┘
                                     │ filas crudas
                     ┌───────────────▼──────────────────────────────┐
  SELECCIÓN          │ selector.py  (puro)                          │
  (qué se toca)      │  es_producto · filtrar_paginas ·             │
                     │  elegir_keyword · priorizar · lote_a_json    │
                     └───────────────┬──────────────────────────────┘
                                     │ lote: url + keyword + puntaje
                     ┌───────────────▼──────────────────────────────┐
  EDICIÓN            │ orchestrator.process(url)                    │
  (cómo se edita)    │  woo.get_product_by_slug                     │
                     │  gsc.queries_for_page                        │
                     │  opportunities.fusionar_gsc / ordenar        │
                     │  checklist.filtrar_canibalizacion            │
                     │  checklist.seleccionar_diversas              │
                     │  editor.edit  ──►  validador.pass_or_rework  │
                     └───────────────┬──────────────────────────────┘
                                     │ ficha aprobada / rechazada
                     ┌───────────────▼──────────────────────────────┐
  ESCRITURA          │ woo.update_product(name, description)        │
  (con gate)         │  sólo si cfg.write_enabled Y aprobado        │
                     └───────────────┬──────────────────────────────┘
                                     │
                     ┌───────────────▼──────────────────────────────┐
  MEDICIÓN           │ db.py (baseline_*) + revisar.comparar        │
                     │  a 14/28 días: subió / igual / bajó          │
                     └──────────────────────────────────────────────┘
```

## Módulos y contratos

| Módulo | Qué hace | Toca la red |
|---|---|---|
| `cassoni/config.py` | Lee `.env.<env>`, resuelve rutas relativas contra la carpeta del `.env` | no |
| `cassoni/gsc.py` | `pages()`, `queries_for_page()`, `top_keywords_for_url()` (compat) | GSC, lectura |
| `cassoni/selector.py` | Convierte filas de GSC en lote priorizado | no (puro) |
| `cassoni/opportunities.py` | Clasifica y puntúa; `elegir_principal`, `ordenar_candidatas`, `fusionar_gsc` | no (puro) |
| `cassoni/checklist.py` | Gate mecánico: longitudes, H2, palabras, conservación, anti-canibalización, diversidad | no (puro) |
| `cassoni/editor.py` | Prompt y contrato del editor; reintenta si el JSON viene incompleto | LLM |
| `cassoni/validator.py` | Mecánico + LLM; re-trabajo hasta 2 pases | LLM |
| `cassoni/woo.py` | Lectura de fichas y `update_product` con gate | WooCommerce |
| `cassoni/db.py` | Trazas, línea base y revisiones | SQLite/PostgreSQL |
| `cassoni/revisar.py` | Comparación a N días y veredicto | GSC (vía cliente) |
| `cassoni/cli.py` | `--preflight`, `--seleccionar`, `--urls`, `--revisar` | orquesta |

## Estados de una ficha

| Estado | Significado |
|---|---|
| `in_queue` | encolada, sin procesar |
| `processed` | edición aprobada **y** aplicada (o lista para aplicar en dry-run) |
| `rejected` | la edición no pasó el gate; **no se escribe** y se registran los motivos |
| `skipped` | no se procesa (draft, sin keywords, URL que no es ficha) |
| `failed` | error técnico (WooCommerce, GSC, LLM) |

`rejected` existe desde el 2-nov-2026: antes un rechazo del validador se guardaba como
`processed` y el lote nocturno habría reportado éxito sobre fichas que no se tocaron.

## Dónde vive cada dato

| Dato | Dónde | Se versiona |
|---|---|---|
| Credenciales | `.env.<env>` + `creds/` | **no** (gitignore) |
| Trazas de cada ficha | `cassoni.db` (SQLite) o PostgreSQL | no |
| Lote seleccionado | `evidencia/lote-*.json` | sí |
| Salidas de tests (RED/GREEN) | `evidencia/*-RED.txt`, `*-GREEN.txt` | sí |
| Regla del cliente | `docs/REGLA-SEO-FICHAS.md` | sí |

## Decisiones de seguridad

- GSC es sólo lectura: `gsc.py` no tiene ninguna función de escritura.
- El gate de escritura es doble: `cfg.write_enabled` (que exige `--write`) **y**
  `val["aprobado"]`. Un dry-run nunca llama a `update_product`.
- Un campo, un escritor: el agente toca `name` y `description`. `short_description`,
  meta title/description y ALT son del n8n.
