# Tanda en seco de 30 fichas + página de evaluación

Medido el **18-nov-2026** sobre la rama `flujo-seo-v2` (commit `b4bbc3e`). Sirve para que el SEO
evalúe la calidad del trabajo **antes** de autorizar un `--write` en la tienda.

## Correr una tanda

```bash
git worktree add /root/wt-cassoni-v5 origin/flujo-seo-v2 -b agent/<unidad>
cd /root/wt-cassoni-v5
ln -sfn /root/cassoni-agent/.env.prod .env.prod && ln -sfn /root/cassoni-agent/creds creds

# 1. excluir lo que ya vio alguien y elegir al azar por semilla (=fecha)
grep -rhoE 'https://cassoni\.com/product/[A-Za-z0-9._%-]+/?' evidencia docs \
  | sed 's#/*$#/#' | sort -u > excluidas.txt
./venv/bin/python tools/elegir_muestra_ciega.py --semilla 20261118 --n 30 \
  --excluir excluidas.txt --out elegidas.txt

# 2. la corrida, con base propia (no toca ninguna traza de producción)
CASSONI_DB_URL=sqlite:////root/cassoni-eval/<fecha>/staging-30.db \
CASSONI_DFS_PRESUPUESTO_USD=2.00 \
  ./venv/bin/python tools/correr_lote.py --urls elegidas.txt --out lote-30.json

# 3. la página para el SEO
./venv/bin/python tools/landing_evaluacion.py --json lote-30.json --out index.html \
  --titulo "Treinta fichas de Cassoni, en seco"
```

`scripts/tanda_seo.sh` hace todo de una (23-nov): base propia en `evaluacion/`, tope de
DataForSEO 3,50, rehace las fichas que se quedaron sin presupuesto y arma esta página. Para
repetir una lista ya elegida: `URLS=/root/wt-cassoni-v5/elegidas.txt bash scripts/tanda_seo.sh`.

## Tiempos y costos reales (30 fichas)

- **Precarga ≈ 26 min**: `_paginas_competidores` hace un `ranked_keywords`/`serp_organico` por ficha,
  con tope de 12 requests por minuto y polling de tareas. No está colgado: se comprueba con
  `py-spy dump --pid <pid>`.
- **Fichas ≈ 14 min** (~28 s cada una, 66 llamadas de LLM).
- **US$ 0,0737 por ficha**: DataForSEO 0,05 + LLM 0,005. Con tope 2,00 un lote de 30 **llega justo
  al tope**: las últimas fichas quedan sin keyword objetivo.

## Lo que rompe la página

- **Las fotos no se pueden incrustar**: `wp-content/uploads/...` devuelve **403 de Cloudflare**,
  incluso desde el navegador headless y con cookies. Se usan las iniciales del producto sobre un
  fondo violeta, y se dice en la página.
- `.kpis` sin `display:grid` renderiza la grilla como filas de 1 px.
- Si el `<em>` del H1 se arma con la keyword, se pierde la mayúscula original: el H1 nuevo se
  compara **palabra por palabra contra el nombre original** y se resalta el fragmento agregado.
- Con 9 KPIs el bloque queda balanceado en **3 columnas** (3×3), no con `auto-fit`.

## Qué se mira en el resultado

Además de aprobadas y rechazadas:

1. **H1 que pierden un término del nombre** (códigos de modelo, ediciones). Corregido en D-027:
   si vuelve a aparecer, es un bug.
2. **Fichas sin keyword objetivo**: cada una debería traer el motivo escrito en `seleccion`. Si
   el motivo es «sin datos de Google», fue el presupuesto: `tools/rehacer_sin_presupuesto.py`.
3. **Cantidad de intentos** por ficha: dos o tres significa que el validador rebotó y hubo re-trabajo.
