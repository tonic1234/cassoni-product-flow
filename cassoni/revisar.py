# -*- coding: utf-8 -*-
"""Medición del efecto: cada keyword objetivo, antes y después de editar.

Corrección del 3-nov-2026 (auditoría): la versión anterior comparaba la suma de
90 días de antes contra la suma de 14 días de después, así que casi todo salía
"bajó". Ahora, para N días:

    antes   = [edición - N, edición - 1]
    después = [edición + 1, edición + N]

Mismo largo de ventana, y las dos se piden a GSC en el momento de revisar (GSC
guarda 16 meses). Solo se miden fichas ESCRITAS de verdad (applied=1): las
corridas en seco y las rechazadas no se editaron, no hay efecto que medir.
GSC tarda ~3 días en consolidar: antes de edición + N + 3 queda "pendiente".
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

UMBRAL_POSICION = 1.0     # media posición de diferencia ya cuenta
UMBRAL_CLICS_REL = 0.20   # 20% de cambio en clics cuenta si la posición no se movió
DEMORA_GSC_DIAS = 3


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
    elif impr_b == 0 and impr_a > 0:
        out["verdict"] = "aparecio"    # keyword nueva (p. ej. de competidores)
    else:
        out["verdict"] = "igual"
    return out


def ventanas(editada: dt.date, days: int) -> tuple[tuple[dt.date, dt.date],
                                                    tuple[dt.date, dt.date]]:
    antes = (editada - dt.timedelta(days=days), editada - dt.timedelta(days=1))
    despues = (editada + dt.timedelta(days=1), editada + dt.timedelta(days=days))
    return antes, despues


def _por_kw(filas: list[dict]) -> dict:
    return {" ".join((f.get("keyword") or "").lower().split()): f for f in filas}


def revisar_url(db, gsc, url: str, *, days: int = 14,
                hoy: Optional[dt.date] = None) -> dict:
    """Mide el efecto de cada keyword objetivo de una ficha ya escrita."""
    hoy = hoy or dt.date.today()
    row = db.get_state(url)
    objetivos = db.objetivos_de(url) if row is not None else []
    if row is None or not row.applied or not row.edited_at or not objetivos:
        return {"url": url, "verdict": "sin_baseline", "days": days,
                "reason": "la ficha no se escribió con el flujo v2 (sin keywords "
                          "objetivo o corrida en seco)"}
    editada = row.edited_at.date()
    if hoy < editada + dt.timedelta(days=days + DEMORA_GSC_DIAS):
        return {"url": url, "verdict": "pendiente", "days": days,
                "reason": f"se puede medir desde el "
                          f"{editada + dt.timedelta(days=days + DEMORA_GSC_DIAS)}"}

    (a0, a1), (d0, d1) = ventanas(editada, days)
    antes = _por_kw(gsc.queries_for_page(url, start=a0, end=a1))
    despues = _por_kw(gsc.queries_for_page(url, start=d0, end=d1))
    medidas = []
    for o in objetivos:
        k = " ".join(o.keyword.lower().split())
        b = antes.get(k) or {}
        a = despues.get(k) or {}
        comp = comparar(b, a) if (a or b) else {"delta_position": 0.0,
                                                "delta_impressions": 0,
                                                "delta_clicks": 0, "verdict": "sin_datos"}
        db.save_review(url=url, keyword=o.keyword, days=days,
                       position=a.get("position"), impressions=a.get("impressions"),
                       clicks=a.get("clicks"), ctr=a.get("ctr"),
                       delta_position=comp["delta_position"],
                       delta_impressions=comp["delta_impressions"],
                       delta_clicks=comp["delta_clicks"], verdict=comp["verdict"])
        medidas.append({"keyword": o.keyword, "origen": o.origen,
                        "antes": {c: b.get(c) for c in ("position", "impressions", "clicks")},
                        "despues": {c: a.get(c) for c in ("position", "impressions", "clicks")},
                        **comp})
    veredictos = [m["verdict"] for m in medidas]
    resumen = ("subio" if any(v in ("subio", "aparecio") for v in veredictos)
               and "bajo" not in veredictos
               else "bajo" if "bajo" in veredictos and not any(
                   v in ("subio", "aparecio") for v in veredictos)
               else "mixto" if "bajo" in veredictos else "igual")
    return {"url": url, "days": days, "editada": editada.isoformat(),
            "ventana_antes": f"{a0}..{a1}", "ventana_despues": f"{d0}..{d1}",
            "verdict": resumen, "keywords": medidas}


def revisar_lote(db, gsc, urls: Optional[list[str]] = None, *, days: int = 14) -> list[dict]:
    """Revisa un lote (o todas las fichas escritas). Reanudable: sólo lee."""
    if urls is None:
        urls = [r.url for r in _escritas(db)]
    return [revisar_url(db, gsc, u, days=days) for u in urls]


def _escritas(db) -> list:
    from .db import ProcessedProduct
    with db.Session() as s:
        return list(s.query(ProcessedProduct).filter(
            ProcessedProduct.applied == 1).all())
