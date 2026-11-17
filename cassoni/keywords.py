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
    # 'Nivola Driving Simulator - Heritage Edition': lo de después del guion es la
    # variante, no el tipo (prueba ciega 11-nov: el tipo salía 'edition')
    limpio = re.split(r"\s[-–—]\s", limpio)[0]
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
    from .h1 import modelo_de
    kw = {_singular(w) for w in _palabras(keyword)}
    # el MODELO, sin la palabra de tipo ('Tiffany', no 'mirror'), y la marca sin
    # sus palabras genéricas ('DV Home Collection' → 'dv'): 'mirror home' no es
    # una búsqueda de marca + modelo (prueba ciega 11-nov)
    modelo = {_singular(w) for w in _palabras(modelo_de(nombre, marca)) if len(w) >= 3}
    propias = {_singular(w) for w in _palabras(marca)} - _GENERICAS_DE_MARCA
    return bool(kw & modelo) and bool(kw & propias)


def nombra_el_modelo(keyword: str, nombre: str, marca: str) -> bool:
    """'white balloon dog' en 'Balloon Dog - White Diamond': la búsqueda nombra el
    modelo entero (2+ palabras propias) aunque no diga el tipo ni la marca."""
    from .h1 import modelo_de
    base = re.split(r"\s[-–—]\s", nombre or "")[0]
    modelo = {_singular(w) for w in _palabras(modelo_de(base, marca)) if len(w) >= 3}
    kw = {_singular(w) for w in _palabras(keyword)}
    return len(modelo) >= 2 and modelo <= kw


_GENERICAS_DE_MARCA = {"home", "collection", "design", "designs", "furniture", "living",
                       "casa", "studio", "italia", "italy", "group", "interiors", "lighting",
                       "light", "arte", "art", "mobili", "the", "and", "di", "de", "by"}


def cubierta_por_el_h1(keyword: str, nombre: str, marca: str) -> bool:
    """Todas sus palabras ya están en el H1 '{Nombre} by {Marca}': agregarla a la
    descripción no suma ('club sofa' en la Club Sofa, 'luceplan illan' en la
    Illan Wall Lamp by Luceplan). El H1 nuevo ya cubre esa búsqueda."""
    h1 = {_singular(w) for w in _palabras(f"{nombre} {marca}")}
    kw = {_singular(w) for w in _palabras(keyword) if w not in _VACIAS}
    if not kw or not kw <= h1:
        return False
    # marca + tipo ('rugiano sofas') no es la búsqueda del modelo: el H1 la nombra
    # de casualidad y es una keyword que el SEO usa (devolución 6-nov). Solo la
    # cubre el H1 si nombra el MODELO ('club sofa', 'luceplan illan').
    from .h1 import modelo_de
    modelo = {_singular(w) for w in _palabras(modelo_de(nombre, marca)) if len(w) >= 3}
    return bool(kw & modelo) or not modelo


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
                             r"meaning|history|diy|review|reviews|guide|brands|"
                             r"best|top)\b", re.I)
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
def clave_variante(keyword: str) -> str:
    """'Club Sofas', 'club sofa', 'a club sofa' → 'club sofa': la misma búsqueda."""
    ws = [_singular(w) for w in re.findall(r"[a-z0-9]+", _plano(keyword))]
    while ws and ws[0] in ("a", "an", "the"):
        ws = ws[1:]
    return " ".join(ws)


def acumula_sinonimos(keyword: str) -> str:
    """'wall light fixture sconce' → 'light, sconce': dos palabras que nombran el
    mismo tipo de producto. 'table lamp' o 'bed frame' no (son tipo compuesto)."""
    ws = [_singular(w) for w in _palabras(keyword)]
    for i, a in enumerate(ws):
        for b in ws[i + 1:]:
            if a != b and (b in _SINONIMOS_TIPO.get(a, set()) or a in _SINONIMOS_TIPO.get(b, set())):
                return f"{a}, {b}"
    return ""


# después del tipo solo puede venir otra palabra de tipo ('bed frame', 'chair set')
_COLAS_DE_TIPO = {"frame", "frames", "set", "sets"}


def nucleo_al_final(keyword: str, tipos: Iterable[str], nombre: str, marca: str) -> bool:
    """En inglés el tipo va al final: 'marble coffee table', 'designer wall
    sconces'. 'mirror home' o 'piano italian' son órdenes que nadie escribe en
    una ficha (prueba 11-nov: el validador las rechazó por forzadas). Las
    búsquedas de modelo o marca + modelo ('luceplan illan') quedan libres."""
    palabras = [w for w in re.findall(r"[a-z]+", _plano(keyword)) if w not in _VACIAS]
    if not palabras:
        return True
    tipos = {_singular(t) for t in tipos}
    if not ({_singular(w) for w in palabras} & tipos):
        return True                       # no nombra un tipo: lo juzgan otras reglas
    ultima = palabras[-1]
    if _singular(ultima) in tipos or ultima in _COLAS_DE_TIPO:
        return True
    return es_marca_y_modelo(keyword, nombre, marca) and _singular(ultima) in {
        _singular(w) for w in _palabras(f"{nombre} {marca}")}


# 'table in glass': el tipo y después 'in' + material es una variante que nadie
# escribe en una ficha (devolución SEO 6-nov); se dice 'glass table'
_VARIANTE_FORZADA = re.compile(r"^([a-z]+) in ([a-z]+)$")


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


# modificadores que no cambian QUÉ es el producto: pueden ir en una keyword aunque
# la ficha no los diga (prueba real 4-nov: la investigación traía 'metal folding
# chairs' para una silla de diseño y 'lamp led for nails' para una aplique)
MODIFICADORES_NEUTROS = {"modern", "contemporary", "luxury", "luxurious", "designer",
                         "design", "italian", "italy", "style", "styled", "elegant",
                         "unique", "decorative", "high", "end", "statement", "iconic",
                         "furniture", "home", "interior", "large", "small", "big"}


def palabras_sin_respaldo(keyword: str, texto_ficha: str, tipos: Iterable[str] = ()) -> list[str]:
    """Palabras de la keyword que la ficha NO dice (ni nombre, marca, categoría,
    atributos ni descripción) y que no son un modificador neutro ni un sinónimo
    del tipo. Para keywords de investigación y competencia: la keyword tiene que
    describir ESTE producto, no compartir una palabra suelta con él."""
    de_la_ficha = {_singular(w) for w in _palabras(texto_ficha)}
    ok = de_la_ficha | {_singular(t) for t in tipos} | MODIFICADORES_NEUTROS | _VACIAS
    return [w for w in re.findall(r"[a-z]+", _plano(keyword))
            if _singular(w) not in ok and w not in ok]


# piezas o repuestos: quien busca 'chair legs' o 'table top' no busca el mueble
# (prueba real 4-nov)
PIEZAS = {"leg", "legs", "top", "tops", "cushion", "cushions", "cover", "covers",
          "part", "parts", "replacement", "replacements", "hardware", "caster",
          "casters", "glides", "slipcover", "slipcovers", "pad", "pads", "kit"}


def problema_de_tipo(keyword: str, nombre: str, tipos: Iterable[str]) -> str:
    """Para keywords de investigación y competencia: '' si nombra ESTE tipo de
    producto; si no, el motivo. 'marble side table' no es una coffee table;
    'leather furniture' no nombra el tipo; 'chair legs' busca una pieza."""
    from .investigacion import _COMPUESTOS, tipo_compuesto
    palabras = re.findall(r"[a-z]+", _plano(keyword))
    if palabras and palabras[-1] in PIEZAS:
        return f"busca una pieza ('{palabras[-1]}'), no el producto"
    tipos = {_singular(t) for t in tipos}
    pos = [i for i, w in enumerate(palabras) if _singular(w) in tipos]
    if not pos:
        return "no nombra el tipo de producto"
    compuesto = tipo_compuesto(nombre or "")
    if " " in compuesto:
        prefijo, base = compuesto.split(" ", 1)
        for i in pos:
            if (_singular(palabras[i]) == base and i > 0 and palabras[i - 1] in _COMPUESTOS
                    and palabras[i - 1] != prefijo):
                return f"es otro tipo de producto ({palabras[i - 1]} {base})"
    return ""


# palabras de una keyword que AFIRMAN algo de la ficha, y lo que en la ficha lo
# contradice (prueba real 4-nov: 'leather armchair' en una silla Armless,
# 'outdoor sectional sofa' en un sofá Straight de tres cuerpos)
_CONTRADICCIONES = {
    "armchair": re.compile(r"\barmless\b"),
    "armchairs": re.compile(r"\barmless\b"),
    "sectional": re.compile(r"shape[^:]*:\s*straight|\b(two|three|2|3)[ -]seater\b"),
    "sectionals": re.compile(r"shape[^:]*:\s*straight|\b(two|three|2|3)[ -]seater\b"),
}
# 'antique' / 'vintage' solo si la ficha lo dice del producto, no como nombre de
# un acabado ('antique bronze satin' no hace antiguo al espejo)
_EPOCA = {"antique", "vintage"}
_ACABADO_TRAS = re.compile(r"\b(antique|vintage)\s+(bronze|brass|gold|silver|copper|"
                           r"white|black|oak|walnut|finish|satin|patina|leather|effect)\b")


def contradice_la_ficha(keyword: str, texto_ficha: str) -> str:
    """'' si la keyword no afirma nada que la ficha contradiga; si no, el motivo."""
    ficha = _plano(texto_ficha)
    for w in re.findall(r"[a-z]+", _plano(keyword)):
        rx = _CONTRADICCIONES.get(w)
        if rx and rx.search(ficha):
            return f"la ficha lo contradice ('{w}': {rx.search(ficha).group(0)})"
        if w in _EPOCA:
            sin_acabados = _ACABADO_TRAS.sub(" ", ficha)
            if not re.search(rf"\b{w}\b", sin_acabados):
                return f"la ficha no dice que sea {w} (solo un acabado)"
    return ""


def _singular(w: str) -> str:
    # 'beds' → 'bed' (con > 4 letras se escapaba: 'hermes beds' no se veía cubierta)
    # 'tennis', 'cactus' no son plurales
    return (w[:-1] if len(w) >= 4 and w.endswith("s")
            and not w.endswith(("ss", "is", "us")) else w)


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
        probada = 1 + 0.5 * max(0, (fila.get("competidores") or 0) - 1) + \
            (0.5 if fila.get("competidores") else 0)   # la rankea la competencia
        return demanda * 0.02 * max(0.0, 1 - kd / 100) * probada
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
                    nombre: Optional[str] = None, marca: str = "",
                    texto_ficha: Optional[str] = None,
                    reescritura: bool = False) -> dict:
    """Devuelve {elegidas, descartadas, faltan}.

    `reescritura`: la descripción se reescribe con la plantilla del SEO, que
    repite el modelo con su tipo ('shibari chairs', 'luceplan illan'): una
    keyword que ya cubre el H1 sí puede ir en la descripción.

    `candidatas`: [{keyword, volume?, impressions?, position?, ...}]
    `asignadas`: {keyword normalizada: url} de keywords ya escritas en otras fichas.
    `texto_especifico`: nombre + marca + atributos; si se pasa, la keyword tiene
    que compartir una palabra con eso que no sea de la categoría.
    `texto_ficha`: todo lo que dice la ficha (nombre, marca, categorías, atributos y
    descripción); si se pasa, cada palabra de una keyword de investigación o de
    competencia tiene que estar ahí (o ser un modificador neutro).
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

    if reescritura:
        # la variante que más vale primero: 'club sofa' y 'club sofas' son UNA
        # búsqueda, y no pueden ocupar dos lugares (prueba de ajuste 11-nov)
        candidatas = sorted(candidatas, key=_orden, reverse=True)
    for c in candidatas:
        kw = (c.get("keyword") or "").strip()
        nk = clave_variante(kw) if reescritura else _norm(kw)
        if not nk or nk in vistas:
            continue
        vistas.add(nk)
        if reescritura and re.match(r"(a|an|the)\s", _plano(kw)):
            descartadas.append({"keyword": kw, "motivo": "empieza con un artículo: es una "
                                                         "variante de otra búsqueda"})
        elif reescritura and acumula_sinonimos(kw):
            descartadas.append({"keyword": kw, "motivo": "encadena sinónimos del tipo "
                                                         f"({acumula_sinonimos(kw)}): no es "
                                                         "una frase que se escriba"})
        elif _palabras(kw) & PALABRAS_SENSIBLES:
            descartadas.append({"keyword": kw, "motivo": "contenido sensible"})
        elif c.get("descartar"):
            descartadas.append({"keyword": kw, "motivo": c["descartar"]})
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
        elif _VARIANTE_FORZADA.search(_plano(kw)) and nombre is not None \
                and _singular(_VARIANTE_FORZADA.search(_plano(kw)).group(1)) in tipos_propios:
            m = _VARIANTE_FORZADA.search(_plano(kw))
            descartadas.append({"keyword": kw, "motivo": f"variante forzada: se dice "
                                                         f"'{m.group(2)} {m.group(1)}'"})
        elif (c.get("origen") == "investigacion" and nombre is not None
              and not (_palabras(kw) & (atributos_palabras | _palabras(marca)))):
            descartadas.append({"keyword": kw, "motivo": "no menciona ningún material, "
                                                         "acabado o estilo de la ficha"})
        elif texto_ficha is not None and contradice_la_ficha(kw, texto_ficha):
            descartadas.append({"keyword": kw, "motivo": contradice_la_ficha(kw, texto_ficha)})
        elif (c.get("origen") in ("investigacion", "competidor") and nombre is not None
              and problema_de_tipo(kw, nombre, tipos_propios)):
            descartadas.append({"keyword": kw, "motivo": problema_de_tipo(kw, nombre,
                                                                          tipos_propios)})
        elif (texto_ficha is not None
              and palabras_sin_respaldo(kw, texto_ficha, tipos_propios)):
            # también las de GSC (6-nov): 'steinway grand piano' en un piano que la
            # ficha no dice que sea de cola
            descartadas.append({"keyword": kw, "motivo": "la ficha no dice '"
                                + "', '".join(palabras_sin_respaldo(kw, texto_ficha,
                                                                    tipos_propios)) + "'"})
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
        elif reescritura and nombre is not None and not nucleo_al_final(kw, tipos, nombre, marca):
            descartadas.append({"keyword": kw, "motivo": "el tipo de producto no va al final "
                                                         "('mirror home', 'piano italian'): "
                                                         "no se escribe así en inglés"})
        elif (nombre is not None and not reescritura
              and cubierta_por_el_h1(kw, nombre, marca)):
            descartadas.append({"keyword": kw, "motivo": "ya la cubre el H1 nuevo"})
        elif c.get("position") and c["position"] > POSICION_MAX:
            descartadas.append({"keyword": kw, "motivo": f"la ficha no compite "
                                                         f"(posición {c['position']:.0f})"})
        elif (nombre is not None and not nombra_el_tipo(kw, tipos)
              and not es_marca_y_modelo(kw, nombre, marca)
              and not (reescritura and nombra_el_modelo(kw, nombre, marca))):
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
