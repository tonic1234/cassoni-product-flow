# Agente SEO — Cassoni

Optimiza fichas de producto de **cassoni.com** (13.079 publicadas) como lo haría el
equipo SEO: por cada ficha escribe un **H1** pensado en lo que la gente busca, elige
**1 a 3 keywords** que la ficha ya atrae o que nombran marca y tipo, y **reescribe la
descripción larga** con la estructura del SEO. Corre solo, como worker con cron: hasta
10 fichas por día, en horario hábil, con un panel de observabilidad y un reporte
diario. Mide el efecto de cada keyword a 14 y 28 días.

> **Para instalarlo en el VPS:** [docs/VPS.md](docs/VPS.md).
> **Cómo funciona por dentro:** [docs/COMO-FUNCIONA.md](docs/COMO-FUNCIONA.md).
> **Qué pidió el SEO y cómo se resolvió:** [docs/SEO-DEVOLUCIONES.md](docs/SEO-DEVOLUCIONES.md).

## Estado (17-nov-2026)

| Pieza | Estado |
|---|---|
| H1 por lo que la gente busca (regla del SEO, 17-nov) | ✅ en código; umbral pendiente de confirmar con el SEO |
| Keywords: Search Console + marca y tipo + genérica del material del H1 | ✅ en código, sin LLM |
| Descripción con la estructura del SEO (DeepSeek, con sus fichas como ejemplo) | ✅ 19 de 20 aprobadas en la última prueba |
| Validación: reglas en código + un segundo modelo como juez | ✅ frena datos inventados y keywords forzadas |
| Worker diario autónomo (`tools/agente_diario.py`) | ✅ probado de punta a punta en seco |
| Panel de observabilidad (`tools/panel.py`) | ✅ estático, se regenera después de cada corrida |
| Cron en el VPS | ⏳ por instalar ([docs/VPS.md](docs/VPS.md)) |
| Escritura en la tienda (`--write`) | ⛔ no ejecutada: el primer lote lo aprueba el SEO |
| Suite de tests | ✅ 429 verdes |

**Medido en las 10 fichas que resolvió el SEO** (`tools/evaluar_vs_seo.py`):
keywords del SEO que elige el agente 2 → 9 de 22; 2,1 keywords por ficha (SEO 2,2);
largo 118 → 96 palabras (SEO 86). Costo por ficha: ~US$ 0,005 de LLM y ~US$ 0,05 de
DataForSEO.

## En una ficha, paso a paso

1. **Lee** la ficha de WooCommerce: nombre, marca, ruta de categorías, atributos y
   descripción. Si ya fue escrita, la saltea.
2. **Tipo de producto** en inglés de EE. UU., por código (`wall sconce`, `bar stool`).
3. **H1**:
   - si el nombre ya se busca (≥ 1.000/mes, como «club sofa»), nombre + marca;
   - si no, nombre + **rasgo** + tipo + marca. El rasgo es el material que tienen
     todas las versiones y, entre esos, el más buscado («Cruise Teak Outdoor Sofa»).
   - En WooCommerce se escribe **sin la marca**: la tienda agrega «by {Marca}» con el
     logo del fabricante.
4. **Keywords**, decididas en código:
   - búsquedas de Search Console con impresiones (primero las variantes del nombre:
     «cruise couch», «shibari chairs»);
   - marca + tipo con volumen («nomon wall clock»);
   - una genérica solo si es del material que dice el H1 («glass dining table»).
5. **Redacta** DeepSeek con las fichas del SEO como ejemplo: apertura, 2 secciones,
   un dato para decidir la compra, medidas en pulgadas, un enlace a la categoría, 60 a
   110 palabras. Nada inventado: los números se controlan en código.
6. **Valida**: reglas en código y un segundo modelo; hasta 3 intentos con los motivos.
7. **Escribe** `name` y `description` solo con `--write` y aprobada.
8. **Mide** cada keyword a 14 y 28 días.

## Probarlo en cinco comandos

```bash
git clone https://github.com/tonic1234/cassoni-product-flow && cd cassoni-product-flow
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/python -m pytest -q                                   # tests, sin red
./venv/bin/python -m cassoni.cli --env prod --preflight          # conexiones, sin gastar LLM
./venv/bin/python tools/agente_diario.py --sin-horario           # una corrida en seco
```

Las credenciales van en `.env.prod` y `creds/` (nunca en git): ver
[docs/OPERACION.md](docs/OPERACION.md). En Windows: `PYTHONUTF8=1`.

## Lo que se mostró al SEO

| Página | Qué es |
|---|---|
| [docs/landing-v3/index.html](docs/landing-v3/index.html) | **Landing v3** que se intercambió con Alex (SEO): qué cambió, agente vs SEO en sus 10 fichas, 10 fichas nuevas y DeepSeek vs Claude. Se regenera con `tools/landing_v3.py`. |
| [docs/agente-vs-seo/index.html](docs/agente-vs-seo/index.html) | Las 10 fichas del SEO, lado a lado con el agente. |
| [docs/revision-seo/index.html](docs/revision-seo/index.html) | Página para calificar fichas (v3.2). |
| [docs/landing/index.html](docs/landing/index.html) | Landing v2 (4-nov), con los primeros resultados. |
| [docs/landing-cliente/](docs/landing-cliente/) | Informe que se mandó al cliente (julio). |

## Mapa del repo

```
cassoni/                el agente
  orchestrator.py         el recorrido de una ficha (precarga, selección, redacción, escritura)
  reglas_seo.py           reglas del SEO en código: H1 por volumen, keywords, genérica del H1
  criterio_seo.py         candidatas (Search Console + genéricas) y ejemplos del SEO
  redactor.py             prompt de redacción y controles en código
  validator.py            segundo modelo como juez
  h1.py                   tipo de EE. UU., modelo, nombre para WooCommerce
  scheduler.py            cupo diario, horario, reintentos, estado
  llm.py / costos.py      DeepSeek (o Claude por SDK de Anthropic) y costo por llamada
  dataforseo.py, gsc.py, woo.py, db.py
tools/
  agente_diario.py        EL WORKER: una corrida diaria + reporte + panel
  panel.py (+ plantilla)  panel de observabilidad estilo Dendra
  correr_lote.py          un lote en seco con su JSON de evidencia
  evaluar_vs_seo.py       parecido con las fichas del SEO
  armar_referencia_seo.py ejemplos del SEO a partir de su documento
  landing_v3.py, pagina_*.py, fotos_fichas.py   páginas para el SEO
  simulacion_*.py         probar otro modelo (o una persona) con las mismas entradas
docs/                   documentación (ver arriba) y páginas para el SEO
evidencia/              corridas, documento del SEO y referencia (referencia-seo.json la usa el agente)
tests/                  suite completa (sin red, con fakes)
```

## Límites declarados

- El agente **no** toca `short_description`, meta title/description ni ALT: son del
  n8n (un solo escritor por campo).
- Search Console es solo lectura.
- Si una ficha no tiene la marca cargada en WooCommerce, la tienda muestra el H1 sin
  «by»: el agente lo avisa.
- Pendiente con el SEO: el umbral de 1.000 búsquedas/mes para el H1; Rock sin «Marble»
  (la tapa también viene en madera); Steinway, cuyo volumen es el de la marca.
