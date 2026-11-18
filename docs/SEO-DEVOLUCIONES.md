# Devoluciones del SEO y cómo se resolvieron

Historial de lo que pidió el equipo SEO y qué cambió en el agente por eso. Cada punto
remite a la decisión (`DECISIONES.md`) y a la evidencia (`evidencia/`).

## 6-nov-2026 · Documento «Propuesta de H1 y descripciones»

Documento del SEO en Google Sheets, copiado en
`evidencia/2026-11-06-seo-referencia.xlsx` (y en CSV/JSON al lado). Tres pestañas:

1. **Propuesta de H1**: califica la v2 del agente en 10 fichas (2 Crítico, 4 Mal,
   3 Aceptable, 1 Bien) y propone la fórmula `{Nombre} + {material o rasgo} + {tipo en
   inglés de EE. UU.} + by {Marca}`.
2. **Cómo hacerlo por ficha**: para 10 fichas, el H1, las keywords que usaría, la URL
   de la categoría y **la descripción escrita por el SEO**.
3. **Competidores y fórmula**: Semrush; los que ganan búsquedas genéricas desde sus
   fichas ponen tipo y material en el H1.

**Qué cambió:** H1 con tipo y rasgo (D-024); la descripción se reescribe con la
estructura del SEO; las fichas del SEO son los ejemplos del agente
(`evidencia/referencia-seo.json`, armada con `tools/armar_referencia_seo.py`). Para
medir sin hacer trampa, cada ficha se procesa viendo las otras nueve, nunca la propia.

## 13-nov-2026 · Landing v3 enviada al SEO

`docs/landing-v3/index.html` (también en `entregas/` como zip, fuera del repo): agente
vs SEO en sus 10 fichas, 10 fichas nuevas elegidas al azar y DeepSeek vs Claude.

Dato que conviene saber al leerla: la lista de keywords del SEO salió de la que le
había propuesto la v2 (conservó 8 de sus keywords), así que la v2 coincide mucho en
keywords aunque sus oraciones estaban forzadas.

## 17-nov-2026 · Respuesta de Alex (SEO)

> La v3 va muy bien. Ya veo esos H1 con fórmula con más forma, aparte de los
> idénticos que se diferencian casi siempre por una palabra.
>
> Prioricemos sobre lo que la gente busca. Si el nombre del producto ya tiene volumen,
> como Club Sofa, basta con nombre y marca. Si no, se añade el rasgo más buscado, como
> «Marble» en Rock.
>
> Veo que DeepSeek le erra en la selección de keywords y Claude es Jesucristo en esto
> («leather table» en Dandy y «marble table» en Palatial). ¿Se sale del presupuesto
> dejárselo a los de Anthropic?
>
> Lo que funciona y va bien son las consultas que ya traen impresiones en Search
> Console y las de marca más tipo, como «nomon wall clock».

**Qué cambió (D-025):**

- **H1 por lo que la gente busca**, en código: si el nombre tiene ≥ 1.000
  búsquedas/mes, nombre + marca; si no, rasgo. 1.000 es el valor que cumple los dos
  ejemplos de Alex (club sofa 1.000 sí; rock coffee table 480 no). Configurable con
  `CASSONI_H1_UMBRAL_NOMBRE`.
- **Keywords decididas en código**, no por el modelo: Search Console con impresiones
  y marca + tipo, como dijo Alex. Las genéricas que fallaban («leather table»,
  «marble table») ya no salen; queda una genérica solo si es del material del H1.
- **DeepSeek solo redacta.** Con esto llega a 9 de 22 keywords del SEO (antes 7) sin
  los errores marcados, a ~US$ 0,005 de LLM por ficha. No hace falta pagar Claude para
  la selección; si se quiere probar, el agente ya acepta modelos `claude-*` por el SDK
  de Anthropic.
- Sobre «Claude es Jesucristo»: la simulación con Claude la hizo Claude Opus en la
  sesión de trabajo, no Sonnet por API, y ya conocía esos dos errores de DeepSeek al
  escribirla. Hay que tomarla como indicio, no como prueba.

**Pendiente de confirmar con Alex** (resuelto el 18-nov, ver abajo y D-026):

1. El umbral de 1.000 búsquedas/mes.
2. Rock: el agente no pone «Marble» porque la tapa también viene en madera (la regla
   evita opciones: sin ella salían «Wood» en Frog, que es de vidrio, y «Gold Leaf» en
   Tiffany). ¿Prefiere el más buscado aunque sea una de dos opciones?
3. Steinway: el volumen del nombre es el de la marca Steinway en general; el H1 quedó
   «Steinway Piano by Riva Mobili D'Arte».

## 17-nov-2026 · Cambio en la tienda: la marca como logo en el H1

La tienda ahora arma el H1 como `{name}` + enlace «by {Marca}» con el logo del
fabricante, y el `<title>` como «{name} by {Marca} | Cassoni». En WooCommerce el
`name` está sin marca («Club Sofa»). El agente escribe el `name` sin «by {Marca}»
(`h1.nombre_para_woo`), así no se duplica.

## 18-nov-2026 · Respuestas a los tres pendientes

1. Umbral de 1.000 búsquedas/mes: **queda**.
2. Rock: el H1 lleva la opción más buscada («Rock Marble Coffee Table») y la
   descripción habla de **las dos** tapas, con «marble coffee table» y «wood coffee
   table». Vale para toda ficha cuya parte principal viene en opciones.
3. Steinway: el volumen del nombre era el de la marca Steinway. Ahora no cuenta: va el
   rasgo («Mother-of-Pearl») y «piano steinway» no se toma como keyword.

Siguiente: tanda de 30 fichas nuevas elegidas al azar por código, en seco, para que el
SEO las revise sin que nadie las haya mirado antes (`scripts/tanda_seo.sh`).

