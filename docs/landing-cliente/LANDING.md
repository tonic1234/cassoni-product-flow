# El documento que se le entregó al cliente

Esta carpeta guarda, tal cual se publicó, el informe técnico que Dendra le mandó a Cassoni
para explicar **qué se va a construir, con qué objetivo y cómo funciona**. Es la fuente de la
promesa: si el código no hace lo que dice acá, el problema es el código.

| | |
|---|---|
| Documento vivo | https://tarsterminal.duckdns.org/cassoni-report/ |
| Copia en este repo | `docs/landing-cliente/index.html` (fuente, 89 KB) |
| PDF entregado | `docs/landing-cliente/informe-cassoni.pdf` (606 KB) |
| Fecha del documento | julio 2026, con la sección "El flujo del agente" agregada el 18-sep-2026 |
| Repo de origen del sitio | `tonic1234/caddy-cassoni-report` |

## Objetivo, en las palabras del documento

> Cassoni opera una tienda WooCommerce con miles de productos de mobiliario de lujo. Cada
> producto tiene un H1 y una descripción larga ya redactados. El pipeline toma una lista de
> URLs, extrae la ficha completa vía API, busca keywords de alto volumen específicas del
> nicho, y las incorpora quirúrgicamente en los textos existentes sin romper el tono ni la
> redacción original. Todo queda registrado en una base de trazabilidad.

En una línea: **mejorar el SEO de cada ficha sin que se note que alguien la tocó.**

## Cómo está explicado (secciones del documento)

1. **Resumen ejecutivo** — objetivo, 4 indicadores (productos, costo asociado, campos
   optimizados, componentes).
2. **Flujo del pipeline** — diagrama de las 7 piezas de punta a punta.
3. **Cómo trabaja el agente, paso a paso** — entrada y extracción · datos reales · reglas, no
   opiniones · escribir y validar · gate y escritura · traza y ritmo · la prueba real sobre
   *Connor Sofa by Borzalino* · una glosa **EN SIMPLE** para lector no técnico.
4. **Cada pieza en detalle** — 01 extractor de URL a slug · 02 WooCommerce API · 03 Google
   Search Console · 04 DataForSEO (bulking por volumen) · 05 editor LLM · 06 validador ·
   07 base de trazabilidad.
5. **Proyección a 11.000 productos** — costo DataForSEO, rango de keywords, costo por producto.
6. **Fases del proyecto** — setup, extracción, keywords, LLM + validación, escala con cron.
7. **Ejecución anti-bot** — ventana horaria e intervalos variables para no parecer un bot.
8. **Tecnologías** y **por qué Python + cron y no n8n**.
9. **Comparativa de modelos** y **estimación de desarrollo**.

## Lo que el documento promete y hoy está distinto (para el auditor)

El informe es de julio y se escribió antes de tener el terreno medido. Estas diferencias son
reales y están resueltas en el código, pero **el documento del cliente no se actualizó**:

| Documento (jul-2026) | Medido / construido hoy | Dónde |
|---|---|---|
| "11.000 productos" | **13.079 publicados**, 14.495 con drafts | `evidencia/2026-11-02-conteo-woo.txt` |
| Gemini 2.5 Flash como LLM recomendado | **deepseek-flash** (API oficial), OpenCode de fallback | `docs/DECISIONES.md` |
| Costo proyectado ~USD 346 | **USD 0,0196 por ficha procesada**, medido con tokens reales | `docs/AUDITORIA.md` §costos |
| Entrada: una lista de URLs | **`--seleccionar N` arma el lote solo desde GSC** (90 días, orden por impresiones, ruido descartado) | `docs/ARQUITECTURA.md` |
| "incorpora keywords de alto volumen" | la principal se elige por **opportunity_score**, el volumen sólo desempata | `docs/DECISIONES.md` |
| Sin medición del efecto | cada ficha guarda `baseline_*` y `--revisar --days 14` compara y firma veredicto | `docs/OPERACION.md` |
| "Proyección ilustrativa" del costo DataForSEO | el costo real por ficha se registra en la DB (`llm_cost`, tokens in/out) | `docs/AUDITORIA.md` |

El resto de la promesa —siete piezas, gate determinista antes de escribir, base de
trazabilidad, ritmo humano— **está implementada y se reproduce con los comandos de
`docs/AUDITORIA.md`**.

## Cómo se audita este documento

```bash
# 1. La promesa escrita
sed -n '1,120p' docs/landing-cliente/index.html     # o abrir la URL viva

# 2. Lo que hace el código, pieza por pieza
sed -n '1,200p' docs/ARQUITECTURA.md

# 3. La prueba de que funciona, con salidas guardadas
sed -n '1,200p' docs/AUDITORIA.md
```
