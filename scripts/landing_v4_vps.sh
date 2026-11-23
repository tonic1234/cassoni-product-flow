#!/usr/bin/env bash
# Landing v4 para Alex, de punta a punta, EN SECO (23-nov-2026).
#
#   bash scripts/landing_v4_vps.sh
#
# 1. Conexiones (preflight).
# 2. Las 10 fichas de Alex con la ficha completa de WooCommerce, y la comparación con él.
# 3. 30 fichas nuevas al azar por código, sin repetir ninguna ya usada (las de evidencia/,
#    docs/ y la lista de TARS del 18-nov si está), en seco, y se rehacen las que se queden
#    sin presupuesto de DataForSEO.
# 4. La landing: docs/landing-v4/index.html.
#
# Nada se escribe en WooCommerce: tools/correr_lote.py arma el pipeline con dry_run=True
# y no tiene opción para cambiarlo. Tarda ~1 h (precarga de DataForSEO) y cuesta ~US$ 3.
set -euo pipefail
cd "$(dirname "$0")/.."

N="${N:-30}"
FECHA="$(date +%F)"
MESES=(ene feb mar abr may jun jul ago sep oct nov dic)
DIA="$(date +%-d)-${MESES[$(( $(date +%-m) - 1 ))]}"
SEMILLA="${SEMILLA:-${FECHA//-/}}"
PY=./venv/bin/python
EVAL="evaluacion/${FECHA}"
mkdir -p "$EVAL" docs/landing-v4
CTRL="evidencia/${FECHA}-control-alex"
TANDA="evidencia/${FECHA}-tanda-${N}"
EXTRA="${EXCLUIR:-/root/wt-cassoni-v5/elegidas.txt}"

echo "== 1/4 conexiones"
$PY -m cassoni.cli --env prod --preflight

echo "== 2/4 las 10 fichas de Alex, con la ficha completa"
$PY -c "import json;print('\n'.join(f['url'] for f in json.load(open('evidencia/referencia-seo.json'))))" \
  > "${CTRL}.txt"
CASSONI_DB_URL="sqlite:///$(pwd)/${EVAL}/control-alex.db" CASSONI_DFS_PRESUPUESTO_USD=1.50 \
  $PY tools/correr_lote.py --urls "${CTRL}.txt" --out "${CTRL}.json" | tee "${CTRL}-consola.txt"
$PY tools/evaluar_vs_seo.py --lote "${CTRL}.json" --out "${CTRL}-vs-seo.json" | tail -1

echo "== 3/4 ${N} fichas nuevas (semilla ${SEMILLA})"
{ grep -rhoE 'https://cassoni\.com/product/[A-Za-z0-9._%-]+/?' evidencia docs 2>/dev/null || true
  [[ -f "$EXTRA" ]] && grep -hoE 'https://cassoni\.com/product/[A-Za-z0-9._%-]+/?' "$EXTRA" || true
} | sed 's#/*$#/#' | sort -u > "${TANDA}-excluidas.txt"
echo "excluidas: $(wc -l < "${TANDA}-excluidas.txt")"
$PY tools/elegir_muestra_ciega.py --semilla "$SEMILLA" --n "$N" \
  --excluir "${TANDA}-excluidas.txt" --out "${TANDA}.txt"
CASSONI_DB_URL="sqlite:///$(pwd)/${EVAL}/tanda.db" CASSONI_DFS_PRESUPUESTO_USD=3.50 \
  $PY tools/correr_lote.py --urls "${TANDA}.txt" --out "${TANDA}.json" | tee "${TANDA}-consola.txt"
CASSONI_DB_URL="sqlite:///$(pwd)/${EVAL}/tanda.db" CASSONI_DFS_PRESUPUESTO_USD=1.50 \
  $PY tools/rehacer_sin_presupuesto.py --lote "${TANDA}.json" | tee -a "${TANDA}-consola.txt"

echo "== 4/4 landing"
$PY tools/landing_v4.py --vs-seo "${CTRL}-vs-seo.json" --nuevas "${TANDA}.json" \
  --muestra "${TANDA}.txt" --fecha "${DIA}" --out docs/landing-v4/index.html

$PY - "${CTRL}-vs-seo.json" "${TANDA}.json" <<'EOF'
import json, sys
from collections import Counter
r = json.load(open(sys.argv[1]))["resumen"]
t = json.load(open(sys.argv[2]))
f = t["fichas"]
print(f"Alex: H1 idénticos {r['h1_iguales']}/10 · keywords {r['keywords_en_comun']}/{r['keywords_seo']} · aprobadas {r['aprobadas']}/10")
print(f"Nuevas: {dict(Counter(x['status'] for x in f))} · sin keywords {sum(1 for x in f if not x['keywords'])}"
      f" · sin presupuesto {sum(1 for x in f if x.get('dfs_sin_presupuesto'))}")
print("costos:", t["meta"]["costos"])
EOF
cat <<EOF

Listo. Todo en seco. La landing está en docs/landing-v4/index.html.

Subir al repo (para revisarla antes de publicar):
  git add evidencia/${FECHA}-* docs/landing-v4/index.html
  git commit -m "Landing v4 para Alex: control de sus 10 fichas y ${N} nuevas (${FECHA})"
  git push origin HEAD:flujo-seo-v2

Publicar en la misma URL de la v3 (guarda la v3 como index-v3.html):
  D=/root/caddy/data/cassoni-agente-seo
  cp \$D/index.html \$D/index-v3.html && cp docs/landing-v4/index.html \$D/index.html
EOF
