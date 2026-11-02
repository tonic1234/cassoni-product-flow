# -*- coding: utf-8 -*-
"""Exporta la muestra de fichas desde la base de trazas a un JSON auditable.

Uso:
  python tools/exportar_muestra.py --db sqlite:///muestra.db --out muestra.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text          # noqa: E402

from cassoni.checklist import conservacion, h2_count, word_count  # noqa: E402
from cassoni.config import Config                  # noqa: E402
from cassoni.woo import WooCommerce                # noqa: E402


def _json(v, default=None):
    if not v:
        return default
    try:
        return json.loads(v)
    except Exception:
        return default


def _bajar_imagen(url: str, destino: Path) -> bool:
    """Intenta traer la foto del producto. El CDN de Cassoni responde 403 a TARS
    (protección de hotlink), así que el fallo es esperable y no rompe nada."""
    if not url:
        return False
    try:
        import requests
        r = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (compatible; CassoniSEO/1.0)",
            "Accept": "image/avif,image/webp,image/*,*/*;q=0.8"})
        if r.status_code != 200 or not r.content:
            return False
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(r.content)
        return True
    except Exception:
        return False


def exportar(db_url: str, out: Path, *, con_woo: bool = True,
             assets: Path | None = None) -> list[dict]:
    eng = create_engine(db_url)
    with eng.connect() as c:
        filas = [dict(r) for r in c.execute(text(
            "SELECT * FROM cassoni_processed_products ORDER BY id")).mappings()]

    cfg = Config.load(env="staging", dry_run=True)
    woo = WooCommerce(cfg) if con_woo else None
    salida = []
    for f in filas:
        slug = (f.get("slug") or "").strip()
        producto = {}
        if woo and slug:
            try:
                producto = woo.get_product_by_slug(slug)
            except Exception as exc:
                producto = {"_error": str(exc)}
        gsc = _json(f.get("gsc_keywords"), []) or []
        principal = f.get("baseline_keyword") or ""
        fila_gsc = next((g for g in gsc if (g.get("keyword") or "") == principal), {})
        attrs = [f"{a.get('name')}: {', '.join(str(o) for o in (a.get('options') or []))}"
                 for a in (producto.get("attributes") or [])
                 if a.get("options") and a.get("visible")]
        imagen_remota = (producto.get("images") or [{}])[0].get("src", "")
        imagen, imagen_error = "", ""
        if imagen_remota and assets is not None:
            ext = ".webp" if ".webp" in imagen_remota else ".jpg"
            destino = assets / f"{slug}{ext}"
            if destino.exists() or _bajar_imagen(imagen_remota, destino):
                imagen = f"{assets.name}/{destino.name}"
                imagen = f"../{assets.name}/{destino.name}" if assets.name != "." else destino.name
            else:
                imagen_error = "el CDN del sitio responde 403 a este servidor"
        elif imagen_remota:
            imagen_error = "no se descargó (usar --assets)" 
        salida.append({
            "url": f["url"], "slug": slug, "status": f["status"],
            "woo_id": producto.get("id"),
            "nombre": producto.get("name") or f.get("original_h1"),
            "categorias": [c2.get("name", "").replace("&amp;", "&")
                           for c2 in (producto.get("categories") or [])],
            "marca": ((producto.get("brands") or [{}])[0].get("name") or ""),
            "imagen": imagen,
            "imagen_remota": imagen_remota,
            "imagen_error": imagen_error,
            "atributos": attrs,
            "gsc": {"keyword": principal, "position": fila_gsc.get("position"),
                    "impressions": fila_gsc.get("impressions"),
                    "clicks": fila_gsc.get("clicks"), "ctr": fila_gsc.get("ctr"),
                    "opportunity": fila_gsc.get("opportunity"),
                    "score": fila_gsc.get("opportunity_score")},
            "h1_antes": f.get("original_h1"), "h1_despues": f.get("edited_h1"),
            "desc_antes": f.get("original_description"),
            "desc_despues": f.get("edited_description"),
            "medido": {
                "palabras_antes": word_count(f.get("original_description") or ""),
                "palabras_despues": word_count(f.get("edited_description") or ""),
                "conservacion": round(conservacion(f.get("original_description") or "",
                                                   f.get("edited_description") or ""), 3),
                "h2": h2_count(f.get("edited_description") or ""),
            },
            "keywords": _json(f.get("selected_keywords"), []),
            "validacion": _json(f.get("validation_result"), {}) or {},
            "intentos": f.get("validation_attempts"),
            "costo": {"usd": float(f.get("llm_cost") or 0),
                      "tokens_in": f.get("llm_tokens_in") or 0,
                      "tokens_out": f.get("llm_tokens_out") or 0},
            "baseline": {"posicion": f.get("baseline_position"),
                         "impresiones": f.get("baseline_impressions"),
                         "ventana": f.get("baseline_window")},
        })
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    return salida


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--sin-woo", action="store_true")
    p.add_argument("--assets", default="", help="carpeta para bajar las fotos")
    a = p.parse_args(argv)
    filas = exportar(a.db, Path(a.out), con_woo=not a.sin_woo,
                     assets=Path(a.assets) if a.assets else None)
    ok = sum(1 for f in filas if f["status"] == "processed")
    usd = sum(f["costo"]["usd"] for f in filas)
    print(f"{len(filas)} fichas · {ok} aprobadas · US$ {usd:.4f} total · "
          f"US$ {usd / max(len(filas), 1):.4f} por ficha → {a.out}")


if __name__ == "__main__":
    main()
