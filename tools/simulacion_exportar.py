# -*- coding: utf-8 -*-
"""Simulación de modelo (13-nov): exporta, por ficha, exactamente lo que recibe el LLM
(datos de la ficha para el redactor y candidatas para la selección), para que otro
modelo -o una persona- responda a mano y se pase después por los mismos controles
(tools/simulacion_validar.py).

    python tools/simulacion_exportar.py --urls lista.txt --out entradas.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cassoni.checklist import strip_html                    # noqa: E402
from cassoni.config import Config                           # noqa: E402
from cassoni.criterio_seo import candidatas_gsc, con_volumen  # noqa: E402
from cassoni.extract import extract_slug                    # noqa: E402
from cassoni.investigacion import materiales_del_texto      # noqa: E402
from cassoni.orchestrator import Pipeline                   # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--urls", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    cfg = Config.load("prod", dry_run=True)
    pipe = Pipeline(cfg, dry_run=True, forzar=True, investigacion=None)
    urls = [u.strip() for u in Path(a.urls).read_text(encoding="utf-8").splitlines()
            if u.strip().startswith("http")]
    out = []
    for u in urls:
        p = pipe._producto(extract_slug(u)[0])
        ctx = pipe._contexto(u, p)
        gen = pipe._genericas(p)
        vol = pipe.volumenes.obtener(gen) if gen else {}
        cands = candidatas_gsc(ctx["kw_rows"], ctx["nombre"], ctx["marca"]) + con_volumen(gen, vol)
        ficha = pipe._ficha_para_redactor(u, p, ctx, p.get("short_description", "") or "")
        ficha["materiales"] = materiales_del_texto(" ".join(
            [ctx["nombre"], *ctx["atributos"], strip_html(ctx["desc_orig"])]))
        ficha["candidatas"] = cands
        out.append(ficha)
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"guardado en {a.out} · DataForSEO US$ {pipe._costos()['dfs_usd']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
