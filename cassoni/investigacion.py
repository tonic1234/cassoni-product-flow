# -*- coding: utf-8 -*-
"""Investigación de keywords para la descripción larga (equipo SEO, 3-nov-2026).

GSC solo muestra búsquedas por las que la ficha YA aparece: en productos de
nicho es casi siempre el nombre, que el H1 nuevo ya cubre. Las keywords que
aportan son las que la ficha TODAVÍA no atrae: el tipo de producto con un
material, acabado o estilo que la ficha tiene ('teak outdoor sofa', 'brass
sofa', 'rosewood chair'). Se buscan en DataForSEO Labs a partir de semillas
armadas con los datos reales de la ficha.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable

# atributos que NO describen el producto para una búsqueda (medidas, códigos…)
_ATRIBUTOS_IGNORADOS = re.compile(
    r"size|dimension|measure|weight|sku|code|ean|collection|designer|light source|"
    r"wattage|lumen|voltage|certif|warranty|delivery|lead time|mattress|typology|"
    r"armrest|base type|backrest|mirror type|top size|headboard size", re.I)
# valores que no forman una búsqueda real ('legs chair', 'high chair' = de bebé)
_VALORES_IGNORADOS = {"legs", "regular", "high", "low", "flat", "straight", "standard",
                      "with armrests", "without armrests", "other", "none", "yes", "no"}
# palabras que, delante del tipo, forman el tipo compuesto ('coffee table')
_COMPUESTOS = {"coffee", "side", "dining", "console", "wall", "floor", "lounge", "outdoor",
               "bar", "accent", "bedside", "writing", "ceiling", "pendant", "table",
               "desk", "office", "arm", "club", "double", "single", "king", "queen"}
_TIPOS = {"sofa", "couch", "sectional", "chair", "armchair", "stool", "bench", "ottoman",
          "pouf", "table", "desk", "console", "bed", "headboard", "lamp", "chandelier",
          "sconce", "pendant", "mirror", "sideboard", "cabinet", "dresser", "nightstand",
          "wardrobe", "rug", "carpet", "piano", "shelf", "bookcase", "vase", "clock",
          "lounger", "daybed", "trolley", "light"}
MAX_SEMILLAS = 10


def _plano(s: str) -> str:
    return unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()


def tipo_compuesto(nombre: str) -> str:
    """'Rock Coffee Table' → 'coffee table'; 'Cleopatra Chair (SC1019)' → 'chair'."""
    palabras = re.findall(r"[a-z]+", _plano(re.sub(r"\(.*?\)", " ", nombre or "")))
    for i in range(len(palabras) - 1, -1, -1):
        w = palabras[i][:-1] if palabras[i].endswith("s") and palabras[i][:-1] in _TIPOS else palabras[i]
        if w in _TIPOS:
            if i > 0 and palabras[i - 1] in _COMPUESTOS and palabras[i - 1] != w:
                return f"{palabras[i - 1]} {w}"
            return w
    return ""


def valores_de_atributos(atributos: Iterable[str]) -> list[str]:
    """Valores de material / acabado / estilo: 'Material: Brass, Leather' →
    ['brass', 'leather']. Sin medidas, códigos ni nombres de colección."""
    out: list[str] = []
    for a in atributos:
        nombre, _, valores = a.partition(":")
        if not valores or _ATRIBUTOS_IGNORADOS.search(nombre):
            continue
        for v in valores.split(","):
            v = re.sub(r"[^a-z\s-]", " ", _plano(v))
            v = " ".join(w for w in v.split() if len(w) >= 3)
            if v and len(v.split()) <= 3 and v not in out and v not in _VALORES_IGNORADOS:
                out.append(v)
    return out


def semillas(nombre: str, marca: str, categorias: Iterable[str],
             atributos: Iterable[str]) -> list[str]:
    """Semillas para la investigación: tipo × atributos reales, más marca × tipo.
    'Cruise Teak Sofa' + 'Material: Teak, Rope' + 'Outdoor Sofas' →
    ['teak sofa', 'rope sofa', 'outdoor teak sofa', 'talenti sofa', 'outdoor sofa']."""
    tipo = tipo_compuesto(nombre)
    if not tipo:
        return []
    exterior = any("outdoor" in _plano(c) for c in categorias)
    base = [f"{v} {tipo}" for v in valores_de_atributos(atributos)]
    if exterior and not tipo.startswith("outdoor"):
        base = [f"outdoor {b}" for b in base[:3]] + base + [f"outdoor {tipo}"]
    if marca:
        base.append(f"{_plano(marca)} {tipo}")
    vistas, out = set(), []
    for s in base:
        s = " ".join(s.split())
        if s and s not in vistas:
            vistas.add(s)
            out.append(s)
    return out[:MAX_SEMILLAS]
