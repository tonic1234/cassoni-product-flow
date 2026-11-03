# Decisiones (ADR cortos)

Cada decisión con su fecha, su motivo y lo que se descartó. Si una decisión se
revierte, se agrega otra entrada; no se borra la anterior.

---

## D-001 · GSC sólo lectura
**2-nov-2026 · vigente desde el inicio**
El cliente no pidió nunca escribir en Search Console y un error ahí es
irreversible. `gsc.py` no expone ninguna función de escritura; el scope del
service account es `webmasters.readonly`.

---

## D-002 · El agente edita H1 y descripción larga, nada más
**18-sep-2026 · decisión de Antonio, textual: "el agente solo tiene que hacer h1 y
long description"**
`short_description`, meta title/description y ALT siguen siendo del n8n. Un solo
escritor por campo evita que dos procesos se pisen. `update_product()` acepta
`short_description=None` = no tocar.

---

## D-003 · La keyword principal se elige por OPORTUNIDAD, no por volumen
**2-nov-2026 · corrige el criterio anterior**
Antes: `candidates[0]` ordenado por volumen de DataForSEO. El problema: una consulta
con 5.000 impresiones en posición 2 ya está rankeando; no hay nada que ganar. La que
está en posición 12 con 300 impresiones sí. Ahora manda `opportunity_score` y el
volumen desempata. Cuando no hay datos de GSC (sólo volumen), se respeta el orden
viejo: la degradación está probada.

---

## D-004 · GSC se lee con 90 días y 200 filas, ordenado por impresiones
**2-nov-2026 · corrige un error de lectura**
La API ordena por clics. Con `rowLimit=10` las consultas con muchas impresiones y
cero clics —las oportunidades— quedaban afuera. Medido en la auditoría del 13-oct:
en `cas-ra-quartz-table-02`, 8 consultas con ≥150 impresiones quedaban fuera del
top-10.

---

## D-005 · El trabajo lo elige el sistema, no una lista a mano
**2-nov-2026**
El pipeline exigía `--urls archivo` y la lista que se pidió al equipo SEO el 31-ago
nunca llegó: el agente no podía arrancar solo. `--seleccionar N` arma el lote desde
GSC. Se descartó depender de una planilla externa: se desactualiza y nadie sabe qué
criterio usó.

---

## D-006 · La diversidad de palabras respeta la oportunidad
**2-nov-2026 · corrige una interacción**
`seleccionar_diversas` ordenaba por volumen para elegir una keyword por palabra
compartida, y revertía en silencio la elección por oportunidad hecha un paso antes.
Ahora ordena por `(opportunity_score, volume)`.

---

## D-007 · Una edición rechazada se registra como `rejected`, nunca como `processed`
**2-nov-2026 · hallazgo del primer piloto real**
El pipeline devolvía `processed` con `aprobado: false` y guardaba `processed` en la
DB, porque en dry-run `applied` se ponía en True sin mirar la validación. En un lote
nocturno eso es un reporte de éxito falso. Ahora `processed` exige aprobado **y**
aplicado.

---

## D-008 · El validador ve los atributos oficiales de la ficha
**2-nov-2026 · hallazgo del piloto**
El validador marcó como "inventadas" las medidas `62"3/8` y `122"W` y la colección
`New Glamour Collection`. Todas son atributos reales de WooCommerce (`Size`,
`Collection`). Sin los atributos, el validador produce falsos positivos y rebota
fichas correctas. Ahora recibe los mismos datos que el editor.

---

## D-009 · El re-trabajo conserva la ficha completa
**2-nov-2026 · hallazgo del piloto**
`Validator._rework` devolvía sólo `h1` y `description`; la segunda pasada se
auto-rechazaba con "falta la keyword principal" y "hay 0 secundarias" porque los
había borrado el propio validador.

---

## D-010 · Punto de partida y revisión obligatorios
**2-nov-2026**
Cada ficha editada guarda posición, impresiones, clics y CTR de su consulta objetivo
(`baseline_*`). Sin eso no se puede afirmar que la edición sirvió. `--revisar` mide a
14/28 días y guarda el veredicto en `cassoni_reviews`.

---

## Pendientes de decisión del cliente

1. **Marca en el H1**: la página ya renderiza "by X for Y" aparte. Sumar la marca al
   `name` la duplica visualmente. Hoy el agente la incluye porque la spec lo pide.
2. **60 caracteres**: el documento del cliente mezcla el H1 con el meta title, que
   escribe el n8n. Son dos campos distintos con dos dueños distintos.
3. **150 palabras en fichas de 55**: el 90% de las descripciones reales no llega a
   150 palabras y muchas no tienen atributos suficientes para expandir sin agregar
   texto genérico. Hay que decidir: ¿se permite texto de categoría, se baja el
   mínimo, o no se tocan esas fichas?

---

## D-011 · H1 por plantilla: `{Nombre} by {Marca}`
**3-nov-2026 · decisión del equipo SEO**
El H1 deja de ser una keyword elegida por el LLM. Es el nombre del producto más
el fabricante, siempre con la misma estructura, para dar consistencia visual. Lo
arma `cassoni/h1.py` sin LLM y se escribe en el campo `name`. Reemplaza la regla
"H1 ≤ 60 con la keyword principal exacta" (D-003 queda sin efecto para el H1).
Descartado: dejar que el LLM proponga el H1 (varía entre fichas).

---

## D-012 · Tres keywords que NO están en la descripción, con volumen
**3-nov-2026 · decisión del equipo SEO**
GSC trae las consultas de la ficha; DataForSEO les suma volumen; se eligen hasta 3
que tengan volumen y no estén ya (frase exacta) en la descripción larga. El LLM no
elige: solo las incorpora de forma coherente con el texto actual. Si DataForSEO no
informa volumen, alcanza con demanda real en GSC (≥30 impresiones): `None` no es 0.

---

## D-013 · DataForSEO como enriquecimiento con caché, no como filtro
**3-nov-2026**
El `KeywordMapper` original reemplazaba las keywords de GSC por las de DataForSEO y
tiraba todo lo de menos de 50 búsquedas: en fichas de producto eso deja la ficha
sin keywords. Ahora el volumen solo se suma, se pide una vez por lote (cuesta lo
mismo 10 keywords que 1.000) y queda en caché 30 días.

---

## D-014 · Si faltan keywords: el mismo producto en 3 competidores
**3-nov-2026 · paso ② de la pizarra**
Se busca "{Nombre} {Marca}" en la API de resultados orgánicos de DataForSEO (no se
scrapea Google), se toman las 3 primeras páginas de otros sitios por encima de
cassoni y se leen sus H1, H2 y texto. Las frases que repiten ≥2 competidores, que
son de este producto y que no tenemos, se validan con volumen. Al LLM no le llega
texto de la competencia. Se respeta `robots.txt`. Descartado: Playwright contra
Google (términos de uso, CAPTCHAs, bloqueos).

---

## D-015 · Anti-canibalización entre fichas ya escritas
**3-nov-2026 · "en la medida de lo posible"**
Las keywords escritas en una ficha quedan registradas. Otra ficha no la usa si hay
alternativas; si no las hay, la usa y queda marcada con `compartida_con` para que
SEO lo vea.

---

## D-016 · Goteo de 10 fichas por día desde la lista de SEO
**3-nov-2026 · pizarra: "5-10 URLs/día"**
El cupo baja de 50 a 10. La lista la arma SEO y crece día a día. Una ficha
rechazada o fallida se reintenta una vez; después queda abandonada (antes se
reintentaba para siempre y gastaba LLM en cada intento).

---

## D-017 · Medición por keyword con ventanas del mismo largo
**3-nov-2026 · corrige D-010**
Antes se comparaba la suma de 90 días previos contra 14 días posteriores: casi todo
salía "bajó". Ahora, para N días, se piden a GSC N días antes y N días después de
la edición, para cada una de las 3 keywords, y solo de fichas escritas de verdad.

---

## D-018 · Idempotencia y HTML seguro
**3-nov-2026 · auditoría externa**
Una ficha escrita no se vuelve a editar salvo `--forzar` (re-correr la lista
editaba encima y pisaba la línea base). La edición no puede agregar HTML que el
original no tenía (scripts, iframes, eventos, enlaces, imágenes): con claves de
admin, WordPress no filtra el contenido.

---

## D-019 · Lo que se agrega es la keyword: una oración por keyword, sin medidas ni relleno
**3-nov-2026 · prueba real en seco**
La primera prueba agregó 36 oraciones y solo 15 tenían una keyword; 11 eran
medidas que la ficha ya muestra en sus atributos. Ahora, en código: una oración
agregada por keyword, cada una con su keyword, sin medidas, con máximo 4 palabras
que la ficha no dice y sin frases de interiorismo genérico. El mínimo de 150
palabras deja de bloquear (pendiente de confirmar por SEO).

---

## D-020 · Las keywords nuevas salen de la competencia y de la investigación, no solo de GSC
**3-nov-2026 · equipo SEO**
GSC solo trae búsquedas por las que la ficha ya aparece: en productos de nicho, su
nombre, que el H1 nuevo ya cubre. Agregarlo a la descripción no suma. Las keywords
de valor son las que la ficha todavía no atrae: las que rankean en el top 20 las
3 páginas de la competencia con el mismo producto (DataForSEO `ranked_keywords`) y
las de tipo × material/acabado de la ficha (`keyword_ideas`). Piso de 50
búsquedas por mes y dificultad ≤ 60. Si nada lo supera, la ficha queda solo con
el H1. Descartado: leer el HTML de la competencia como fuente principal (adivina
frases; `ranked_keywords` es el dato real) — queda como respaldo.

---

## D-021 · Selección por oportunidad de la ficha
**3-nov-2026**
Se ordena por potencial de clics (demanda × CTR que se gana al top 3 desde la
posición actual; para competencia e investigación, volumen × dificultad). Fuera:
lo que ya cubre el H1, posición > 30, informativas, transaccionales, otra marca,
otro tipo de producto, palabras sensibles y tipeos.

---

## D-022 · DataForSEO: errores de cuenta visibles y tope de gasto
**3-nov-2026 · prueba real**
Sin saldo (402), cuenta sin verificar (403) o pausada (40201, con HTTP 200) se
informan con el mensaje de la API y no se reintentan. `CASSONI_DFS_PRESUPUESTO_USD`
corta los pedidos que pasarían el tope de la corrida.
