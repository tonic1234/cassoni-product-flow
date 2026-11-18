#!/usr/bin/env bash
# Tanda nueva para el SEO, sin intervención humana (18-nov-2026).
#
#   bash scripts/tanda_seo.sh            # 30 fichas
#   N=10 bash scripts/tanda_seo.sh       # otra cantidad
#
# 1. Excluye toda ficha que ya aparece en evidencia/ o docs/ (ya la vio alguien).
# 2. Elige N fichas nuevas al azar por código (semilla = fecha, publicada en el
#    archivo), entre las que tienen >= 50 impresiones en Search Console,
#    estratificadas por familia de categoría.
# 3. Las corre EN SECO: no se escribe nada en WooCommerce.
# 4. Arma la página de revisión para el SEO.
#
# Corre en el VPS, donde están .env.prod y creds/. Costo esperado: ~US$ 0,05 de
# DataForSEO y ~US$ 0,005 de LLM por ficha (~US$ 1,70 las 30).
set -euo pipefail
cd "$(dirname "$0")/.."

N="${N:-30}"
FECHA="$(date +%F)"
SEMILLA="${SEMILLA:-${FECHA//-/}}"
BASE="evidencia/${FECHA}-tanda-${N}"
PY=./venv/bin/python
# el tope por corrida de .env.prod (1,50) corta una tanda de 30 a la mitad
export CASSONI_DFS_PRESUPUESTO_USD="${CASSONI_DFS_PRESUPUESTO_USD_TANDA:-3.00}"

echo "== 1/5 conexiones"
$PY -m cassoni.cli --env prod --preflight

echo "== 2/5 fichas ya vistas (se excluyen)"
grep -rhoE 'https://cassoni\.com/product/[A-Za-z0-9._%-]+/?' evidencia docs 2>/dev/null \
  | sed 's#/*$#/#' | sort -u > "${BASE}-excluidas.txt"
wc -l < "${BASE}-excluidas.txt"

echo "== 3/5 elección al azar (semilla ${SEMILLA})"
$PY tools/elegir_muestra_ciega.py --semilla "$SEMILLA" --n "$N" \
  --excluir "${BASE}-excluidas.txt" --out "${BASE}.txt"

echo "== 4/5 corrida en seco"
$PY tools/correr_lote.py --urls "${BASE}.txt" --out "${BASE}.json" | tee "${BASE}-consola.txt"

echo "== 5/5 página para el SEO"
mkdir -p docs/revision-seo
$PY tools/pagina_revision_seo.py --lote "Tanda nueva de ${N} (${FECHA})=${BASE}.json" \
  --out "docs/revision-seo/tanda-${FECHA}.html" --fecha "$FECHA"

$PY - "${BASE}.json" <<'EOF'
import json, sys
from collections import Counter
d = json.load(open(sys.argv[1]))
c = Counter(f["status"] for f in d["fichas"])
print("estados:", dict(c))
print("costos:", d["meta"]["costos"])
EOF
echo
echo "Listo. Subir al repo:"
echo "  git add ${BASE}* docs/revision-seo/tanda-${FECHA}.html && git commit -m 'Tanda de ${N} para el SEO (${FECHA})' && git push"
