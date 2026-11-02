# -*- coding: utf-8 -*-
"""Lógica de Oportunidades de GSC — convierte filas crudas de Search Analytics
(query, posición, impresiones, clics, ctr) en categorías y scores de prioridad.

Puro, sin I/O. Categorías en orden de prioridad de negocio:
  materialize_demand  -> hay demanda (impresiones) pero la página rankea fuera del top;
                         optimizar sube posiciones = la oportunidad de mayor valor.
  lift_ctr            -> la página aparece seguido pero casi nadie entra (ctr bajísimo);
                         optimizar H1/título levanta clics.
  hold_top            -> ya rankea en top; conservar / usar como keyword principal.
  long_tail           -> demanda baja, no prioritario.
"""
from __future__ import annotations

from typing import Iterable

# --- Thresholds (configurables por constante, con defaults validados) ---
MATERIALIZE_POS_MIN = 4          # posición mínima para "demanda que se puede materializar"
MATERIALIZE_POS_MAX = 20         # hasta página ~2: aún vale la pena empujar
MATERIALIZE_IMPRESSIONS = 150    # impresiones mínimas para que exista demanda real
CTR_IMPRESSIONS = 500            # impresiones mínimas para considerar "mucho aparecer"
CTR_MAX = 0.03                    # ctr por debajo de esto es "aparece pero nadie entra"
HOLD_TOP_POS = 3                 # considerar top-ranking lo que está en 1..3

# --- Categorías (ordinal, orden de prioridad) ---
LONG_TAIL = "long_tail"
HOLD_TOP = "hold_top"
LIFT_CTR = "lift_ctr"
MATERIALIZE_DEMAND = "materialize_demand"
_CATEGORY_ORDER = [LONG_TAIL, HOLD_TOP, LIFT_CTR, MATERIALIZE_DEMAND]


def classify(row: dict) -> str:
    """Clasifica una fila de GSC ({position, impressions, clicks, ctr}) en una
    categoría de oportunidad. Devuelve la de MAYOR prioridad que aplique."""
    pos = row.get("position") or 0
    impr = row.get("impressions") or 0
    ctr = row.get("ctr") or 0
    if MATERIALIZE_POS_MIN <= pos <= MATERIALIZE_POS_MAX and impr >= MATERIALIZE_IMPRESSIONS:
        return MATERIALIZE_DEMAND
    if impr >= CTR_IMPRESSIONS and ctr <= CTR_MAX:
        return LIFT_CTR
    if 0 < pos <= HOLD_TOP_POS:
        return HOLD_TOP
    return LONG_TAIL


def opportunity_score(row: dict) -> int:
    """Score de prioridad 0-100. Tránsparente y monótono sobre la demanda."""
    pos = row.get("position") or 0
    impr = row.get("impressions") or 0
    ctr = row.get("ctr") or 0
    cat = classify(row)
    if cat == MATERIALIZE_DEMAND:
        # más cerca del top (pos baja) y más demanda -> más alto
        return int(min(100, 55 + max(0, (MATERIALIZE_POS_MAX - pos))
                       + min(25, impr // 100)))
    if cat == LIFT_CTR:
        return int(min(90, 55 + min(35, impr // 200)))
    if cat == HOLD_TOP:
        return 40
    return 0  # long_tail


def annotate(rows: Iterable[dict]) -> list[dict]:
    """Devuelve una NUEVA lista, cada fila enriquecida con `opportunity` y
    `opportunity_score`. No muta las filas de entrada."""
    out = []
    for r in rows:
        r2 = dict(r)
        r2["opportunity"] = classify(r2)
        r2["opportunity_score"] = opportunity_score(r2)
        out.append(r2)
    return out


def top_opportunities(rows: Iterable[dict], top_n: int = 10) -> list[dict]:
    """Ordena las filas por opportunity_score desc y devuelve las top `top_n`
    (todas por encima de score 0; nunca incluye long_tail)."""
    scored = annotate(rows)
    ranked = sorted(scored, key=lambda r: r["opportunity_score"], reverse=True)
    valuable = [r for r in ranked if r["opportunity_score"] > 0]
    return valuable[:top_n]


def has_opportunity(row: dict) -> bool:
    """True si la fila es una oportunidad real (no long_tail)."""
    return classify(row) != LONG_TAIL

def ordenar_candidatas(candidates: Iterable[dict]) -> list[dict]:
    """Devuelve una NUEVA lista ordenada por oportunidad; el volumen desempata.

    Si ninguna candidata trae datos de GSC (position/impressions), se respeta el
    orden recibido: es la degradación cuando sólo hay volumen de DataForSEO.
    """
    filas = [dict(c) for c in candidates]
    if not any("position" in f or "impressions" in f for f in filas):
        return filas
    anotadas = annotate(filas)
    anotadas.sort(key=lambda r: (r["opportunity_score"], r.get("volume") or 0,
                                 r.get("impressions") or 0), reverse=True)
    return anotadas


def elegir_principal(candidates: Iterable[dict]) -> str:
    """La keyword principal: la de mayor oportunidad (volumen como desempate)."""
    ordenadas = ordenar_candidatas(candidates)
    return (ordenadas[0].get("keyword") or "") if ordenadas else ""


def fusionar_gsc(candidates: Iterable[dict], gsc_rows: Iterable[dict]) -> list[dict]:
    """Pega a cada candidata los datos de GSC de su misma consulta.

    DataForSEO devuelve sólo volumen; sin esto, al elegir la principal se pierde la
    posición y las impresiones (o sea, la señal de oportunidad). Match por keyword
    normalizada; las candidatas sin fila de GSC quedan como vinieron.
    """
    def norm(s: str) -> str:
        return " ".join((s or "").lower().split())

    por_kw = {norm(r.get("keyword", "")): r for r in gsc_rows if r.get("keyword")}
    out = []
    for c in candidates:
        c2 = dict(c)
        g = por_kw.get(norm(c2.get("keyword", "")))
        if g:
            for campo in ("impressions", "clicks", "ctr", "position"):
                if campo in g and campo not in c2:
                    c2[campo] = g[campo]
        out.append(c2)
    return out
