# Agente SEO — Cassoni

Optimiza fichas de producto de **cassoni.com** (13.079 publicadas): decide qué ficha
vale la pena tocar a partir de Google Search Console, y edita **sólo el H1 y la
descripción larga** incorporando keywords con la regla del cliente. Mide el efecto a
14/28 días.

Este repo está pensado para ser **auditado desde afuera**: cada afirmación tiene un
comando que la reproduce y una salida guardada en `evidencia/`.

## Auditar en cinco comandos

```bash
git clone https://github.com/tonic1234/cassoni-product-flow && cd cassoni-product-flow
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
bash scripts/verify.sh                                    # tests + secretos + doc
./venv/bin/python -m cassoni.cli --env prod --preflight   # GSC / Woo / LLM
./venv/bin/python -m cassoni.cli --env prod --seleccionar 20 --days 90
```

`--preflight` y `--seleccionar` no escriben nada y no gastan LLM. Para las
credenciales ver [docs/OPERACION.md](docs/OPERACION.md).

## Qué hace, en orden

1. **Elige** las fichas con más oportunidad real: posición 4-20 con demanda, o mucho
   aparecer con CTR bajo. Descarta el ruido (posición > 30 sin un clic), todo lo que
   no sea `/product/` y las consultas que no son del producto (GSC devuelve
   `geef foto` o `liberator lounger` en fichas donde no corresponden).
2. **Lee** la ficha real de WooCommerce (texto, categorías, marca, atributos) y las
   consultas de GSC de los últimos 90 días.
3. **Filtra** keywords: anti-canibalización determinista (contra los H1 de las fichas
   hermanas y las categorías reales) y una sola keyword por palabra compartida.
4. **Edita** con un LLM: H1 ≤ 60 caracteres con la keyword principal exacta, y la
   descripción larga editada sobre la existente (mínimo 80% de las oraciones
   originales intactas), 150-300 palabras, máximo 2 H2, 2-3 secundarias.
5. **Valida** en dos capas: reglas mecánicas en código primero, LLM después (tono,
   datos inventados, HTML). Si no aprueba, re-trabaja hasta dos veces.
6. **Escribe** sólo si el gate está abierto (`--write`) y la ficha fue aprobada.
7. **Mide**: guarda la línea base de la consulta objetivo y compara a 14/28 días.

## Estado real (2-nov-2026)

| Pieza | Estado |
|---|---|
| Selección de trabajo desde GSC | ✅ funciona (`--seleccionar 20` en 1m21s) |
| Lectura de GSC (90 días, 200 filas) | ✅ corregida |
| Keyword principal por oportunidad | ✅ con tests |
| Línea base y revisión | ✅ con tests |
| Preflight | ✅ verde contra producción |
| Suite de tests | ✅ 209 verdes |
| Piloto de punta a punta | ✅ **3 de 3** fichas reales aprobadas en dry-run tras el filtro de relevancia (antes: 1 de 3) |
| Escritura en producción | ⛔ **no ejecutada**: el primer lote debe aprobarlo el equipo SEO |
| Cron / timer | ⛔ **no instalado**: el agente corre a mano |

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
PLAN.md             puesta en marcha y unidades de trabajo
evidencia/          salidas crudas: RED/GREEN de cada unidad, lote real, pilotos
scripts/verify.sh   la puerta (VERDE = terminado)
```

## Límites declarados

- El agente **no** toca `short_description`, meta title/description ni ALT: son del
  n8n (un solo escritor por campo).
- GSC es sólo lectura.
- Sin cron instalado, no hay nada corriendo solo. Cuando exista, se documenta acá.
- El costo real por ficha todavía no se registra en la traza (`llm_cost` vacío).
