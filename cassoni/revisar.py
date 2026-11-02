# -*- coding: utf-8 -*-
"""Medición del efecto: comparar la consulta objetivo antes y después de editar.

Sin esto no hay forma de saber si la edición sirvió (auditoría 13-oct: la DB
guardaba el texto, no la posición). La comparación es pura; la consulta a GSC y
el guardado viven en `revisar_url`.
"""
from __future__ import annotations

from typing import Optional

UMBRAL_POSICION = 1.0     # media posición de diferencia ya cuenta
UMBRAL_CLICS_REL = 0.20   # 20% de cambio en clics cuenta si la posición no se movió


def comparar(baseline: dict, actual: dict, *,
             umbral_pos: float = UMBRAL_POSICION,
             umbral_clics: float = UMBRAL_CLICS_REL) -> dict:
    """Compara dos mediciones de la MISMA consulta. Posición menor = mejor."""
    pos_b = float(baseline.get("position") or 0)
    pos_a = float(actual.get("position") or 0)
    clics_b = int(baseline.get("clicks") or 0)
    clics_a = int(actual.get("clicks") or 0)
    impr_b = int(baseline.get("impressions") or 0)
    impr_a = int(actual.get("impressions") or 0)

    dpos = round(pos_a - pos_b, 2) if (pos_a and pos_b) else 0.0
    out = {
        "delta_position": dpos,
        "delta_impressions": impr_a - impr_b,
        "delta_clicks": clics_a - clics_b,
    }
    if dpos <= -umbral_pos:
        out["verdict"] = "subio"
    elif dpos >= umbral_pos:
        out["verdict"] = "bajo"
    elif clics_b > 0:
        rel = (clics_a - clics_b) / clics_b
        out["verdict"] = ("subio" if rel >= umbral_clics
                          else "bajo" if rel <= -umbral_clics else "igual")
    elif clics_a > 0:
        out["verdict"] = "subio"       # de cero clics a alguno
    else:
        out["verdict"] = "igual"
    return out


def revisar_url(db, gsc, url: str, *, days: int = 14) -> dict:
    """Mide el efecto sobre la consulta objetivo de una ficha ya editada."""
    row = db.get_state(url)
    if row is None or not getattr(row, "baseline_keyword", None):
        return {"url": url, "verdict": "sin_baseline", "days": days,
                "reason": "la ficha no tiene línea base (se editó con una versión anterior)"}

    filas = gsc.queries_for_page(url, days=days)
    por_kw = {f.get("keyword"): f for f in filas}
    actual = por_kw.get(row.baseline_keyword)
    if actual is None:
        return {"url": url, "keyword": row.baseline_keyword, "verdict": "sin_datos",
                "days": days,
                "reason": "la consulta objetivo no aparece en la ventana posterior"}

    baseline = {"position": row.baseline_position,
                "impressions": row.baseline_impressions,
                "clicks": row.baseline_clicks,
                "ctr": row.baseline_ctr}
    comp = comparar(baseline, actual)
    db.save_review(url=url, keyword=row.baseline_keyword, days=days,
                   position=actual.get("position"), impressions=actual.get("impressions"),
                   clicks=actual.get("clicks"), ctr=actual.get("ctr"),
                   delta_position=comp["delta_position"],
                   delta_impressions=comp["delta_impressions"],
                   delta_clicks=comp["delta_clicks"], verdict=comp["verdict"])
    return {"url": url, "keyword": row.baseline_keyword, "days": days,
            "position": actual.get("position"),
            "impressions": actual.get("impressions"),
            "clicks": actual.get("clicks"),
            **comp}


def revisar_lote(db, gsc, urls: Optional[list[str]] = None, *, days: int = 14) -> list[dict]:
    """Revisa un lote (o todas las fichas con línea base). Reanudable: sólo lee."""
    if urls is None:
        urls = [r.url for r in _con_baseline(db)]
    return [revisar_url(db, gsc, u, days=days) for u in urls]


def _con_baseline(db) -> list:
    from .db import ProcessedProduct
    with db.Session() as s:
        return list(s.query(ProcessedProduct).filter(
            ProcessedProduct.baseline_keyword.isnot(None)).all())
