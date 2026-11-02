#!/usr/bin/env bash
# Puerta de calidad del agente SEO de Cassoni. VERDE = terminado.
#   bash scripts/verify.sh
set -uo pipefail
cd "$(dirname "$0")/.."

PY="${PY:-}"
if [ -z "$PY" ]; then
  if [ -x "./venv/bin/python" ]; then PY="./venv/bin/python"; else PY="python3"; fi
fi
FAIL=0

paso() { printf '\n== %s ==\n' "$1"; }
fallo() { echo "ROJO: $1"; FAIL=1; }

paso "1/4 sintaxis"
if ! "$PY" -m compileall -q cassoni tests >/dev/null; then
  fallo "hay errores de sintaxis"
else
  echo "ok"
fi

paso "2/4 tests"
if ! "$PY" -m pytest tests/ -q; then
  fallo "tests en rojo"
fi

paso "3/4 secretos"
# claves de WooCommerce, claves privadas y tokens de Google no van al repo.
# Se escanea lo VERSIONADO (git grep): creds/ y .env* son locales y están ignorados.
PATRON='ck_[a-f0-9]{20,}|cs_[a-f0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|AQ[A-Za-z0-9_-]{28,}'
if git rev-parse --git-dir >/dev/null 2>&1; then
  if git grep -InE "$PATRON" -- '*.py' '*.md' '*.json' '*.sh' '*.yml' '*.txt' 2>/dev/null; then
    fallo "hay credenciales versionadas"
  else
    echo "ok: sin credenciales en lo versionado"
  fi
elif grep -RInE "$PATRON" --include='*.py' --include='*.md' --include='*.json' \
        --include='*.sh' --include='*.yml' --include='*.txt' . \
        --exclude-dir=.git --exclude-dir=venv --exclude-dir=creds \
        --exclude-dir=__pycache__ 2>/dev/null; then
  fallo "hay credenciales en texto plano"
else
  echo "ok: sin credenciales"
fi

paso "4/4 documentación ejecutable"
# los comandos que la doc promete tienen que existir en el CLI
if ! "$PY" -m pytest tests/test_docs.py -q; then
  fallo "la doc cita comandos o archivos que no existen"
fi

printf '\n'
if [ "$FAIL" -ne 0 ]; then
  echo "VERIFY: ROJO"
  exit 1
fi
echo "VERIFY: VERDE"
