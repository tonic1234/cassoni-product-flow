# Agente SEO — Cassoni

Optimiza fichas de producto de **cassoni.com** (13.079 publicadas). Cada día toma
hasta 10 fichas de la lista que arma el equipo SEO, pone el H1 en el formato
**`{Nombre} by {Marca}`** e incorpora en la **descripción larga** las 3 keywords con
volumen de búsqueda que todavía no tiene. Mide el efecto de cada keyword a 14/28 días.

**Landing explicativa:** [`docs/landing/index.html`](docs/landing/index.html).

Este repo está pensado para ser **auditado desde afuera**: cada afirmación tiene un
comando que la reproduce y una salida guardada en `evidencia/`.

## Auditar en cinco comandos

```bash
git clone https://github.com/tonic1234/cassoni-product-flow && cd cassoni-product-flow
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
bash scripts/verify.sh                                    # tests + secretos + doc
./venv/bin/python -m cassoni.cli --env prod --preflight   # GSC / Woo / LLM
./venv/bin/python -m cassoni.cli --env prod --urls lista.txt --batch 10   # en seco
```

`--preflight` no escribe ni gasta LLM. `--urls` sin `--write` corre en seco. Para las
credenciales ver [docs/OPERACION.md](docs/OPERACION.md).

## Qué hace, en orden

1. **Toma la lista del día**: las URLs que SEO va sumando a `lista.txt`, hasta 10
   por día, en horario hábil y con pausas aleatorias (para no editar en masa).
2. **Lee** la ficha real de WooCommerce (nombre, marca, categorías, atributos,
   descripción). Si ya fue escrita, la saltea.
3. **H1 por plantilla**: `{Nombre} by {Marca}`, siempre igual, sin LLM. Cubre las
   búsquedas de marca + modelo ("rugiano club sofa", "luceplan illan").
4. **Keywords nuevas, de tres fuentes** (todas con volumen de DataForSEO):
   - **GSC**: búsquedas por las que la ficha ya aparece en posición 4-30;
   - **competencia**: las búsquedas que **rankean en el top 20** las 3 páginas que
     venden el mismo producto y están por encima de cassoni (DataForSEO
     `ranked_keywords`); puntúan más las que rankean varios competidores;
   - **investigación**: tipo de producto × material/acabado/estilo de la ficha
     ("marble coffee table", "outdoor teak sofa") en DataForSEO `keyword_ideas`.
5. **Filtra y ordena**: fuera lo que ya cubre el H1, lo que no es de este producto
   (otro tipo de mueble, otra marca, un material que la ficha no tiene), lo
   informativo, lo de dificultad > 60 y lo de menos de **50 búsquedas por mes**.
   Gana el potencial de clics para esta ficha. Hasta 3. Si no queda ninguna, la
   descripción no se toca: la ficha queda solo con el H1.
6. **Edita** con un LLM: **una oración por keyword**, junto a la oración del
   original con la que tiene relación y armada con lo que la ficha ya dice. Sin
   medidas, sin relleno, conservando el 80% de las oraciones originales.
7. **Valida** en dos capas: reglas en código (keyword exacta, una oración por
   keyword, máximo 4 palabras que la ficha no dice, sin frases vacías ni medidas,
   HTML seguro) y LLM (tono, datos inventados). Hasta 2 pases.
8. **Escribe** `name` + `description` solo con `--write` y aprobada.
9. **Mide** cada keyword: N días antes vs N días después de la edición.

## Estado real (3-nov-2026)

| Pieza | Estado |
|---|---|
| H1 por plantilla `{Nombre} by {Marca}` | ✅ con tests y probado en seco contra la tienda |
| Keywords de GSC por oportunidad | ✅ probado en seco: aportan poco (casi siempre el nombre, que cubre el H1) |
| Keywords que rankea la competencia (`ranked_keywords`) | ⚠️ con tests, **sin probar contra la API** (cuenta sin saldo) |
| Investigación por atributos (`keyword_ideas`) | ⚠️ con tests, **sin probar contra la API** (cuenta sin saldo) |
| Una oración por keyword, anclada en la ficha, sin medidas | ✅ probado en seco: 12 oraciones, 11 con keyword, 0 medidas |
| DataForSEO: lotes, caché, tope de gasto, errores de cuenta visibles | ✅ con tests y probado contra la API |
| Idempotencia, HTML seguro, staging ≠ producción | ✅ con tests |
| Suite de tests | ✅ 336 verdes |
| Escritura en producción | ⛔ **no ejecutada**: el primer lote lo aprueba el equipo SEO |
| Cron | ⛔ **no instalado** (ejemplo en `docs/OPERACION.md`) |

**Antes de la próxima corrida** (con saldo en DataForSEO):
`./venv/bin/python tools/probar_dataforseo.py --env prod --url <una ficha>` hace una
consulta de cada tipo, muestra el costo real y confirma el formato de las respuestas.

## Muestra para validar con el cliente

Diez fichas reales elegidas por insumo (las que tienen material para escribir sin
inventar), procesadas en seco y publicadas para revisión:

**https://tarsterminal.duckdns.org/muestra-cassoni/**

```bash
./venv/bin/python -m cassoni.cli --env prod --urls muestra.txt --batch 10 --db sqlite:///muestra.db
./venv/bin/python tools/exportar_muestra.py --db sqlite:///muestra.db --out muestra.json
./venv/bin/python tools/generar_muestra.py --json muestra.json --out index.html
```

Medido en esa corrida: **8 de 10** aprobadas por el validador, **US$ 0,0196 por ficha**
(tokens reales), 1.255 → 2.024 palabras. Las dos rechazadas quedan en la página con el
motivo: un rechazo honesto vale más que una muestra toda verde.

## Mapa del repo

```
cassoni/            el agente (selector, gsc, editor, validador, woo, db, revisar)
tests/              suite completa (sin red, con fakes)
docs/
  ARQUITECTURA.md   la cadena y los contratos
  DECISIONES.md     ADR: qué se decidió, por qué, qué se descartó
  OPERACION.md      comandos, credenciales, qué hacer si falla
  AUDITORIA.md      cada número con el comando que lo reproduce
  REGLA-SEO-FICHAS.md   spec del cliente (fuente)
  landing-cliente/  el informe que se le mandó al cliente: objetivo y flujo (index.html + PDF)
PLAN.md             puesta en marcha y unidades de trabajo
evidencia/          salidas crudas: RED/GREEN de cada unidad, lote real, pilotos
scripts/verify.sh   la puerta (VERDE = terminado)
```

## Límites declarados

- El agente **no** toca `short_description`, meta title/description ni ALT: son del
  n8n (un solo escritor por campo).
- GSC es sólo lectura.
- El mínimo de 150 palabras del cliente **ya no bloquea** (obligaba a rellenar con
  medidas); el máximo de 300 se mide contra el original. Pendiente de confirmar
  por SEO.
- Pendiente de SEO: sacar los códigos del H1 ("Cleopatra Chair (SC1019) by OAK").
- Sin cron instalado, no hay nada corriendo solo.
