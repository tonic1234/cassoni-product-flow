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
