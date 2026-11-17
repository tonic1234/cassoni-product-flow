# -*- coding: utf-8 -*-
"""Pasa respuestas escritas fuera del agente (otro modelo, una persona) por los MISMOS
controles: la selección tiene que salir de las candidatas, el H1 y la descripción pasan
por `redactor.controles` (código) y, si se pide, por el validador LLM del agente como
juez independiente. Guarda el resultado con el formato de tools/correr_lote.py.

    python tools/simulacion_validar.py --entradas entradas.json --respuestas resp.json \\
        --out evidencia/X.json --modelo "Claude (simulación en sesión)" [--juez]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cassoni.config import Config            # noqa: E402
from cassoni.llm import LLMClient            # noqa: E402
from cassoni.redactor import controles       # noqa: E402
from cassoni.validator import Validator      # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entradas", required=True)
    ap.add_argument("--respuestas", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--modelo", required=True)
    ap.add_argument("--juez", action="store_true", help="validador LLM del agente como juez")
    a = ap.parse_args(argv)
    entradas = json.loads(Path(a.entradas).read_text(encoding="utf-8"))
    respuestas = json.loads(Path(a.respuestas).read_text(encoding="utf-8"))
    assert len(entradas) == len(respuestas), "una respuesta por ficha"
    cfg = Config.load("prod", dry_run=True)
    llm = LLMClient(cfg)
    juez = Validator(cfg, llm) if a.juez else None
    fichas = []
    for ficha, r in zip(entradas, respuestas):
        cands = {c["keyword"].lower(): c for c in ficha["candidatas"]}
        fuera = [k for k in r["keywords"] if k.lower() not in cands]
        elegidas = [cands[k.lower()] for k in r["keywords"] if k.lower() in cands]
        redactado = {"h1": r["h1"], "description": r["description"],
                     "keywords": [{"keyword": k} for k in r["keywords"]], "omitidas": []}
        issues = [f"keyword fuera de la lista de candidatas: {k}" for k in fuera]
        issues += controles(ficha, redactado, [e["keyword"] for e in elegidas])
        val = {"aprobado": not issues, "issues": issues, "razon": "reglas en código"}
        if not issues and juez is not None:
            val = juez.validate_reescritura(ficha=ficha, redactado=redactado,
                                            keywords=[e["keyword"] for e in elegidas])
            val["razon"] = "juez (validador del agente): " + str(val.get("razon", ""))
        fichas.append({
            "url": ficha["url"], "status": "processed" if val.get("aprobado") else "rejected",
            "reason": "simulación (dry run)", "h1_original": ficha["nombre"],
            "h1": r["h1"], "descripcion": r["description"],
            "descripcion_original": ficha["descripcion"],
            "keywords": [e["keyword"] for e in elegidas],
            "keywords_detalle": [{**e, "volume": e.get("volumen"),
                                  "impressions": e.get("impresiones")} for e in elegidas],
            "seleccion": "elegidas: " + (", ".join(r["keywords"]) or "ninguna")
                         + " | por qué: " + r.get("por_que", ""),
            "validacion": val, "intentos": r.get("intentos", 1)})
        estado = "ok " if val.get("aprobado") else "NO "
        print(f"{estado} {r['h1']}  kw={r['keywords']}")
        for i in val.get("issues") or []:
            print(f"      - {i}")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                            text=True).stdout.strip()
    out = {"meta": {"modo": "reescritura", "llm": a.modelo, "commit": commit,
                    "codigo_con_cambios_sin_commit": True, "dry_run": True,
                    "simulacion": True,
                    "costos": {**llm.consumo(), "dfs_usd": 0.0,
                               "nota": "solo el juez; la redacción no tuvo costo de API"}},
           "fichas": fichas}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = sum(f["status"] == "processed" for f in fichas)
    print(f"\n{ok}/{len(fichas)} aprobadas · guardado en {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
