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


def es_marca_y_modelo(keyword: str, nombre: str, marca: str) -> bool:
    """'luceplan illan', 'illan luceplan': búsqueda de ESE producto aunque no
    nombre el tipo (prueba real: se descartaban siendo las más valiosas)."""
    kw = {_singular(w) for w in _palabras(keyword)}
    modelo = {_singular(w) for w in _palabras(nombre) if len(w) >= 3}
    return bool(kw & modelo) and bool(kw & {_singular(w) for w in _palabras(marca)})


def cubierta_por_el_h1(keyword: str, nombre: str, marca: str) -> bool:
    """Todas sus palabras ya están en el H1 '{Nombre} by {Marca}': agregarla a la
    descripción no suma ('club sofa' en la Club Sofa, 'luceplan illan' en la
    Illan Wall Lamp by Luceplan). El H1 nuevo ya cubre esa búsqueda."""
    h1 = {_singular(w) for w in _palabras(f"{nombre} {marca}")}
    kw = {_singular(w) for w in _palabras(keyword) if w not in _VACIAS}
    return bool(kw) and kw <= h1


# tipos de producto: si la keyword nombra OTRO tipo, habla de otro producto
# ('cleopatra chair sofa' en una silla, 'hermes mattress' en una cama)
TIPOS_DE_PRODUCTO = {
    "sofa", "couch", "sectional", "loveseat", "chair", "armchair", "stool", "bench",
    "ottoman", "pouf", "table", "desk", "console", "bed", "mattress", "headboard",
    "lamp", "chandelier", "sconce", "pendant", "mirror", "sideboard", "cabinet",
    "dresser", "nightstand", "wardrobe", "rug", "carpet", "piano", "shelf",
    "bookcase", "vase", "clock", "lounger", "daybed", "bar", "trolley"}
# lo que busca un artículo y no una ficha (el filtro de blog solo tenía español)
_INFORMATIVA_RX = re.compile(r"^(what|how|why|when|where|who|which)\b|\b(vs|versus|ideas|"
                             r"meaning|history|diy|review|reviews|guide)\b", re.I)
# intención de compra: va en el título o la meta, no en la prosa de la descripción
_TRANSACCIONAL_RX = re.compile(r"\b(for sale|price|prices|cost|near me|buy|cheap|"
                               r"discount|sale|outlet|used)\b", re.I)
# otra marca famosa con el mismo nombre ('tiffany and co', 'steinway and sons' ok)
_OTRA_MARCA_RX = re.compile(r"\b(and|&)\s*co\b|\bbirkin\b|\bkelly bag\b", re.I)


def otro_tipo(keyword: str, tipos: set[str]) -> str:
    """El tipo de producto que nombra la keyword y que este producto NO es."""
    for w in _palabras(keyword):
        t = _singular(w)
        if t in TIPOS_DE_PRODUCTO and t not in tipos:
            return t
    return ""


_VACIAS = {"the", "a", "an", "of", "by", "for", "and", "de", "la", "el", "en", "y"}


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
    # 'beds' → 'bed' (con > 4 letras se escapaba: 'hermes beds' no se veía cubierta)
    return w[:-1] if len(w) >= 4 and w.endswith("s") and not w.endswith("ss") else w


def _con_demanda(fila: dict, min_volume: int) -> bool:
    vol = fila.get("volume")
    if vol is not None:
        return vol >= min_volume
    return (fila.get("impressions") or 0) >= MIN_IMPRESIONES_SIN_VOLUMEN


# CTR aproximado por posición orgánica (curva pública típica): lo que se gana
# subiendo una ficha de su posición actual al top 3
_CTR = {1: .28, 2: .15, 3: .11, 4: .08, 5: .065, 6: .05, 7: .04, 8: .033, 9: .028, 10: .025}
POSICION_MAX = 30          # más allá, la ficha no compite por esa búsqueda


def _ctr(pos: float) -> float:
    if not pos:
        return 0.0
    if pos <= 10:
        return _CTR[max(1, round(pos))]
    return 0.012 if pos <= 20 else 0.004


def potencial(fila: dict) -> float:
    """Clics por mes que se ganarían llevando la ficha al top 3 en esa búsqueda.
    Demanda = volumen de DataForSEO, o impresiones de GSC (90 días → mes) si no
    hay volumen. Manda la OPORTUNIDAD de esta página, no el volumen genérico:
    'luxury wall lights' (210/mes, posición 37) vale menos que una búsqueda con
    impresiones reales en posición 8 (prueba real 3-nov)."""
    demanda = fila.get("volume")
    if demanda is None:
        demanda = (fila.get("impressions") or 0) / 3
    pos = fila.get("position")
    if not pos:                       # investigación o competidores: la ficha todavía no
        kd = fila.get("difficulty") or 0       # aparece; pesa lo que cuesta entrar
        return demanda * 0.02 * max(0.0, 1 - kd / 100)
    return demanda * max(0.0, _CTR[3] - _ctr(pos))


KD_MAX = 60                # dificultad (0-100) por encima de la cual una ficha no compite


def _orden(fila: dict) -> tuple:
    return (potencial(fila), fila.get("impressions") or 0)


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
    atributos_palabras = ({w for w in _palabras(texto_especifico or "")
                           - _palabras(nombre or "") - _palabras(marca) if len(w) >= 3}
                          if nombre is not None else set())
    tipos_propios = set(tipos)     # solo nombre + categoría: 'mattress' en un atributo
                                   # de la cama no convierte a la cama en colchón
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
        elif c.get("intent") == "informational":
            descartadas.append({"keyword": kw, "motivo": "búsqueda informativa: es para "
                                                         "un artículo, no para la ficha"})
        elif (c.get("difficulty") or 0) > KD_MAX:
            descartadas.append({"keyword": kw, "motivo": f"demasiado competida para una ficha "
                                                         f"(dificultad {c['difficulty']})"})
        elif (c.get("origen") == "investigacion" and nombre is not None
              and not (_palabras(kw) & atributos_palabras)):
            descartadas.append({"keyword": kw, "motivo": "no menciona ningún material, "
                                                         "acabado o estilo de la ficha"})
        elif _INFORMATIVA_RX.search(kw):
            descartadas.append({"keyword": kw, "motivo": "búsqueda informativa: es para "
                                                         "un artículo, no para la ficha"})
        elif _TRANSACCIONAL_RX.search(kw):
            descartadas.append({"keyword": kw, "motivo": "intención de compra: va en el "
                                                         "título o la meta, no en la descripción"})
        elif _OTRA_MARCA_RX.search(kw):
            descartadas.append({"keyword": kw, "motivo": "habla de otra marca"})
        elif nombre is not None and otro_tipo(kw, tipos_propios):
            descartadas.append({"keyword": kw, "motivo": f"nombra otro producto "
                                                         f"({otro_tipo(kw, tipos_propios)})"})
        elif nombre is not None and cubierta_por_el_h1(kw, nombre, marca):
            descartadas.append({"keyword": kw, "motivo": "ya la cubre el H1 nuevo"})
        elif c.get("position") and c["position"] > POSICION_MAX:
            descartadas.append({"keyword": kw, "motivo": f"la ficha no compite "
                                                         f"(posición {c['position']:.0f})"})
        elif (nombre is not None and not nombra_el_tipo(kw, tipos)
              and not es_marca_y_modelo(kw, nombre, marca)):
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
    h1_palabras = [w for w in _palabras(f"{nombre or ''} {marca}")]
    puntuar = lambda cs: [dict(c, opportunity_score=potencial(c)) for c in cs]  # noqa: E731
    div = seleccionar_diversas(puntuar(libres), max_sec=n, ignorar=h1_palabras)
    elegidas = [{k: v for k, v in c.items() if k != "opportunity_score"}
                for c in div["elegidas"]]
    for o in div["omitidas"]:
        descartadas.append({"keyword": o["keyword"], "motivo": o["motivo"]})

    # "en la medida de lo posible": si faltan, se completa con las ya usadas en
    # otra ficha antes que quedarse corto (y queda registrado con quién choca)
    if len(elegidas) < n and reserva:
        reserva.sort(key=_orden, reverse=True)
        div2 = seleccionar_diversas(puntuar(elegidas + reserva), max_sec=n,
                                    ignorar=h1_palabras)
        elegidas = [{k: v for k, v in c.items() if k != "opportunity_score"}
                    for c in div2["elegidas"]]
    usadas = {_norm(e["keyword"]) for e in elegidas}
    for r in reserva:
        if _norm(r["keyword"]) not in usadas:
            descartadas.append({"keyword": r["keyword"],
                                "motivo": f"ya está en otra ficha ({r['compartida_con']})"})

    return {"elegidas": elegidas, "descartadas": descartadas,
            "faltan": max(0, n - len(elegidas))}
