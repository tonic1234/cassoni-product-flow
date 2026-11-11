# -*- coding: utf-8 -*-
"""Corre un lote de fichas EN SECO (nada se escribe en WooCommerce) y guarda el
resultado completo en un JSON de evidencia, con el hash del commit.

    ./venv/bin/python tools/correr_lote.py --urls lista.txt --out evidencia/X.json
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cassoni.config import Config            # noqa: E402
from cassoni.orchestrator import Pipeline    # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--urls", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--env", default="prod")
    a = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    cfg = Config.load(a.env, dry_run=True)
    pipe = Pipeline(cfg, dry_run=True, forzar=True)
    urls = [u.strip() for u in Path(a.urls).read_text().splitlines()
            if u.strip() and not u.startswith("#")]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                            text=True).stdout.strip()
    sucio = bool(subprocess.run(["git", "status", "--porcelain", "cassoni"],
                                capture_output=True, text=True).stdout.strip())
    pipe.precargar(urls)          # volumen en 2 pedidos para todo el lote
    fichas = []
    for u in urls:
        t0 = time.time()
        r = pipe.process(u)
        fila = pipe.db.get_state(u)
        fichas.append({
            "url": u, "status": r.status, "reason": r.reason,
            "h1_original": getattr(fila, "original_h1", None),
            "h1": r.edited_h1, "descripcion": r.edited_description,
            "descripcion_original": getattr(fila, "original_description", None),
            "keywords": [k["keyword"] for k in r.selected],
            "keywords_detalle": r.selected,
            "seleccion": getattr(fila, "selection_reason", None),
            "validacion": json.loads(fila.validation_result) if getattr(
                fila, "validation_result", None) else None,
            "intentos": getattr(fila, "validation_attempts", None),
            "segundos": round(time.time() - t0, 1)})
        print(f"[{len(fichas)}/{len(urls)}] {r.status:9} {r.edited_h1}  kw={fichas[-1]['keywords']}",
              flush=True)
    out = {"meta": {"modo": cfg.modo_descripcion, "llm": cfg.llm_editor_model,
                    "commit": commit, "codigo_con_cambios_sin_commit": sucio,
                    "dry_run": True, "costos": pipe._costos()},
           "fichas": fichas}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))
    print("guardado en", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
