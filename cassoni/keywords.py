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

import re
import unicodedata
from typing import Iterable, Optional

from .checklist import (filtrar_canibalizacion, kw_exacta_en, seleccionar_diversas,
                        strip_html)
from .selector import relevante

N_OBJETIVO = 3
MIN_IMPRESIONES_SIN_VOLUMEN = 30   # DFS no informa: alcanza con demanda real en GSC


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def _palabras(texto: str) -> set[str]:
    plano = unicodedata.normalize("NFKD", (texto or "").lower()).encode("ascii", "ignore").decode()
    return set(re.findall(r"[a-z]+", plano))


def _distancia(a: str, b: str) -> int:
    """Levenshtein (las palabras son cortas: alcanza la versión simple)."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _plural(a: str, b: str) -> bool:
    return a == b + "s" or b == a + "s" or a == b + "es" or b == a + "es"


def parece_typo(keyword: str, nombre: str) -> bool:
    """'rock coffe table' o 'club sofs': una palabra que no está en el NOMBRE del
    producto (ni la marca) pero está a una letra de una que sí, sin ser su
    plural. Se descarta para no escribir el error en la ficha. Solo se compara
    contra el nombre: contra todo el texto había falsos positivos ('grand' por
    'brand', 'what' por 'that'). Prueba real del 3-nov-2026."""
    producto = {w for w in _palabras(nombre) if len(w) >= 4}
    for w in _palabras(keyword):
        if len(w) < 4 or w in producto:
            continue
        if any(not _plural(w, p) and abs(len(w) - len(p)) <= 1 and _distancia(w, p) == 1
               for p in producto):
            return True
    return False


# palabras de tipo de producto que se usan como sinónimo en las búsquedas
_SINONIMOS_TIPO = {
    "sofa": {"couch", "settee", "sectional", "loveseat"},
    "couch": {"sofa", "settee"},
    "chair": {"armchair", "seat", "seating"},
    "armchair": {"chair", "seat"},
    "lamp": {"light", "lighting", "sconce", "luminaire", "fixture"},
    "sconce": {"lamp", "light", "lighting"},
    "table": {"desk"},
    "bed": {"headboard", "bedframe"},
    "mirror": {"looking"},
    "nightstand": {"bedside"},
    "sideboard": {"credenza", "buffet"},
}
# fuera siempre, cuide la marca (prueba real: 'shibari bondage' en una silla)
PALABRAS_SENSIBLES = {"bondage", "bdsm", "sex", "sexual", "porn", "nude", "naked",
                      "erotic", "fetish", "xxx", "nsfw"}


def tipo_de_producto(nombre: str, categorias: Iterable[str] = ()) -> set[str]:
    """Palabras que dicen QUÉ es el producto: la última palabra del nombre
    ('Club Sofa' → sofa, 'Cleopatra Chair (SC1019)' → chair) más las de la
    categoría, con sus sinónimos."""
    limpio = re.sub(r"\(.*?\)", " ", nombre or "")
    palabras = [w for w in re.findall(r"[a-z]+", _plano(limpio)) if len(w) >= 3]
    tipos = {_singular(palabras[-1])} if palabras else set()
    for c in categorias:
        tipos |= {_singular(w) for w in _palabras(c) if len(w) >= 3}
    for t in list(tipos):
        tipos |= _SINONIMOS_TIPO.get(t, set())
    return tipos


def nombra_el_tipo(keyword: str, tipos: set[str]) -> bool:
    return bool({_singular(w) for w in _palabras(keyword)} & tipos)


def _plano(s: str) -> str:
    return unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()


def es_especifica(keyword: str, texto_especifico: str, categorias: Iterable[str]) -> bool:
    """Comparte al menos una palabra con el nombre, la marca o los atributos que
    NO sea una palabra de la categoría. 'sectionals' sola no dice nada de ESTE
    producto; 'club sofa' sí ('club')."""
    de_categoria = set()
    for c in categorias:
        de_categoria |= {_singular(w) for w in _palabras(c)}
    propias = {_singular(w) for w in _palabras(texto_especifico) if len(w) >= 3} - de_categoria
    return bool({_singular(w) for w in _palabras(keyword)} & propias)


def _singular(w: str) -> str:
    return w[:-1] if len(w) > 4 and w.endswith("s") else w


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
                    min_volume: int = 10, n: int = N_OBJETIVO,
                    texto_especifico: Optional[str] = None,
                    nombre: Optional[str] = None, marca: str = "") -> dict:
    """Devuelve {elegidas, descartadas, faltan}.

    `candidatas`: [{keyword, volume?, impressions?, position?, ...}]
    `asignadas`: {keyword normalizada: url} de keywords ya escritas en otras fichas.
    `texto_especifico`: nombre + marca + atributos; si se pasa, la keyword tiene
    que compartir una palabra con eso que no sea de la categoría.
    `nombre`: si se pasa, la keyword tiene que nombrar el tipo de producto
    ('hermes brand' no habla de la Hermes Maxi Bed) y el tipeo se mide contra él.
    Una keyword asignada a otra ficha solo se usa si no quedan alternativas, y
    sale marcada con `compartida_con` para que SEO lo vea.
    """
    asignadas = asignadas or {}
    categorias = list(categorias)
    tipos = tipo_de_producto(nombre, categorias) if nombre is not None else set()
    if nombre is not None and texto_especifico:
        # los atributos reales también identifican el producto ('boucle upholstery')
        tipos |= {_singular(w) for w in
                  _palabras(texto_especifico) - _palabras(nombre) - _palabras(marca)
                  if len(w) >= 4}
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
        if _palabras(kw) & PALABRAS_SENSIBLES:
            descartadas.append({"keyword": kw, "motivo": "contenido sensible"})
        elif not relevante(kw, texto_producto):
            descartadas.append({"keyword": kw, "motivo": "no es de este producto"})
        elif c.get("spell") or parece_typo(kw, f"{nombre} {marca}" if nombre is not None
                                           else texto_producto):
            descartadas.append({"keyword": kw, "motivo": "parece un error de tipeo"})
        elif nombre is not None and not nombra_el_tipo(kw, tipos):
            descartadas.append({"keyword": kw,
                                "motivo": "no nombra el producto ni un atributo real"})
        elif texto_especifico is not None and not es_especifica(kw, texto_especifico,
                                                                 categorias):
            descartadas.append({"keyword": kw,
                                "motivo": "genérica de la categoría, no de este producto"})
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
