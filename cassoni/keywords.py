# -*- coding: utf-8 -*-
"""Selección de las keywords objetivo de una ficha (regla SEO del 3-nov-2026).

    keywords de GSC + volumen de DataForSEO
      → que sean de ESTE producto (relevancia)
      → que NO estén ya en la descripción larga (frase exacta)
      → con volumen de búsqueda (o impresiones reales si DFS no informa)
      → anti-canibalización: H1 de fichas hermanas, categorías, intención de blog,
        y keywords ya escritas en OTRAS fichas (en la medida de lo posible)
      → una sola keyword por palabra compartida
      → las 3 de más volumen

Puro, sin I/O: todo llega por parámetro y es testeable sin red.
"""
from __future__ import annotations

from typing import Iterable, Optional

from .checklist import (filtrar_canibalizacion, kw_exacta_en, seleccionar_diversas,
                        strip_html)
from .selector import relevante

N_OBJETIVO = 3
MIN_IMPRESIONES_SIN_VOLUMEN = 30   # DFS no informa: alcanza con demanda real en GSC


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def _con_demanda(fila: dict, min_volume: int) -> bool:
    vol = fila.get("volume")
    if vol is not None:
        return vol >= min_volume
    return (fila.get("impressions") or 0) >= MIN_IMPRESIONES_SIN_VOLUMEN


def _orden(fila: dict) -> tuple:
    return (fila.get("volume") or 0, fila.get("impressions") or 0)


def elegir_keywords(candidatas: Iterable[dict], *, descripcion: str,
                    texto_producto: str, h1_hermanas: Iterable[str] = (),
                    categorias: Iterable[str] = (),
                    asignadas: Optional[dict[str, str]] = None,
                    min_volume: int = 10, n: int = N_OBJETIVO) -> dict:
    """Devuelve {elegidas, descartadas, faltan}.

    `candidatas`: [{keyword, volume?, impressions?, position?, ...}]
    `asignadas`: {keyword normalizada: url} de keywords ya escritas en otras fichas.
    Una keyword asignada a otra ficha solo se usa si no quedan alternativas, y
    sale marcada con `compartida_con` para que SEO lo vea.
    """
    asignadas = asignadas or {}
    plano = strip_html(descripcion)
    descartadas: list[dict] = []
    vistas: set[str] = set()
    vivas: list[dict] = []

    for c in candidatas:
        kw = (c.get("keyword") or "").strip()
        nk = _norm(kw)
        if not nk or nk in vistas:
            continue
        vistas.add(nk)
        if not relevante(kw, texto_producto):
            descartadas.append({"keyword": kw, "motivo": "no es de este producto"})
        elif kw_exacta_en(plano, kw):
            descartadas.append({"keyword": kw, "motivo": "ya está en la descripción"})
        elif not _con_demanda(c, min_volume):
            descartadas.append({"keyword": kw, "motivo": "sin volumen de búsqueda"})
        else:
            vivas.append(dict(c, keyword=kw))

    filtro = filtrar_canibalizacion([c["keyword"] for c in vivas],
                                    principals_ya_usadas=h1_hermanas,
                                    categorias_como_pagina=categorias)
    pasan = {_norm(f["keyword"]) for f in filtro["aceptadas"]}
    for d in filtro["descartadas"]:
        descartadas.append({"keyword": d["keyword"], "motivo": d["motivo"]})
    vivas = [c for c in vivas if _norm(c["keyword"]) in pasan]

    libres = [c for c in vivas if _norm(c["keyword"]) not in asignadas]
    reserva = [dict(c, compartida_con=asignadas[_norm(c["keyword"])])
               for c in vivas if _norm(c["keyword"]) in asignadas]

    libres.sort(key=_orden, reverse=True)
    div = seleccionar_diversas([dict(c, opportunity_score=0) for c in libres], max_sec=n)
    elegidas = [{k: v for k, v in c.items() if k != "opportunity_score"}
                for c in div["elegidas"]]
    for o in div["omitidas"]:
        descartadas.append({"keyword": o["keyword"], "motivo": o["motivo"]})

    # "en la medida de lo posible": si faltan, se completa con las ya usadas en
    # otra ficha antes que quedarse corto (y queda registrado con quién choca)
    if len(elegidas) < n and reserva:
        reserva.sort(key=_orden, reverse=True)
        div2 = seleccionar_diversas([dict(c, opportunity_score=0) for c in elegidas + reserva],
                                    max_sec=n)
        elegidas = [{k: v for k, v in c.items() if k != "opportunity_score"}
                    for c in div2["elegidas"]]
    usadas = {_norm(e["keyword"]) for e in elegidas}
    for r in reserva:
        if _norm(r["keyword"]) not in usadas:
            descartadas.append({"keyword": r["keyword"],
                                "motivo": f"ya está en otra ficha ({r['compartida_con']})"})

    return {"elegidas": elegidas, "descartadas": descartadas,
            "faltan": max(0, n - len(elegidas))}
