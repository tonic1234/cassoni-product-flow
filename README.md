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
3. **H1 por plantilla**: `{Nombre} by {Marca}`, siempre igual, sin LLM.
4. **Keywords**: las de GSC de la ficha + volumen de DataForSEO (un solo pedido por
   lote, con caché). Se quedan las que son del producto, **no están ya en la
   descripción** y tienen volumen, con anti-canibalización (fichas hermanas,
   categorías y keywords ya escritas en otras fichas). Hasta 3.
5. **Si faltan**: busca el mismo producto en Google vía DataForSEO, lee las 3
   páginas de competidores que rankean por encima y saca frases que repiten y
   nosotros no tenemos. Validadas con volumen.
6. **Edita** con un LLM: mete las 3 keywords en la descripción actual, conservando
   al menos el 80% de las oraciones originales.
7. **Valida** en dos capas: reglas en código (cada keyword exacta, 150-300 palabras,
   ≤2 H2, conservación, HTML seguro) y LLM (tono, datos inventados). Hasta 2 pases.
8. **Escribe** `name` + `description` solo con `--write` y aprobada.
9. **Mide** cada keyword: N días antes vs N días después de la edición.

## Estado real (3-nov-2026)

| Pieza | Estado |
|---|---|
| H1 por plantilla `{Nombre} by {Marca}` | ✅ con tests |
| 3 keywords que faltan, con volumen (GSC + DataForSEO) | ✅ con tests |
| Competidores cuando faltan keywords | ✅ con tests (sin probar contra la API real) |
| Caché de volumen y costo de DataForSEO por ficha | ✅ con tests |
| Anti-canibalización entre fichas escritas | ✅ con tests |
| Idempotencia (no re-editar) y HTML seguro | ✅ con tests |
| Medición por keyword con ventanas iguales | ✅ con tests |
| Staging no puede apuntar a producción | ✅ con tests |
| Suite de tests | ✅ 291 verdes |
| Corrida real del flujo v2 | ⛔ **pendiente**: correr `--batch 10` en seco con la lista de SEO |
| Escritura en producción | ⛔ **no ejecutada**: el primer lote lo aprueba el equipo SEO |
| Cron | ⛔ **no instalado** (ejemplo en `docs/OPERACION.md`) |

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
- La regla de 150-300 palabras sigue vigente: una ficha cuyo original ya supera
  300 palabras va a salir rechazada. Decisión pendiente del equipo SEO.
- Sin cron instalado, no hay nada corriendo solo.
