# Operación

## Requisitos

```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
cp .env.staging.example .env.staging   # completar credenciales (nunca en git)
```

El service account de GSC va en `creds/gsc-service-account.json` (0600). Tiene que
tener la propiedad `sc-domain:cassoni.com` compartida como **Restringido**. El prefijo
`https://cassoni.com/` da 403: usar sólo `sc-domain`.

Las rutas relativas del `.env` se resuelven contra la carpeta del `.env`, no contra
el directorio desde el que se corre el comando.

## Los cuatro comandos

```bash
# 1) ¿está todo conectado? No gasta LLM.
./venv/bin/python -m cassoni.cli --env prod --preflight

# 2) elegir el trabajo (escribe evidencia/lote-<fecha>-<N>.json)
./venv/bin/python -m cassoni.cli --env prod --seleccionar 20 --days 90 --pausa 1

# 3) procesar (DRY-RUN por defecto: no toca el sitio)
./venv/bin/python -m cassoni.cli --env prod --urls lote.txt --batch 20

# 4) escribir de verdad (exige que el validador apruebe, ficha por ficha)
./venv/bin/python -m cassoni.cli --env prod --urls lote.txt --write --scheduler

# 5) medir el efecto
./venv/bin/python -m cassoni.cli --env prod --revisar --days 14
```

## Qué mirar en la salida

```
Resultados: {'processed': 17, 'rejected': 2, 'skipped': 1}
Resumen DB: {'total': 20, 'processed': 17, 'rejected': 2, 'failed': 0, ...}
```

- `processed` = aprobada **y** aplicada.
- `rejected` = el gate la frenó. El motivo de cada rechazo queda en
  `validation_result.issues` de la DB y se imprime en la consola.
- `skipped` = no correspondía (draft, sin consultas en GSC, URL que no es ficha).

Un lote sano no debe tener `failed`. Si hay `failed`, es un error técnico y el
mensaje dice de qué pieza (WooCommerce, GSC o LLM).

## Ritmo

`--scheduler` procesa de 9 a 18 (lun-vie) con pausas aleatorias de 30 s a 5 min, y
reanuda al día siguiente lo que quedó pendiente (`cassoni_sched.json`). El objetivo
por defecto es 50 fichas/día.

**No hay ningún cron ni timer instalado todavía.** El plan de puesta en marcha
contempla un timer de systemd, pero hasta que exista y esté verificado, el agente
corre sólo cuando alguien ejecuta el comando. No se documenta como automático lo que
no lo es.

## Credenciales

| Qué | Dónde | Permiso |
|---|---|---|
| GSC | `creds/gsc-service-account.json` | lectura (`webmasters.readonly`) |
| WooCommerce | `.env.<env>` `CASSONI_WC_KEY/SECRET` | lectura + escritura de productos |
| DataForSEO | `.env.<env>` `CASSONI_DFS_LOGIN/PASSWORD` | lectura |
| LLM | `.env.<env>` `CASSONI_LLM_*` | API oficial de DeepSeek |

`bash scripts/verify.sh` falla si aparece una credencial en texto plano en el repo.

## Costos

- GSC: gratis (cuota de API).
- DataForSEO: se cobra por request de volumen; hoy el CLI no lo usa (el mapper es
  opcional) y el lote se arma sólo con GSC.
- LLM: ~1 a 2 minutos de `deepseek-flash` por ficha, con hasta 2 pases de
  validador. La columna `llm_cost` de la DB existe pero **todavía no se llena**: el
  costo real por ficha se mide con el panel del proveedor, no con la traza. Es una
  deuda declarada, no un dato que se pueda citar.

## Cuando algo falla

| Síntoma | Causa más probable | Qué hacer |
|---|---|---|
| `FALTAN credenciales` | `.env` incompleto | completar y volver a correr `--preflight` |
| GSC `403` | se usó `https://cassoni.com/` como sitio | usar `sc-domain:cassoni.com` |
| GSC `FileNotFoundError` | service account en ruta relativa y cwd distinto | correr desde la raíz del repo (ya resuelto desde 2-nov) |
| Todo `rejected` | la ficha no tiene insumo para llegar a 150 palabras, o el validador ve datos que no están en la ficha | leer `validation_result.issues`; ver D-008 |
| `failed: editor LLM` | cuota, clave o timeout del proveedor | revisar `--preflight` (ping a `/models`) |
| WooCommerce `401` | clave sin permiso de escritura | pedir clave read+write |
