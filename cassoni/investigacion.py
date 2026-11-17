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
    r"armrest|base type|backrest|mirror type|top size|headboard size|dimmer|model|"
    r"version|^\s*set|space|seat height|filter by type|\bled\b|kelvin|temperature|"
    r"finish code|option", re.I)
# valores que no forman una búsqueda real ('legs chair', 'high chair' = de bebé)
_VALORES_IGNORADOS = {"legs", "regular", "high", "low", "flat", "straight", "standard",
                      "with armrests", "without armrests", "other", "none", "yes", "no",
                      "indoors", "outdoors", "indoor", "fixed", "bi-color", "single-color",
                      "two-color", "multi-color", "custom", "various"}
# materiales y técnicas que la gente busca con el tipo ('brass chandelier',
# 'blown glass ceiling light'): se toman también de la DESCRIPCIÓN, porque muchas
# fichas los dicen solo ahí (prueba del 13-nov: Spear, Saba, Cristallino, Almeria)
_MATERIALES = ("blown glass", "murano glass", "tempered glass", "smoked glass",
               "crystal", "glass", "brass", "bronze", "copper", "gold leaf", "stainless steel",
               "steel", "aluminum", "iron", "wrought iron", "nickel", "chrome",
               "marble", "travertine", "onyx", "stone", "ceramic", "porcelain", "concrete",
               "leather", "velvet", "boucle", "linen", "fabric", "rope", "rattan", "wicker",
               "cane", "teak", "walnut", "oak", "ash", "rosewood", "mahogany", "ebony", "wood",
               "lacquered", "mother of pearl", "alabaster", "resin", "fiberglass")
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


def materiales_del_texto(texto: str) -> list[str]:
    """Materiales que la ficha dice en el texto, del más específico al más
    general, sin repetir lo que ya cubre uno más largo ('blown glass' tapa 'glass')."""
    t = " " + re.sub(r"[^a-z]+", " ", _plano(texto)) + " "
    t = t.replace(" wooden ", " wood ")
    # "Without Marble Top": el material negado no es de la ficha (Palatial, 13-nov)
    t = re.sub(r" (?:without|no|not) (?:[a-z]+ ){1,3}", " ", t)
    out: list[str] = []
    for m in sorted(_MATERIALES, key=len, reverse=True):
        if f" {m} " in t and not any(f" {m} " in f" {o} " for o in out):
            out.append(m)
    return out


def semillas(nombre: str, marca: str, categorias: Iterable[str],
             atributos: Iterable[str], tipo: str = "", descripcion: str = "") -> list[str]:
    """Semillas para la investigación: tipo × materiales/estilo reales, más marca × tipo.
    `tipo` es el de EE. UU. que ya resolvió el H1 ('foosball table', 'valet stand');
    sin él, se toma del nombre.
    'Cruise Teak Sofa' + 'Material: Teak, Rope' + 'Outdoor Sofas' →
    ['teak sofa', 'rope sofa', 'outdoor teak sofa', 'talenti sofa', 'outdoor sofa']."""
    tipo = _plano(tipo) or tipo_compuesto(nombre)
    if not tipo:
        return []
    exterior = any("outdoor" in _plano(c) for c in categorias) or tipo.startswith("outdoor ")
    nucleo = tipo[len("outdoor "):] if tipo.startswith("outdoor ") else tipo
    valores = valores_de_atributos(atributos)
    texto = " ".join([nombre, *atributos, re.sub(r"<[^>]+>", " ", descripcion or "")])
    mats = [m for m in materiales_del_texto(texto) if m not in valores]
    # primero los materiales (lo que más se busca), después estilo y demás valores
    base = [f"{v} {nucleo}" for v in mats + valores if v != "outdoor" and v not in nucleo]
    if exterior:
        base = [f"outdoor {b}" for b in base[:3]] + base + [f"outdoor {nucleo}"]
    if marca:
        base.append(f"{_plano(marca)} {nucleo}")
    vistas, out = set(), []
    for s in base:
        s = " ".join(s.split())
        if s and s not in vistas:
            vistas.add(s)
            out.append(s)
    return out[:MAX_SEMILLAS]


# prefijos que SON el producto ('foosball table' se busca por 'foosball')
_PREFIJO_DISTINTIVO = {"foosball", "pool", "billiard", "valet", "bathroom", "bath", "coat"}
_SINONIMOS_NUCLEO = {"lamp": ["light"], "light": ["lamp"], "sconce": ["light"],
                     "sofa": ["couch"], "couch": ["sofa"], "armchair": ["chair"],
                     "bathroom": ["bath"], "basket": ["baskets"]}


def nucleos(tipo: str) -> list[str]:
    """Palabras que una idea de keyword TIENE que contener para ser de este tipo de
    producto: 'ceiling lamp' → ['lamp', 'light']; 'foosball table' → ['foosball'].
    Sin esto, keyword_ideas devuelve 'adirondack chairs' para un sillón tapizado
    (prueba del 13-nov)."""
    palabras = _plano(tipo).split()
    if not palabras:
        return []
    clave = next((w for w in palabras if w in _PREFIJO_DISTINTIVO), palabras[-1])
    return [clave, *_SINONIMOS_NUCLEO.get(clave, [])]


# quien busca esto quiere un repuesto o un accesorio, no el producto
_REPUESTOS = {"rod", "rods", "part", "parts", "replacement", "replacements", "cover",
              "covers", "cushion", "cushions", "bulb", "bulbs", "shade", "shades",
              "leg", "legs", "kit", "repair", "hardware", "accessories", "accessory",
              "bracket", "screws"}


def motivo_idea(keyword: str, tipo: str) -> str:
    """Por qué una idea de keyword no sirve para la ficha ('' si sirve).
    - 'foosball table rods' busca repuestos (prueba del 13-nov);
    - 'ceiling living room light' parte el tipo ('ceiling light') con otras
      palabras: no es una frase que se escriba en una oración natural."""
    palabras = re.findall(r"[a-z]+", _plano(keyword))
    tipo_p = _plano(tipo).split()
    if tipo_p and tipo_p[0] == "outdoor":
        tipo_p = tipo_p[1:]
    if "for" in palabras and tipo_p:
        # 'frame for mirror', 'cushions for outdoor sofa': algo PARA el producto
        cabeza = {tipo_p[-1], *_SINONIMOS_NUCLEO.get(tipo_p[-1], [])}
        despues = palabras[palabras.index("for") + 1:]
        if any(w.rstrip("s") in {c.rstrip("s") for c in cabeza} for w in despues):
            return f"busca algo para un {tipo_p[-1]}, no el producto"
    if palabras and palabras[-1] in _REPUESTOS and palabras[-1] not in tipo_p:
        return f"busca un repuesto o accesorio ('{palabras[-1]}'), no el producto"
    if len(tipo_p) == 2:
        a, b = tipo_p
        cabeza = {b, *_SINONIMOS_NUCLEO.get(b, [])}
        if a in palabras:
            i = palabras.index(a)
            resto = palabras[i + 1:]
            if any(w.rstrip("s") in {c.rstrip("s") for c in cabeza} for w in resto[1:])                     and (not resto or resto[0].rstrip("s") not in {c.rstrip("s") for c in cabeza}):
                return f"parte el tipo '{a} {b}' con otras palabras: no se escribe así"
    return ""
