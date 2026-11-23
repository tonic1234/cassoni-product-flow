#!/usr/bin/env bash
# Tanda en seco para el SEO, sin intervención humana.
#
#   bash scripts/tanda_seo.sh                          # 30 fichas nuevas al azar
#   URLS=/root/wt-cassoni-v5/elegidas.txt bash scripts/tanda_seo.sh   # una lista ya elegida
#   N=10 bash scripts/tanda_seo.sh                     # otra cantidad
#
# 1. Si no se pasa URLS: excluye toda ficha que ya aparece en evidencia/ o docs/ y
#    elige N nuevas al azar por código (semilla = fecha), entre las que tienen >= 50
#    impresiones en Search Console, estratificadas por familia.
# 2. Las corre EN SECO, con base propia (no toca las trazas de producción).
# 3. Vuelve a correr las que se quedaron sin presupuesto de DataForSEO.
# 4. Arma la página de evaluación (tools/landing_evaluacion.py).
#
# Corre en el VPS, donde están .env.prod y creds/. Medido el 18-nov con 30 fichas:
# ~26 min de precarga + ~14 min de fichas, US$ 0,0737 por ficha (≈ US$ 2,20).
set -euo pipefail
cd "$(dirname "$0")/.."

N="${N:-30}"
FECHA="$(date +%F)"
SEMILLA="${SEMILLA:-${FECHA//-/}}"
BASE="evidencia/${FECHA}-tanda-${N}"
PY=./venv/bin/python
# con 2,00 la tanda de 30 del 18-nov llegó justo al tope y las últimas quedaron sin
# datos de Google
export CASSONI_DFS_PRESUPUESTO_USD="${CASSONI_DFS_PRESUPUESTO_USD_TANDA:-3.50}"
# base propia: una corrida de evaluación no se mezcla con lo que hace el worker
mkdir -p evaluacion
export CASSONI_DB_URL="${CASSONI_DB_URL_TANDA:-sqlite:///$(pwd)/evaluacion/${FECHA}-tanda.db}"

echo "== 1/6 conexiones"
$PY -m cassoni.cli --env prod --preflight

if [[ -n "${URLS:-}" ]]; then
  echo "== 2/6 lista dada: ${URLS}"
  cp "$URLS" "${BASE}.txt"
else
  echo "== 2/6 elección al azar (semilla ${SEMILLA}), sin las fichas ya vistas"
  grep -rhoE 'https://cassoni\.com/product/[A-Za-z0-9._%-]+/?' evidencia docs 2>/dev/null \
    | sed 's#/*$#/#' | sort -u > "${BASE}-excluidas.txt"
  $PY tools/elegir_muestra_ciega.py --semilla "$SEMILLA" --n "$N" \
    --excluir "${BASE}-excluidas.txt" --out "${BASE}.txt"
fi

echo "== 3/6 corrida en seco"
$PY tools/correr_lote.py --urls "${BASE}.txt" --out "${BASE}.json" | tee "${BASE}-consola.txt"

echo "== 4/6 las que se quedaron sin presupuesto de DataForSEO"
$PY tools/rehacer_sin_presupuesto.py --lote "${BASE}.json" | tee -a "${BASE}-consola.txt"

echo "== 5/6 página para el SEO"
mkdir -p docs/revision-seo
$PY tools/landing_evaluacion.py --json "${BASE}.json" \
  --out "docs/revision-seo/tanda-${FECHA}.html" \
  --titulo "Tanda de ${N} fichas · ${FECHA}" --fotos || \
$PY tools/landing_evaluacion.py --json "${BASE}.json" \
  --out "docs/revision-seo/tanda-${FECHA}.html" --titulo "Tanda de ${N} fichas · ${FECHA}"

echo "== 6/6 resumen"
$PY - "${BASE}.json" <<'EOF'
import json, sys
from collections import Counter
d = json.load(open(sys.argv[1]))
f = d["fichas"]
print("estados:", dict(Counter(x["status"] for x in f)))
print("sin keywords:", sum(1 for x in f if not x["keywords"]))
print("sin presupuesto (después de rehacer):", sum(1 for x in f if x.get("dfs_sin_presupuesto")))
print("costos:", d["meta"]["costos"], d["meta"].get("costos_rehechas", ""))
EOF
echo
echo "Listo. Subir al repo:"
echo "  git add ${BASE}* docs/revision-seo/tanda-${FECHA}.html && git commit -m 'Tanda de ${N} para el SEO (${FECHA})' && git push"
