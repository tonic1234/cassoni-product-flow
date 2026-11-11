# -*- coding: utf-8 -*-
"""Elige las fichas de la PRUEBA CIEGA sin intervención humana: al azar, con una
semilla fija y publicada, entre las fichas que ya reciben impresiones en Google
(GSC, 90 días), estratificadas por familia de categoría. Quedan afuera las 10
fichas de ajuste que el SEO ya revisó.

Que la elección sea por código evita que quien ajustó el agente elija fichas
"fáciles". Cualquiera puede repetirla con la misma semilla y el mismo día de GSC.

    ./venv/bin/python tools/elegir_muestra_ciega.py --semilla 20261111 --n 10 \
        --excluir lista_ajuste.txt --out evidencia/X-muestra-ciega.txt
"""
from __future__ import annotations

import argparse
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cassoni.config import Config            # noqa: E402
from cassoni.extract import extract_slug     # noqa: E402
from cassoni.gsc import GSCClient            # noqa: E402
from cassoni.selector import es_producto     # noqa: E402
from cassoni.woo import WooCommerce          # noqa: E402

MIN_IMPRESIONES = 50


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--semilla", type=int, required=True)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--excluir", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cfg = Config.load("prod")
    gsc, woo = GSCClient(cfg), WooCommerce(cfg)
    excluir = {u.strip().rstrip("/") for u in (Path(a.excluir).read_text().splitlines()
                                              if a.excluir else []) if u.strip()}
    paginas = sorted({p["url"].rstrip("/") + "/" for p in gsc.pages()
                      if es_producto(p.get("url", "")) and (p.get("impressions") or 0)
                      >= MIN_IMPRESIONES and p["url"].rstrip("/") not in excluir})
    rnd = random.Random(a.semilla)
    rnd.shuffle(paginas)
    por_familia: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for url in paginas[: a.n * 8]:            # se mira un tramo, no las 13.000
        try:
            p = woo.get_product_by_slug(extract_slug(url)[0])
        except Exception:
            continue
        if p.get("status") != "publish" or not p.get("categories"):
            continue
        ruta = woo.ruta_categoria(p["categories"][0]["id"])
        familia = ruta[0]["slug"] if ruta else "otra"
        por_familia[familia].append((url, p.get("name", "")))
    elegidas: list[tuple[str, str, str]] = []
    familias = sorted(por_familia)
    while len(elegidas) < a.n and any(por_familia.values()):
        for f in familias:                   # una por familia por vuelta
            if por_familia[f] and len(elegidas) < a.n:
                url, nombre = por_familia[f].pop(0)
                elegidas.append((f, url, nombre))
    lineas = [f"# semilla {a.semilla}, {len(paginas)} fichas con >= {MIN_IMPRESIONES} "
              f"impresiones en GSC, estratificadas por familia"]
    lineas += [f"# {f}: {n}" for f, _, n in elegidas]
    lineas += [u for _, u, _ in elegidas]
    Path(a.out).write_text("\n".join(lineas) + "\n")
    print("\n".join(lineas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
