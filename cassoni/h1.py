# -*- coding: utf-8 -*-
"""H1 de la ficha.

v3 (devolución SEO, 6-nov-2026): `{Modelo} + {rasgo o material} + {tipo EE. UU.} +
by {Marca}`. Es la fórmula de los sitios que más tráfico ganan por fichas
(gomodern.co.uk, artemest.com): el tipo y el material en el H1 hacen que la
ficha compita por búsquedas genéricas ("marble coffee table"), no solo por el
nombre del modelo.

Reparto del trabajo:
- CÓDIGO (este archivo): limpia códigos del nombre (SC1019, 19800), decide el
  TIPO en inglés de EE. UU. a partir del nombre, la ruta de categorías y los
  atributos ('Fixed Tables' bajo 'Dining Room' → 'dining table'), arma un H1
  de respaldo sin LLM y VERIFICA el H1 que proponga el redactor: que termine en
  "by {Marca}", que tenga el modelo y el tipo, que no tenga códigos y que cada
  palabra esté en la ficha (nada inventado).
- LLM (cassoni/redactor.py): elige el rasgo más vendedor de lo que la ficha
  dice (material, forma, técnica o construcción).

`h1_plantilla` (v2, `{Nombre} by {Marca}`) queda para el modo de edición
quirúrgica.
"""
from __future__ import annotations

import html
import re
import unicodedata
from typing import Iterable

_WS = re.compile(r"\s+")


def _limpio(s: str) -> str:
    return _WS.sub(" ", html.unescape(s or "")).strip()


def _plano(s: str) -> str:
    return unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()


def h1_plantilla(nombre: str, marca: str) -> tuple[str, str]:
    """v2: devuelve (h1, aviso). `aviso` vacío = se aplicó la plantilla sin dudas."""
    nombre, marca = _limpio(nombre), _limpio(marca)
    if not nombre:
        return "", "la ficha no tiene nombre"
    if not marca:
        return nombre, "sin marca: el H1 queda como el nombre actual"
    sufijo = re.compile(r"\s+by\s+" + re.escape(marca) + r"$", re.I)
    if sufijo.search(nombre):
        base = sufijo.sub("", nombre).strip()
        return f"{base} by {marca}", ""
    prefijo = re.compile(r"^" + re.escape(marca) + r"\b[\s\-–—:|]*", re.I)
    base = prefijo.sub("", nombre).strip() or nombre
    return f"{base} by {marca}", ""


# --- v3 --------------------------------------------------------------------

# un código de catálogo: 'SC1019', 'SC_1019', 'AB-200', '19800' (3+ dígitos solos)
_CODIGO_TOKEN = re.compile(r"^(?:[A-Z]{1,4}[-_]?\d{2,}[A-Z0-9]*|\d{3,})$")


def es_codigo(token: str) -> bool:
    return bool(_CODIGO_TOKEN.match(token.strip("()[],.;:")))


def sin_codigos(nombre: str) -> str:
    """'Cleopatra Chair (SC1019)' → 'Cleopatra Chair'; '19800 Steinway Piano' →
    'Steinway Piano'. Un paréntesis se va entero si todo lo de adentro es código.
    No toca '3-Seater' ni 'Sofa 2' (no son códigos de catálogo)."""
    nombre = _limpio(nombre)

    def _paren(m: re.Match) -> str:
        dentro = m.group(1).split()
        return " " if dentro and all(es_codigo(t) for t in dentro) else m.group(0)

    nombre = re.sub(r"\(([^)]*)\)", _paren, nombre)
    tokens = [t for t in nombre.split() if not es_codigo(t)]
    return _WS.sub(" ", " ".join(tokens)).strip(" -–—|")


def sin_marca(nombre: str, marca: str) -> str:
    """Saca la marca si el nombre la trae al principio o como 'by {Marca}' al final."""
    if not marca:
        return nombre
    nombre = re.sub(r"\s+by\s+" + re.escape(marca) + r"$", "", nombre, flags=re.I)
    nombre = re.sub(r"^" + re.escape(marca) + r"\b[\s\-–—:|]*", "", nombre, flags=re.I)
    return nombre.strip()


# tipo de producto de la última palabra del nombre (o de la categoría) → término de EE. UU.
_TIPOS = ("sofa", "couch", "sectional", "loveseat", "chair", "armchair", "stool", "bench",
          "ottoman", "pouf", "table", "desk", "console", "bed", "headboard", "lamp",
          "chandelier", "sconce", "pendant", "mirror", "sideboard", "cabinet", "dresser",
          "nightstand", "wardrobe", "rug", "carpet", "piano", "shelf", "bookcase", "vase",
          "clock", "lounger", "daybed", "trolley", "parasol", "umbrella", "sunshade",
          "planter", "pot", "light", "buffet", "credenza", "chaise", "screen", "tray",
          "candleholder", "sculpture")
_PREFIJOS = {"coffee", "side", "dining", "console", "wall", "floor", "lounge", "bar",
             "accent", "bedside", "writing", "ceiling", "pendant", "desk", "office",
             "sun", "chaise", "counter", "end", "night", "table", "suspension"}
# ('club' no: en 'Club Sofa' es el nombre del modelo, no un tipo)
# hoja de categoría (slug) → tipo, para fichas cuyo nombre no lo dice ('Anamon')
_TIPO_POR_CATEGORIA = {
    "coffee-side-tables": "coffee table", "fixed-tables": "dining table",
    "extendable-tables": "extendable dining table", "chairs-armchairs": "chair",
    "sofas-sectionals": "sofa", "armchairs": "armchair", "double-beds": "bed",
    "single-beds": "bed", "mirrors": "mirror", "wall-lamps-sconces": "wall sconce",
    "floor-lamps": "floor lamp", "table-lamps": "table lamp", "chandeliers": "chandelier",
    "suspension-lamps": "pendant light", "pendant-lamps": "pendant light",
    "sideboards": "sideboard", "nightstands": "nightstand", "consoles": "console table",
    "umbrellas-sunshades": "parasol", "rugs": "rug", "bookcases": "bookcase",
    "poufs-ottomans": "ottoman", "benches": "bench", "stools": "stool",
    "bar-stools": "bar stool", "desks": "desk", "wardrobes": "wardrobe",
    "dressers": "dresser", "vases": "vase", "clocks": "clock", "daybeds": "daybed",
}
# nombres de cassoni que en EE. UU. se buscan con otro término
_TERMINO_EE_UU = {"wall lamp": "wall sconce", "wall light": "wall sconce",
                  "suspension lamp": "pendant light", "pendant lamp": "pendant light",
                  "bedside table": "nightstand", "night table": "nightstand",
                  "sunshade": "parasol"}


def _singular(w: str) -> str:
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("es") and w[:-2] in _TIPOS:
        return w[:-2]
    if w.endswith("s") and w[:-1] in _TIPOS:
        return w[:-1]
    return w


def _tipo_del_nombre(modelo: str) -> tuple[str, int]:
    """('coffee table', índice de la primera palabra del tipo) o ('', -1)."""
    palabras = re.findall(r"[a-z]+", _plano(modelo))
    for i in range(len(palabras) - 1, -1, -1):
        w = _singular(palabras[i])
        if w in _TIPOS:
            if i > 0 and palabras[i - 1] in _PREFIJOS and palabras[i - 1] != w:
                return f"{palabras[i - 1]} {w}", i - 1
            return w, i
    return "", -1


def _attr(atributos: Iterable[str], patron: str) -> str:
    rx = re.compile(patron, re.I)
    for a in atributos:
        nombre, _, valor = a.partition(":")
        if rx.search(nombre):
            return _plano(html.unescape(valor))
    return ""


def tipo_ee_uu(nombre: str, ruta_categorias: Iterable[str] = (),
               atributos: Iterable[str] = ()) -> str:
    """Tipo de producto en inglés de EE. UU., con su uso cuando lo define la ruta
    de categorías o un atributo. Nada inventado: todo sale de la ficha.

    'Bakkarat Table' + .../dining-room/fixed-tables → 'dining table'
    'Cruise Sofa' + outdoor/... → 'outdoor sofa'
    'Illan Wall Lamp' → 'wall sconce'
    'Tiffany Mirror' + 'Base Type (Mirrors): Wall-mounted' → 'wall mirror'
    'Shibari Chair' + 'Armrest: With Armrests' → 'armchair'
    'Hermes Maxi Bed' + 'Bed Size: King' → 'king bed'"""
    ruta = [_plano(r) for r in ruta_categorias]
    atributos = list(atributos)
    tipo, _ = _tipo_del_nombre(sin_codigos(nombre))
    if not tipo:
        for slug in reversed(ruta):
            if slug in _TIPO_POR_CATEGORIA:
                tipo = _TIPO_POR_CATEGORIA[slug]
                break
    if not tipo:
        return ""
    tipo = _TERMINO_EE_UU.get(tipo, tipo)
    if tipo.endswith("lamp") and any("wall-lamps" in r for r in ruta):
        tipo = "wall sconce"
    base = tipo.split()[-1]
    brazos = _attr(atributos, r"armrest")
    if base == "chair" and tipo == "chair":
        if "with armrests" in brazos:
            tipo = "armchair"
        elif any("dining" in r for r in ruta):
            tipo = "dining chair"
    if tipo == "table" and any("dining" in r for r in ruta):
        tipo = "dining table"
    if tipo == "mirror" and "wall" in _attr(atributos, r"base type|mount"):
        tipo = "wall mirror"
    if base == "bed" and tipo == "bed":
        medida = _attr(atributos, r"bed size")
        for m in ("king", "queen", "twin", "full"):
            if m in medida.split(",")[0]:
                tipo = f"{m} bed"
                break
    if any("outdoor" in r for r in ruta) and "outdoor" not in tipo:
        tipo = f"outdoor {tipo}"
    return tipo


def modelo_de(nombre: str, marca: str) -> str:
    """Nombre sin códigos, sin marca y sin la palabra de tipo final:
    'Cleopatra Chair (SC1019)' → 'Cleopatra'; 'Hermes Maxi Bed' → 'Hermes Maxi';
    'Rock Coffee Table' → 'Rock'. Si el nombre es solo el tipo, queda entero.
    Si el código es el ÚNICO nombre ('W017 Sideboard'), el código es el modelo
    (prueba ciega 11-nov: el H1 quedaba 'Sideboard … by Zanaboni')."""
    def _parte_modelo(texto: str) -> str:
        tipo, _ = _tipo_del_nombre(texto)
        if not tipo:
            return texto
        primera, palabras = tipo.split()[0], texto.split()
        for i in range(len(palabras) - 1, 0, -1):
            if _singular("".join(re.findall(r"[a-z]+", _plano(palabras[i])))) == primera:
                return " ".join(palabras[:i])
        return ""

    limpio = sin_marca(sin_codigos(nombre), marca)
    modelo = _parte_modelo(limpio)
    if modelo:
        return modelo
    con_codigo = sin_marca(re.sub(r"\([^)]*\)", " ", _limpio(nombre)), marca)
    return _parte_modelo(_WS.sub(" ", con_codigo).strip()) or limpio


def _titulo(s: str) -> str:
    return " ".join(w if w.isupper() else w[:1].upper() + w[1:] for w in s.split())


def h1_respaldo(nombre: str, marca: str, tipo: str) -> str:
    """H1 sin LLM: '{Modelo} {Tipo} by {Marca}'. Se usa si el redactor no propone
    uno válido."""
    modelo = modelo_de(nombre, marca) or sin_codigos(nombre)
    cuerpo = f"{modelo} {_titulo(tipo)}".strip() if tipo else sin_codigos(nombre)
    return f"{cuerpo} by {marca}" if marca else cuerpo


# palabras que el H1 puede tener sin que la ficha las diga (gramática y tipos EE. UU.)
_LIBRES = {"by", "with", "and", "in", "of", "for", "the", "a", "an", "&"}


def _raiz(w: str) -> str:
    """Raíz tosca para comparar 'carved' con 'carvings', 'upholstered' con
    'upholstery': alcanza para decidir si la ficha respalda la palabra."""
    w = _singular(w)
    for suf in ("ings", "ing", "ered", "ery", "ed", "es", "s", "ly"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def verificar_h1(h1: str, *, nombre: str, marca: str, tipo: str,
                 texto_ficha: str, max_palabras: int = 9) -> list[str]:
    """Problemas del H1 propuesto ([] = válido). `texto_ficha`: nombre, atributos,
    categorías y descripción original: cada palabra del H1 tiene que estar ahí
    (o ser el tipo de EE. UU. que decidió el código)."""
    issues: list[str] = []
    h1 = _limpio(h1)
    if not h1:
        return ["H1 vacío"]
    cuerpo = h1
    if marca:
        sufijo = f" by {marca}"
        if not h1.lower().endswith(sufijo.lower()):
            issues.append(f"el H1 tiene que terminar en 'by {marca}'")
        else:
            cuerpo = h1[: -len(sufijo)]
        if marca.lower() in cuerpo.lower():
            issues.append("la marca aparece dos veces en el H1")
    del_modelo = set(modelo_de(nombre, marca).split())
    codigos = [t for t in cuerpo.split() if es_codigo(t) and t not in del_modelo]
    if codigos:
        issues.append(f"el H1 tiene códigos de catálogo: {', '.join(codigos)}")
    palabras_cuerpo = re.findall(r"[a-z]+", _plano(cuerpo))
    if len(cuerpo.split()) > max_palabras:
        issues.append(f"el H1 es largo: {len(cuerpo.split())} palabras antes de 'by' "
                      f"(máximo {max_palabras})")
    modelo = modelo_de(nombre, marca)
    faltan_modelo = [w for w in re.findall(r"[a-z]+", _plano(modelo))
                     if w not in palabras_cuerpo]
    if faltan_modelo:
        issues.append(f"el H1 perdió el nombre del modelo ({modelo})")
    if tipo:
        base = _singular(tipo.split()[-1])
        if base not in {_singular(w) for w in palabras_cuerpo}:
            issues.append(f"el H1 no dice qué es: falta '{tipo}'")
    respaldo = {_raiz(w) for w in re.findall(r"[a-z]+", _plano(f"{nombre} {texto_ficha} {tipo}"))}
    sin_respaldo = [w for w in palabras_cuerpo
                    if w not in _LIBRES and _raiz(w) not in respaldo and len(w) > 2]
    if sin_respaldo:
        issues.append("el H1 dice cosas que la ficha no dice: " + ", ".join(sin_respaldo))
    return issues
