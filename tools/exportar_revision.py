# -*- coding: utf-8 -*-
"""Exporta una corrida en seco del flujo v2 a un JSON para que SEO la revise.

Por ficha: H1 antes/después, descripción por bloques con cada oración marcada
como original o agregada, las keywords objetivo (volumen, impresiones, origen),
las consultas descartadas con su motivo, el veredicto del validador, la
conservación y el costo. Opcional: la foto del producto en miniatura (base64).

Uso:
  python tools/exportar_revision.py --db sqlite:///prueba.db --env prod \\
      --out revision.json [--fotos]
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, text          # noqa: E402

from cassoni.checklist import (_BLOQUE_RX, _PUNT_PEGADA_RX, _SENT_RX,  # noqa: E402
                               conservacion, h2_count, norm, oraciones,
                               strip_html, word_count)
from cassoni.config import Config                  # noqa: E402
from cassoni.keywords import cubierta_por_el_h1    # noqa: E402
from cassoni.woo import WooCommerce                # noqa: E402

_ABRE_RX = re.compile(r"<(h[1-6]|p|li|div|section|blockquote|tr)\b", re.I)


def _json(v, default=None):
    if not v:
        return default
    try:
        return json.loads(v)
    except Exception:
        return default


def bloques(html: str, original: str) -> list[dict]:
    """[{tipo: h2|p, frases: [{t, nueva}]}] de la descripción editada."""
    previas = set(oraciones(original))
    out = []
    for crudo in _BLOQUE_RX.split(html or ""):
        if not strip_html(crudo):
            continue
        m = None
        for m in _ABRE_RX.finditer(crudo):
            pass
        tipo = "h2" if m and m.group(1).lower() in ("h1", "h2", "h3") else "p"
        texto = _PUNT_PEGADA_RX.sub(r"\1 ", strip_html(crudo))
        frases = [{"t": s, "nueva": norm(s) not in previas}
                  for s in _SENT_RX.split(texto) if s.strip()]
        out.append({"tipo": tipo, "frases": frases})
    return out


def descartadas(motivo_sel: str) -> list[dict]:
    """Del texto de selection_reason: 'kw (motivo); kw (motivo)'."""
    if "| descartadas: " not in (motivo_sel or ""):
        return []
    parte = motivo_sel.split("| descartadas: ", 1)[1]
    out = []
    for item in parte.split("; "):
        m = re.match(r"^(.*) \((.*)\)$", item.strip())
        if m:
            out.append({"keyword": m.group(1), "motivo": m.group(2)})
    return out


def competidores(motivo_sel: str) -> list[str]:
    m = re.search(r"\| competidores: ([^|]*)", motivo_sel or "")
    return [u.strip() for u in m.group(1).split(",")] if m else []


def valor(f: dict, marca: str) -> dict:
    """El aporte en números: búsquedas de GSC que el H1 nuevo cubre y el viejo no
    (las de marca + modelo), y el volumen mensual de las keywords agregadas."""
    nombre = f.get("original_h1") or ""
    gsc = _json(f.get("gsc_keywords"), []) or []
    nuevas_h1 = [g for g in gsc if cubierta_por_el_h1(g.get("keyword", ""), nombre, marca)
                 and not cubierta_por_el_h1(g.get("keyword", ""), nombre, "")]
    kws = _json(f.get("selected_keywords"), []) or []
    aprobada = f.get("status") == "processed"
    return {"h1_busquedas": [{"keyword": g["keyword"], "impresiones": g.get("impressions")}
                             for g in nuevas_h1],
            "h1_impresiones": sum(g.get("impressions") or 0 for g in nuevas_h1),
            "volumen_nuevo": sum(k.get("volume") or 0 for k in kws) if aprobada else 0}


def miniatura(url: str, ancho: int = 520) -> str:
    """data URI JPEG de ~520px (sips de macOS). '' si no se pudo."""
    if not url:
        return ""
    try:
        import requests
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (CassoniSEO)"})
        if r.status_code != 200 or not r.content:
            return ""
        with tempfile.TemporaryDirectory() as d:
            src, dst = Path(d) / "in", Path(d) / "out.jpg"
            src.write_bytes(r.content)
            subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "72",
                            "-Z", str(ancho), str(src), "--out", str(dst)],
                           check=True, capture_output=True)
            return "data:image/jpeg;base64," + base64.b64encode(dst.read_bytes()).decode()
    except Exception:
        return ""


def exportar(db_url: str, env: str, *, fotos: bool) -> list[dict]:
    eng = create_engine(db_url)
    with eng.connect() as c:
        filas = [dict(r) for r in c.execute(text(
            "SELECT * FROM cassoni_processed_products ORDER BY id")).mappings()]
        objetivos = [dict(r) for r in c.execute(text(
            "SELECT * FROM cassoni_keyword_objetivo ORDER BY id")).mappings()]
    woo = WooCommerce(Config.load(env=env, dry_run=True))
    salida = []
    for f in filas:
        producto = {}
        try:
            producto = woo.get_product_by_slug(f["slug"])
        except Exception:
            pass
        orig = f.get("original_description") or ""
        edit = f.get("edited_description") or orig
        val = _json(f.get("validation_result"), {}) or {}
        sel = f.get("selection_reason") or ""
        marca = ((producto.get("brands") or [{}])[0].get("name") or "")
        salida.append({
            "valor": valor(f, marca),
            "url": f["url"], "status": f["status"], "motivo": f.get("reason") or "",
            "marca": ((producto.get("brands") or [{}])[0].get("name") or ""),
            "categorias": [c2.get("name", "").replace("&amp;", "&")
                           for c2 in (producto.get("categories") or [])],
            "foto": miniatura((producto.get("images") or [{}])[0].get("src", "")) if fotos else "",
            "h1_antes": f.get("original_h1") or "", "h1_despues": f.get("edited_h1") or "",
            "keywords": [{"keyword": o["keyword"], "origen": o.get("origen") or "gsc",
                          "volumen": o.get("volume"),
                          "dificultad": None,
                          "impresiones": o.get("baseline_impressions"),
                          "posicion": o.get("baseline_position"),
                          "compartida_con": o.get("compartida_con")}
                         for o in objetivos if o["url"] == f["url"]],
            "descartadas": descartadas(sel),
            "competidores": competidores(sel),
            "bloques": bloques(edit, orig),
            "validador": {"aprobado": bool(val.get("aprobado")),
                          "issues": val.get("issues") or [], "razon": val.get("razon") or "",
                          "intentos": f.get("validation_attempts")},
            "medido": {"palabras_antes": word_count(orig), "palabras_despues": word_count(edit),
                       "conservacion": round(conservacion(orig, edit), 3),
                       "h2": h2_count(edit)},
            "costo": {"llm_usd": float(f.get("llm_cost") or 0),
                      "dfs_usd": float(f.get("dfs_cost") or 0)},
        })
    return salida


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True)
    p.add_argument("--env", default="prod")
    p.add_argument("--out", required=True)
    p.add_argument("--fotos", action="store_true",
                   help="incluir miniatura de cada producto (solo para la landing: en "
                        "evidencia/ el base64 dispara el escaneo de secretos)")
    a = p.parse_args(argv)
    import datetime as dt
    fichas = exportar(a.db, a.env, fotos=a.fotos)
    datos = {"meta": {"fecha": dt.date.today().strftime("%d-%m-%Y"), "env": a.env,
                      "dry_run": True}, "fichas": fichas}
    Path(a.out).write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(fichas)} fichas → {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
