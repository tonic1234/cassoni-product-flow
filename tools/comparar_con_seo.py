# -*- coding: utf-8 -*-
"""Compara una corrida en seco con la referencia del SEO (hoja del 6-nov):
estructura de la descripción, H1 propuesto por SEO vs. agente, y keywords que
de verdad son NUEVAS en cada ficha (no estaban en el H1 ni en la descripción).

    python tools/comparar_con_seo.py --lote X.json [--lote Y.json] [--seo hoja.csv]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cassoni.checklist import h2_count, strip_html, usos_de, word_count  # noqa: E402

PULG = re.compile(r'\d+(?: \d+/\d+)?"\s*[WDH]')


def estructura(desc: str) -> dict:
    return {"palabras": word_count(desc), "h2": h2_count(desc),
            "apertura": bool(re.match(r"\s*<p>", desc or "")),
            "lista": "<ul>" in (desc or ""), "medidas_pulg": bool(PULG.search(strip_html(desc))),
            "enlace_categoria": "product-category/" in (desc or "")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lote", action="append", required=True)
    ap.add_argument("--seo", default="")
    a = ap.parse_args(argv)
    seo = {}
    if a.seo:
        filas = list(csv.reader(Path(a.seo).read_text(encoding="utf-8").splitlines()))
        cab = next(i for i, f in enumerate(filas) if f and f[0] == "#")
        for f in filas[cab + 1:]:
            if len(f) > 9 and f[1].startswith("http"):
                seo[f[1].rstrip("/")] = {"h1": f[9], "nota": f[8], "kw_viejas": f[6]}
    total = {"fichas": 0, "con_kw": 0, "kw": 0, "vol": 0, "cumple": 0}
    for ruta in a.lote:
        d = json.loads(Path(ruta).read_text(encoding="utf-8"))
        print(f"\n=== {ruta}")
        for f in d["fichas"]:
            if f["status"] not in ("processed", "rejected"):
                continue
            total["fichas"] += 1
            antes = (f.get("h1_original") or "") + " " + strip_html(f.get("descripcion_original") or "")
            nueva = strip_html(f.get("descripcion") or "")
            nuevas = [k for k in f["keywords_detalle"]
                      if usos_de(k["keyword"], antes) == 0 and usos_de(k["keyword"], nueva) > 0]
            e = estructura(f.get("descripcion") or "")
            ok = (1 <= e["h2"] <= 2 and e["apertura"] and e["enlace_categoria"]
                  and 70 <= e["palabras"] <= 200)
            total["cumple"] += ok
            total["con_kw"] += bool(nuevas)
            total["kw"] += len(nuevas)
            total["vol"] += sum(k.get("volume") or 0 for k in nuevas)
            s = seo.get(f["url"].rstrip("/"), {})
            print(f"- {f['h1_original']}: {word_count(f.get('descripcion_original') or '')}→"
                  f"{e['palabras']} pal · h2={e['h2']} lista={e['lista']} "
                  f"medidas={e['medidas_pulg']} enlace={e['enlace_categoria']} "
                  f"{'PLANTILLA OK' if ok else 'NO CUMPLE'}")
            print(f"    H1 agente: {f['h1']}")
            if s:
                print(f"    H1 SEO   : {s['h1']}   (nota 6-nov: {s['nota']})")
            print(f"    kw nuevas: {[(k['keyword'], k.get('volume')) for k in nuevas]}")
    print(f"\nTOTAL {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
