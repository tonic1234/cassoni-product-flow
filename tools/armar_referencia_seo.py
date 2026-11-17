# -*- coding: utf-8 -*-
"""Arma la referencia del SEO que usa el agente como ejemplos: por cada ficha que
hizo el SEO (su documento del 6-nov), las candidatas que el agente le arma (GSC +
genéricas con volumen) y lo que el SEO eligió, su H1 y su descripción.

    python tools/armar_referencia_seo.py \\
        --seo evidencia/2026-11-06-seo-referencia-descripciones.json \\
        --out evidencia/referencia-seo.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cassoni.checklist import strip_html                        # noqa: E402
from cassoni.config import Config                               # noqa: E402
from cassoni.criterio_seo import (candidatas_gsc, clave, con_volumen,  # noqa: E402
                                  genericas)
from cassoni.extract import extract_slug                        # noqa: E402
from cassoni.investigacion import materiales_del_texto          # noqa: E402
from cassoni.orchestrator import Pipeline                       # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seo", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--env", default="prod")
    a = ap.parse_args(argv)
    cfg = Config.load(a.env, dry_run=True)
    pipe = Pipeline(cfg, dry_run=True, forzar=True, investigacion=None)
    seo = json.loads(Path(a.seo).read_text(encoding="utf-8"))
    base = []
    for r in seo:
        p = pipe._producto(extract_slug(r["url"])[0])
        ctx = pipe._contexto(r["url"], p)
        gen = genericas(ctx["nombre"], ctx["marca"], ctx["tipo"], ctx["atributos"], ctx["desc_orig"])
        base.append((r, ctx, gen))
    vol = pipe.volumenes.obtener([g for _, _, gen in base for g in gen]
                                 + [k for r, _, _ in base for k in r["keywords"]])
    out = []
    for r, ctx, gen in base:
        cands = candidatas_gsc(ctx["kw_rows"], ctx["nombre"], ctx["marca"]) + con_volumen(gen, vol)
        claves = {clave(c["keyword"]) for c in cands}
        # lo que el SEO eligió y el agente no tenía como candidata: se agrega para que
        # el ejemplo sea coherente, y se informa
        for k in r["keywords"]:
            if clave(k) not in claves:
                v = (vol.get(k.lower()) or {}).get("volume")
                print(f"  {ctx['nombre']}: el SEO eligió '{k}' (vol {v}) y no era candidata")
                cands.append({"keyword": k, "origen": "generica", "volumen": v})
        out.append({"url": r["url"], "nombre": ctx["nombre"], "marca": ctx["marca"],
                    "tipo": ctx["tipo"],
                    "materiales": materiales_del_texto(" ".join(
                        [ctx["nombre"], *ctx["atributos"], strip_html(ctx["desc_orig"])])),
                    "candidatas": cands, "keywords_seo": r["keywords"], "h1_seo": r["h1"],
                    "descripcion_seo": r["descripcion"], "url_categoria_seo": r["url_categoria"]})
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"guardado en {a.out} · DataForSEO US$ {pipe._costos()['dfs_usd']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
