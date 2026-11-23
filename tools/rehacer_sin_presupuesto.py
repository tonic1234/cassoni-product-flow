# -*- coding: utf-8 -*-
"""Vuelve a correr, EN SECO, las fichas de un lote que salieron sin datos de Google
porque se agotó el tope de DataForSEO de la corrida, y las reemplaza en el mismo JSON.

Una ficha sin presupuesto sale «sin keywords objetivo», igual que una a la que de
verdad no le corresponde ninguna: no se le puede mostrar así al SEO (23-nov-2026).

    ./venv/bin/python tools/rehacer_sin_presupuesto.py --lote evidencia/X.json

Reconoce la marca `dfs_sin_presupuesto` de tools/correr_lote.py y, en lotes viejos
que no la tienen, el motivo «sin datos de Google» en la selección.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

MARCA_VIEJA = "sin datos de Google"


def sin_presupuesto(ficha: dict) -> bool:
    if ficha.get("dfs_sin_presupuesto"):
        return True
    return not ficha.get("keywords") and MARCA_VIEJA in (ficha.get("seleccion") or "")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lote", required=True)
    ap.add_argument("--env", default="prod")
    ap.add_argument("--solo-listar", action="store_true", help="no corre nada")
    a = ap.parse_args(argv)
    ruta = Path(a.lote)
    lote = json.loads(ruta.read_text(encoding="utf-8"))
    rehacer = [f["url"] for f in lote["fichas"] if sin_presupuesto(f)]
    print(f"{len(rehacer)} de {len(lote['fichas'])} fichas salieron sin presupuesto de DataForSEO")
    for u in rehacer:
        print(" ", u)
    if a.solo_listar or not rehacer:
        return 0

    from cassoni.config import Config            # noqa: E402
    from cassoni.orchestrator import Pipeline    # noqa: E402
    from correr_lote import procesar             # noqa: E402
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    cfg = Config.load(a.env, dry_run=True)
    pipe = Pipeline(cfg, dry_run=True, forzar=True)
    pipe.precargar(rehacer)
    nuevas = {}
    for u in rehacer:
        nuevas[u] = procesar(pipe, u)
        print(f"  {nuevas[u]['status']:9} {nuevas[u]['h1']}  kw={nuevas[u]['keywords']}"
              + ("  ⚠ otra vez sin presupuesto" if nuevas[u]["dfs_sin_presupuesto"] else ""))
    lote["fichas"] = [nuevas.get(f["url"], f) for f in lote["fichas"]]
    lote["meta"]["rehechas_sin_presupuesto"] = rehacer
    lote["meta"]["costos_rehechas"] = pipe._costos()
    ruta.write_text(json.dumps(lote, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("actualizado", ruta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
