# -*- coding: utf-8 -*-
"""¿Puede una FICHA ganar esta búsqueda? Se mira qué muestra Google (DataForSEO
SERP, top 10) antes de elegir una keyword objetivo.

Devolución SEO del 6-nov-2026, las tres fallas que el volumen no ve:
- de CATEGORÍA: 'wood table', 'marble table', 'decorative wall mirror'. Google
  muestra colecciones ('Solid Wood Dining Tables'): una ficha no compite.
- de OTRO TEMA: 'cruise couch' (foros de cruceros), "cleopatra's chair" (una
  ruta de senderismo). No es una búsqueda de compra de muebles.
- de OTRO PRODUCTO: 'tiffany style mirrors' (vidrio de colores: 'stained glass'
  en 5 de 10 títulos). La ficha no es eso.

Se decide por los TÍTULOS de los resultados: las URLs llegan recortadas. Una
página de colección se titula en plural ('Marble Dining Tables'); una ficha, en
singular ('Bali 86" Natural Teak Outdoor Sofa'). Calibrado con 16 búsquedas
reales (evidencia/2026-11-11-serps-calibracion.json).

Puro, sin I/O: el SERP llega por parámetro.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Iterable

MIN_RESULTADOS = 5            # con menos, no hay señal: no se descarta
MAX_FUERA_DE_TEMA = 4         # resultados que no venden muebles (foros, rutas, fotos)
UMBRAL_CATEGORIA = 0.6        # proporción de títulos en plural entre los que nombran el tipo
MIN_CON_TIPO_CATEGORIA = 5    # ...con al menos estos títulos que nombran el tipo
MIN_DOMINANTE = 4             # una palabra ajena en 4 títulos...
PROP_DOMINANTE = 0.4          # ...y en el 40% de ellos define la búsqueda (los
                              # resultados cambian de un día a otro: 5 de 9 un día,
                              # 4 de 8 otro; un umbral fijo de 5 quedaba en el borde)

_FUERA_DE_TEMA = re.compile(
    r"\b(forum|forums|boards?|reddit|quora|cruise|cruises|stateroom|trail|trails|hiking|"
    r"national park|camp|expedition|stock photo|photography|images|wikipedia|youtube|"
    r"instagram|tiktok|facebook|what is|how to|questions?|answers|meaning|recipe|"
    r"lyrics|movie|nostalgia|guide|profiles? of|most famous|most popular|top \d+|"
    r"the \d+ (?:best|most)|best \w+ brands?)\b|^(which|where|why|who)\b", re.I)
# palabras de comercio o de relleno que no definen QUÉ es el producto
_NEUTRAS = {
    "the", "and", "for", "with", "from", "your", "our", "shop", "buy", "sale", "sales",
    "online", "best", "new", "modern", "luxury", "designer", "design", "home", "furniture",
    "store", "collection", "collections", "price", "prices", "free", "shipping", "top",
    "high", "quality", "handmade", "custom", "contemporary", "style", "styles", "set",
    "inch", "updated", "nov", "dec", "jan", "ideas", "decor", "living", "room", "rooms",
    "wall", "interior", "interiors", "italian", "brand", "official", "site", "inc", "llc",
    "amazon", "etsy", "ebay", "pinterest", "wayfair", "ikea", "com", "www", "co",
}


def _plano(s: str) -> str:
    return unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()


def _palabras(s: str) -> list[str]:
    return re.findall(r"[a-z]+", _plano(s))


def _plural_de(tipo: str) -> set[str]:
    if tipo.endswith(("s", "x", "ch", "sh")):
        return {tipo + "es"}
    if tipo.endswith("y"):
        return {tipo[:-1] + "ies"}
    return {tipo + "s"}


def _singular(w: str) -> str:
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("es") and len(w) > 4 and w[-3] in "sxh":
        return w[:-2]
    return (w[:-1] if len(w) > 3 and w.endswith("s")
            and not w.endswith(("ss", "is", "us")) else w)


def veredicto(keyword: str, serp: list[dict], tipos: Iterable[str],
              texto_ficha: str = "") -> dict:
    """{'ok': bool, 'motivo': str, 'senales': {...}}.

    `tipos`: palabras que dicen qué es el producto, con sinónimos ({'sofa','couch'}).
    `texto_ficha`: lo que dice la ficha; una palabra que domina los títulos y no
    está ahí ni en la keyword es otro producto ('stained' en un espejo liso)."""
    filas = [r for r in serp[:10] if (r.get("title") or "").strip()]
    tipos = {_singular(_plano(t)) for t in tipos if t}
    senales = {"resultados": len(filas)}
    if len(filas) < MIN_RESULTADOS:
        return {"ok": True, "motivo": "", "senales": senales}

    fuera = [r["title"] for r in filas
             if _FUERA_DE_TEMA.search(f"{r.get('title', '')} {r.get('domain', '')}")
             or r["title"].strip().endswith("?")]
    senales["fuera_de_tema"] = len(fuera)
    if len(fuera) >= MAX_FUERA_DE_TEMA:
        return {"ok": False, "senales": senales,
                "motivo": f"Google no muestra muebles a la venta ({len(fuera)} de "
                          f"{len(filas)} resultados son otra cosa: «{fuera[0][:50]}»)"}

    plurales = {p for t in tipos for p in _plural_de(t)}
    plural = singular = 0
    for r in filas:
        ws = set(_palabras(r["title"]))
        if ws & plurales:
            plural += 1
        elif ws & tipos:
            singular += 1
    senales.update(titulos_plural=plural, titulos_singular=singular)
    con_tipo = plural + singular
    if con_tipo >= MIN_CON_TIPO_CATEGORIA and plural / con_tipo >= UMBRAL_CATEGORIA:
        return {"ok": False, "senales": senales,
                "motivo": f"búsqueda de categoría: Google muestra colecciones ({plural} de "
                          f"{con_tipo} títulos en plural), no fichas"}

    propias = {_singular(w) for w in _palabras(f"{keyword} {texto_ficha}")} | tipos
    conteo: Counter = Counter()
    for r in filas:
        for w in {_singular(w) for w in _palabras(r["title"])}:
            if len(w) >= 4 and w not in _NEUTRAS and w not in propias:
                conteo[w] += 1
    dominantes = [w for w, n in conteo.most_common(3)
                  if n >= MIN_DOMINANTE and n / len(filas) >= PROP_DOMINANTE]
    senales["dominantes"] = dict(conteo.most_common(3))
    if texto_ficha and dominantes:
        return {"ok": False, "senales": senales,
                "motivo": f"Google la asocia a '{dominantes[0]}' ({conteo[dominantes[0]]} de "
                          f"{len(filas)} títulos) y la ficha no lo dice: es otro producto"}
    return {"ok": True, "motivo": "", "senales": senales}
