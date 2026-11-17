# -*- coding: utf-8 -*-
"""Bajan la foto principal de cada ficha (WooCommerce) y la guardan como miniatura
JPEG en base64, para embeberla en las páginas de revisión (las páginas publicadas
no pueden cargar imágenes de otro sitio).

    python tools/fotos_fichas.py --urls a.txt --urls b.txt --out evidencia/fotos.json
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import sys
from pathlib import Path

import requests
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cassoni.config import Config            # noqa: E402
from cassoni.extract import extract_slug     # noqa: E402
from cassoni.woo import WooCommerce          # noqa: E402

ANCHO = 520


def miniatura(src: str) -> str:
    r = requests.get(src, timeout=30)
    r.raise_for_status()
    im = Image.open(io.BytesIO(r.content)).convert("RGB")
    im.thumbnail((ANCHO, ANCHO))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=72, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--urls", action="append", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--env", default="prod")
    a = ap.parse_args(argv)
    woo = WooCommerce(Config.load(a.env, dry_run=True))
    out = json.loads(Path(a.out).read_text(encoding="utf-8")) if Path(a.out).exists() else {}
    urls = [u.strip() for f in a.urls for u in Path(f).read_text(encoding="utf-8").splitlines()
            if u.strip().startswith("http")]
    for u in urls:
        if u in out:
            continue
        try:
            p = woo.get_product_by_slug(extract_slug(u)[0])
            src = ((p.get("images") or [{}])[0]).get("src", "")
            out[u] = miniatura(src) if src else ""
            print(f"ok  {len(out[u]) // 1024:>3} KB  {u}")
        except Exception as exc:
            out[u] = ""
            print(f"sin foto ({exc})  {u}")
    Path(a.out).write_text(json.dumps(out), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
