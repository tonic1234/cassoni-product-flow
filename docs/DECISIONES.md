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

---

## D-023 · Semillas de investigación con el tipo real y los materiales del texto
**13-nov-2026 · prueba en seco de la tanda nueva (v3.1 → v3.2)**
Con v3.1, 7 de 10 fichas nuevas quedaban sin keywords. La causa estaba antes de
los filtros: el tipo salía solo del nombre ('Salomé Valet Stand With Mirror' →
mirror; el metegol → table; set de baño y canastos sin tipo), entraban atributos
técnicos como estilo ('dali chandelier', 'triac chandelier') y los materiales que
la ficha dice solo en la descripción (latón, vidrio soplado, cuero) no se usaban.
Ahora:
- el tipo es el de EE. UU. que ya resuelve el H1 (`tipo_ee_uu`), que además corta
  en ' with ' y prefiere la categoría cuando es más precisa ('stool' → 'bar stool');
- las semillas son material/estilo × tipo, con los materiales de la descripción;
- las semillas mismas son candidatas con su volumen, pedido en el pedido único del
  lote (ficha por ficha costaba US$ 0,09 cada una y agotaba el presupuesto);
- `keyword_ideas` filtra por el núcleo del tipo ('%foosball%', '%lamp%' o '%light%');
- se descartan las ideas que buscan repuestos ('foosball table rods'), algo para el
  producto ('frame for mirror') o que parten el tipo ('ceiling living room light').
Resultado medido: tanda nueva 3 → 5 de 10 fichas con keywords; control 4 → 8 de 10.
Costo: ~US$ 0,09 por ficha en DataForSEO y ~US$ 0,007 en LLM. El tope por corrida
(`CASSONI_DFS_PRESUPUESTO_USD`) tiene que ser ≥ US$ 1,20 para 10 fichas; con 0,30
la corrida se corta y ninguna ficha recibe keywords.

---

## D-024 · Imitar el documento del SEO: sus fichas como ejemplos, probado sin ver la respuesta
**13-nov-2026 · pedido del equipo: "hacer lo mismo que el SEO en el resto de las fichas"**
El documento del SEO del 6-nov (pestaña "Cómo hacerlo por ficha") resuelve 10 fichas:
H1, 1–3 keywords y descripción. Su criterio de keywords no es el de v3.2: usa
variantes del nombre por las que la ficha ya aparece en GSC (sin piso de volumen),
marca + tipo y una genérica corta de material o tipo, y evita el nombre tal cual.
`CASSONI_MODO_KEYWORDS=seo` (por defecto):
- candidatas = GSC (posición ≤ 30, ≥ 2 impresiones, sin tipeos, otro idioma, precio
  ni navegación ajena) + genéricas armadas solo con datos de la ficha, con volumen;
- un LLM elige 1–3 viendo las elecciones reales del SEO (`evidencia/referencia-seo.json`,
  armada con `tools/armar_referencia_seo.py`);
- el redactor recibe las descripciones del SEO como ejemplo de estilo y largo
  (60–110 palabras).
Regla de la prueba: cada ficha ve como ejemplo las OTRAS nueve, nunca la propia, y las
instrucciones solo tienen ejemplos inventados (una primera corrida que citaba keywords
de estas fichas en el prompt se descartó por eso).
Medido en las 10 fichas (`tools/evaluar_vs_seo.py`): H1 idénticos 1 → 4; keywords del SEO
que elige el agente 2 → 7 de 22; largo 118 → 96 palabras (SEO 86).
Pendiente: más fichas resueltas por el SEO para que aprenda mejor el criterio de keywords.
`CASSONI_MODO_KEYWORDS=filtros` conserva la selección por reglas de v3.2.

---

## D-025 · Reglas del SEO en código; DeepSeek solo redacta. Agente diario autónomo
**17-nov-2026 · devolución de Alex (SEO)**
Alex: el H1 prioriza lo que la gente busca (si el nombre ya tiene volumen, nombre +
marca; si no, el rasgo más buscado), y las keywords que funcionan son las de Search
Console con impresiones y marca + tipo. Las genéricas de DeepSeek fallaban («leather
table» en Dandy, «marble table» en Palatial). `CASSONI_MODO_KEYWORDS=reglas` (por defecto):
- H1: si el nombre tiene ≥ `CASSONI_H1_UMBRAL_NOMBRE` búsquedas/mes (1.000: Club Sofa
  1.000 sí, Rock Coffee Table 480 no) va nombre + marca, fijo. Si no, el redactor elige
  el rasgo entre los materiales de la ficha con su volumen: el que tienen todas las
  versiones y, entre esos, el más buscado (el más buscado a secas tomaba opciones:
  «Wood» en Frog, «Fabric» en Cruise, «Gold Leaf» en Tiffany).
- Keywords en código: Search Console (primero variantes del nombre; sin el nombre
  tal cual ni recortado, sin la marca sola, sin símbolos, ≥5 impresiones si no nombra
  modelo ni marca), marca + tipo con volumen, y una genérica opcional solo si su
  material es el del H1 (el código lo controla). El redactor las usa todas.
- La tienda agrega «by {Marca}» con el logo al H1: el `name` se escribe sin la marca.
Medido en las 10 fichas del SEO: keywords del SEO 7 → 9 de 22, 2,1 por ficha (SEO 2,2);
19 de 20 aprobadas (la rechazada inventaba un dato y el validador la frenó). Costo:
US$ 0,005 de LLM y ~US$ 0,05 de DataForSEO por ficha.
`tools/agente_diario.py` corre solo: lista del SEO (o propuestas de Search Console si
se vacía), cupo diario, reporte del día en `evidencia/diario/`, medición los lunes.
En seco y escribiendo llevan estados separados. `scripts/instalar_tarea_windows.ps1`
lo registra en el Programador de tareas.
Pendiente con Alex: el umbral de 1.000; Rock sin «Marble» (la tapa también viene en
madera); Steinway, cuyo volumen es el de la marca Steinway, no el de esta pieza.

## D-026 · Opciones de la parte principal y marcas ajenas en el nombre
**18-nov-2026 · respuesta a los tres pendientes de D-025**
- **Umbral de 1.000 búsquedas/mes:** confirmado. Sin cambios.
- **Opciones (Rock):** cuando la ficha ofrece la parte principal como alternativa en una
  misma oración («top available in painted wood or in a wide range of marble options»),
  el H1 lleva la opción más buscada y queda fijo («Rock Marble Coffee Table by Rugiano»,
  33.100 > 27.100), y la descripción cubre **todas** las opciones, cada una con su
  genérica '{opción} {tipo}' como keyword objetivo («marble coffee table», «wood coffee
  table»). Con opciones entra una sola de Search Console para dejar lugar a las dos.
  `reglas_seo.opciones_de_material`, `keywords_de_opciones`; bloque OPCIONES del redactor.
- **Marca ajena (Steinway):** el volumen de «steinway piano» (27.100) es el de la marca
  Steinway, no el de la pieza de Riva Mobili D'Arte. Si el nombre trae una marca de otro
  fabricante (`reglas_seo.MARCAS_AJENAS`), su volumen no cuenta como «el nombre ya se
  busca» y va la regla del rasgo («Mother-of-Pearl»); las búsquedas que son solo esa
  marca (+ el tipo: «piano steinway») no se toman como keyword.
Descartado: ponerle al H1 las dos opciones («Rock Marble or Wood Coffee Table»): largo y
no es como escribe el SEO. Tests: `tests/test_opciones_y_marca_ajena.py`,
`tests/test_seleccion_reglas_opciones.py` (evidencia `2026-11-18-opciones-marca-ajena-*`).

## D-027 · El H1 no pierde términos del nombre; las fichas sin presupuesto se rehacen
**23-nov-2026 · revisión de la tanda de 30 del 18-nov (notas de TARS en EVALUACION-EN-SECO)**
TARS anotó H1 que pierden códigos de modelo y ediciones, y que el tope de DataForSEO
(US$ 2,00) se agotó al final del lote. Tres causas en el H1 y una en el presupuesto:
- **D-026 demasiado amplio:** la lista de marcas ajenas tenía marcas de autos y de moda
  (Hermes, Tiffany, Harley, Vespa) que en Cassoni son nombres de modelo; esas fichas
  pasaban a la regla del rasgo. Ahora solo fabricantes de pianos, y solo si el modelo
  ES la marca («19800 Steinway Piano»; «Aurora Steinway Grand Piano» no).
- **La regla del rasgo cortaba después del tipo** (viene de D-025): «Cleopatra Chair
  Limited Edition» → «Cleopatra Walnut Chair». Ahora el H1 conserva lo que el nombre dice
  después del tipo (`reglas_seo.sufijo_del_nombre`), y si lo arma el redactor, el
  control en código lo exige.
- **Presupuesto:** con el tope agotado, las keywords se descartan «sin datos de Google»
  y la ficha sale «sin keywords objetivo», igual que una a la que no le corresponde
  ninguna. Ahora cada ficha del lote lleva `dfs_sin_presupuesto` y
  `tools/rehacer_sin_presupuesto.py` las vuelve a correr (reconoce también lotes viejos
  por el motivo). `scripts/tanda_seo.sh` usa tope 3,50, base propia y rehace solo.
Como cambian las reglas del H1, el lote del 18-nov no representa el código actual: se
vuelven a correr **las mismas 30** (`URLS=elegidas.txt`).
Tests: `test_h1_conserva_nombre.py`, `test_rehacer_sin_presupuesto.py`,
`test_seleccion_reglas_opciones.py` (evidencia `2026-11-23-h1-conserva-nombre-*`).

**Ajuste del mismo día contra la referencia de Alex** (sus 10 fichas, `evidencia/referencia-seo.json`,
simuladas sin red ni LLM):
- **Opciones:** solo decide el H1 una opción **estructural única** (la tapa de Rock:
  «Rock Marble Coffee Table», igual que Alex). Si la opción es el **tapizado**, Alex no
  elige uno («Hermes Maxi **Upholstered** King Bed») y no suma keywords por opción; con
  **varios grupos** (Club Sofa: tubos de latón o bronce, cuero o tela) tampoco. En todos
  los casos el redactor cubre las opciones en la descripción (Alex: sección UPHOLSTERY).
  La versión del 18-nov fijaba «Leather» en Hermes, donde el agente ya coincidía con Alex.
- **Códigos:** se descartó conservar en el H1 los códigos que la gente busca: Alex saca
  «SC1019» y «19800».
- **Marca ajena:** sigue sin contar para el H1, pero la búsqueda de la marca **sí** puede
  ser keyword (Alex: «steinway and sons pianos»).
Resultado de la simulación: el H1 que decide el código coincide con Alex donde lo fija
(Rock, Club Sofa por nombre); keywords de Alex elegidas por el código: 10 de 22 (antes 9).
Lo que faltaba eran genéricas cortas de material + tipo: ver D-028.

## D-028 · Genéricas cortas como en la referencia de Alex
**23-nov-2026**
Alex nunca dijo «nunca marble table». El 17-nov marcó dos errores de DeepSeek: «marble
table» en **Palatial** (esa versión no tiene mármol: la keyword afirmaba algo falso) y
«leather table» en **Dandy** (es una mesa de pool: «leather table» es otro producto).
En D-025 lo generalizamos de más a «sin genéricas cortas», y su propia referencia las usa.
Regla nueva, en código:
- **Material exacto del H1 + tipo corto** (`cabeza_de`: 'coffee table' → 'table'), sin
  repetir el H1 tal cual y una por combinación de palabras (`genericas_para_h1`):
  Bakkarat «Glass Dining Table» → «dining table in glass», «glass table»; Cleopatra «Wood
  and Leather Dining Chair» → «wood and leather chair» (no «wood chair»). Hasta dos.
- **Opción estructural** (D-027): forma corta de cada opción si tiene volumen (Rock:
  «marble table», «wood table»).
- **Nunca** un material que la ficha no tiene (solo materiales del texto) ni un tipo que
  acortado es otro producto (`_NO_ACORTAR`: pool, billiard, foosball… → Dandy sin
  «leather table»).
- El redactor recibe la regla; el control en código rechaza la genérica de otro material
  y pide la del H1 si falta (salvo que el redactor la declare omitida por no entrar natural).
- **Marca ajena:** su nombre completo respalda las búsquedas («steinway and sons piano»),
  la marca sola no es keyword, y entre «&» y «and» va la forma escrita.
Simulación sobre las 10 fichas de Alex (`evidencia/2026-11-23-simulacion-vs-referencia-alex.txt`,
sin red ni LLM): keywords de Alex elegidas **16 de 22** con su H1 y **15 de 22** con el H1
que escribió el agente (antes 9 medido). Las 6 que faltan son elecciones puntuales («hermes
bed frame», «cleopatra's chair», «wall light», «wall sconce», «italian piano», «visionnaire
chair»): forzarlas sería ajustar a 10 fichas. Lo que hace el redactor con la regla nueva
se mide en la próxima tanda en seco.
**Medido el mismo día con DeepSeek real** (`tools/control_alex_sin_tienda.py`, deepseek-v4.1-flash
por OpenCode, en seco y sin atributos de WooCommerce;
`evidencia/2026-11-23-control-alex-sin-tienda*.json`): keywords de Alex **15 de 22** (17-nov: 9),
H1 idénticos 3 (antes 2), parecido 0,74 (antes 0,66), 10 de 10 aprobadas, 87 palabras promedio
(Alex 86). Diferencias que quedan: Cleopatra sale «Leather» y no «Wood and Leather» (por eso no
entra «wood and leather chair»); Illan suma dos genéricas del mismo material.

