# -*- coding: utf-8 -*-
"""Reglas del SEO (Alex, 17-nov-2026), en código: las decisiones donde el modelo se
equivocaba ya no las toma el modelo.

H1 — "prioricemos sobre lo que la gente busca":
- si el nombre del producto ya tiene volumen ('club sofa', 1.000/mes), el H1 es
  nombre + marca: 'Club Sofa by Rugiano';
- si no, se agrega el rasgo MÁS BUSCADO de la ficha: entre sus materiales, el de
  mayor volumen como '{material} {tipo}' ('marble coffee table' 33.100 >
  'wood coffee table' 27.100 → 'Rock Marble Coffee Table by Rugiano').

Keywords — "lo que funciona son las consultas que ya traen impresiones en Search
Console y las de marca más tipo ('nomon wall clock')":
- primero las de Search Console con impresiones que no repiten el H1 ni dicen algo
  que la ficha no dice;
- después marca + tipo con volumen;
- genéricas como en la referencia de Alex (23-nov): el material EXACTO del H1 con el
  tipo corto, sin repetir el H1 ('marble table', 'glass table', 'wood and leather
  chair'). Nunca un material que la ficha no tiene ('marble table' en Palatial) ni un
  tipo corto que es otro producto ('leather table' de una mesa de pool, Dandy).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Iterable, Optional

from .h1 import _singular, es_codigo, modelo_de, sin_codigos
from .keywords import palabras_sin_respaldo

UMBRAL_NOMBRE = 50        # búsquedas/mes para que el nombre solo alcance
MIN_IMPRESIONES = 2
MIN_IMPRESIONES_GENERICA = 5   # búsquedas de GSC que no nombran el modelo ni la marca
MIN_VOL_MARCA = 10
MIN_VOL_GENERICA = 50
MAX_KEYWORDS = 3              # objetivo: 3 (decisión del 23-nov)
MIN_KEYWORDS = 3              # mínimo: 3, siempre coherentes con la ficha (23-nov)


def _plano(s: str) -> str:
    return unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()


def _norm(s: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", _plano(s)))


def _titulo(s: str) -> str:
    return " ".join(w if w.isupper() else w[:1].upper() + w[1:] for w in s.split())


def nombre_de_busqueda(nombre: str) -> str:
    """'Cleopatra Chair (SC1019)' → 'cleopatra chair'; 'Dandy Pool Table (7, 8 or 9
    feet)' → 'dandy pool table'. Lo que la gente escribiría para buscarlo."""
    limpio = re.sub(r"\([^)]*\)", " ", sin_codigos(nombre or ""))
    limpio = re.split(r"\s[-–—]\s", limpio)[0]
    return _norm(limpio)


# fabricantes de pianos que aparecen en nombres de la tienda («19800 Steinway Piano» de
# Riva Mobili D'Arte): el volumen de su búsqueda es el de esa marca, no el de la pieza
# (18-nov). Sin marcas de autos o de moda: en Cassoni son nombres de modelo (Hermes
# Maxi, Tiffany, Harley) y no se pueden distinguir por el nombre (23-nov).
MARCAS_AJENAS = frozenset({
    "steinway", "bosendorfer", "fazioli", "bechstein", "yamaha", "kawai", "bluthner",
    "petrof", "schimmel", "grotrian",
})


# el nombre completo de la marca respalda sus búsquedas («steinway and sons piano»:
# Alex usa «steinway and sons pianos»)
NOMBRE_COMPLETO = {"steinway": "steinway and sons", "bluthner": "bluthner pianos"}


def marca_ajena_en(nombre: str, marca: str) -> str:
    """La marca de otro fabricante que ES el modelo de la ficha, o ''.
    '19800 Steinway Piano' → 'steinway'; 'Aurora Steinway Grand Piano' → '' (tiene
    modelo propio: el volumen de su nombre sí es de la pieza)."""
    modelo = _norm(modelo_de(nombre or "", marca or ""))
    propia = _norm(marca)
    if modelo in MARCAS_AJENAS and modelo not in propia:
        return modelo
    return ""


def _partes_del_nombre(nombre: str) -> list[str]:
    """Palabras de la parte principal del nombre: sin paréntesis de códigos ni lo que
    va después de ' - '."""
    limpio = re.sub(r"\([^)]*\)", " ", nombre or "")
    limpio = re.split(r"\s[-–—]\s", limpio)[0]
    return limpio.split()


def sufijo_del_nombre(nombre: str, marca: str, tipo: str) -> str:
    """Lo que el nombre dice después del tipo y el H1 no puede perder:
    'Cleopatra Chair Limited Edition' → 'Limited Edition'; 'Club Sofa 3-Seater' →
    '3-Seater'. Sin códigos de catálogo ni la marca."""
    if not tipo:
        return ""
    ultima = _singular(_norm(tipo).split()[-1])
    palabras = [w for w in _partes_del_nombre(sin_codigos(nombre)) if not es_codigo(w)]
    idx = [i for i, w in enumerate(palabras) if _singular(_norm(w)) == ultima]
    if not idx:
        return ""
    resto = palabras[idx[-1] + 1:]
    marca_w = set(_norm(marca).split())
    resto = [w for w in resto if _norm(w) not in marca_w and _norm(w) != "by"]
    return " ".join(resto).strip()


# materiales de tapizado: cuando la opción es el tapizado, Alex no elige uno en el H1
# («Hermes Maxi Upholstered King Bed») y no suma keywords por opción (23-nov)
TAPIZADOS = frozenset({"fabric", "leather", "velvet", "boucle", "suede", "linen", "cotton",
                       "wool", "nubuck", "eco leather", "faux leather", "microfiber"})


def grupos_de_opciones(texto: str, materiales: Iterable[str]) -> list[list[str]]:
    """Cada «X or Y» entre dos materiales distintos de una misma oración es un grupo:
    Rock → [['wood', 'marble']]; Club Sofa («brass or bronze tubes … leather or
    fabric») → [['brass', 'bronze'], ['leather', 'fabric']]."""
    mats = sorted({_norm(m) for m in materiales if m}, key=len, reverse=True)
    grupos: list[list[str]] = []
    for oracion in re.split(r"(?<=[.!?;])\s+|\n+", _plano(texto)):
        palabras = _norm(oracion).split()
        for i, w in enumerate(palabras):
            if w != "or":
                continue
            izq = " " + " ".join(palabras[max(0, i - 6):i]) + " "
            der = " " + " ".join(palabras[i + 1:i + 9]) + " "
            a = [m for m in mats if f" {m} " in izq]
            b = [m for m in mats if f" {m} " in der]
            if a and b:
                a1 = max(a, key=lambda m: izq.rfind(f" {m} "))
                b1 = min(b, key=lambda m: der.find(f" {m} "))
                if a1 != b1 and [a1, b1] not in grupos:
                    grupos.append([a1, b1])
    return grupos


def opciones_de_material(texto: str, materiales: Iterable[str]) -> list[str]:
    """Todos los materiales que la ficha ofrece como alternativa, sin repetir."""
    out: list[str] = []
    for g in grupos_de_opciones(texto, materiales):
        out += [m for m in g if m not in out]
    return out


def opciones_para_h1(texto: str, materiales: Iterable[str]) -> list[str]:
    """La única opción estructural de la ficha (la tapa de Rock: madera o mármol), que
    decide el H1 y suma una keyword por opción. Vacío si hay más de un grupo (Club
    Sofa) o si la opción es el tapizado (Hermes: «Upholstered», lo escribe el redactor)."""
    grupos = grupos_de_opciones(texto, materiales)
    if len(grupos) != 1 or set(grupos[0]) <= TAPIZADOS:
        return []
    return grupos[0]


# tipos que acortados son OTRO producto: quien busca «leather table» no quiere una
# mesa de pool (Dandy, devolución de Alex del 17-nov)
_NO_ACORTAR = frozenset({"pool table", "billiard table", "foosball table", "ping pong table",
                         "table tennis table", "game table", "card table", "poker table",
                         "air hockey table", "massage table"})


def cabeza_de(tipo: str) -> str:
    """El tipo corto que sigue siendo el mismo producto: 'coffee table' → 'table',
    'outdoor sofa' → 'sofa', 'armchair' → 'armchair'; 'pool table' → '' (no se acorta)."""
    t = _norm(tipo)
    if t.startswith("outdoor "):
        t = t[len("outdoor "):]
    if not t or t in _NO_ACORTAR:
        return ""
    return t.split()[-1]


def keywords_de_opciones(opciones: Iterable[str], nucleo: str, vol: dict,
                         minimo: int = 0) -> list[dict]:
    """Una keyword por opción, de la más buscada a la menos: la forma corta como Alex
    ('marble table', 'wood table') si tiene volumen; si no, '{opción} {tipo}'."""
    minimo = minimo or MIN_VOL_GENERICA
    cabeza = cabeza_de(nucleo)
    out = []
    for m in opciones:
        for kw in ([f"{m} {cabeza}".lower()] if cabeza else []) + [f"{m} {nucleo}".lower()]:
            v = int((vol.get(kw) or {}).get("volume") or 0)
            if v >= minimo:
                out.append({"keyword": kw, "origen": "opcion", "volumen": v, "material": m})
                break
    return sorted(out, key=lambda k: -k["volumen"])


def rasgo_combinado(texto: str, materiales: Iterable[str], nucleo: str,
                    vol: dict, minimo: int = 0) -> Optional[tuple[str, int]]:
    """('{m1} and {m2}', volumen) cuando la PRIMERA oración define el producto con dos
    materiales que no son opciones entre sí y la combinación se busca:
    «Wooden chair with leather upholstery» → ('wood and leather', 1300), como el
    «Cleopatra Wood and Leather Dining Chair» de Alex. Si no, None."""
    minimo = minimo or MIN_VOL_GENERICA
    cabeza = cabeza_de(nucleo)
    if not cabeza:
        return None
    primera = re.split(r"(?<=[.!?;])\s+|\n+", (texto or "").strip())[0]
    t = " " + _norm(primera).replace(" wooden ", " wood ") + " "
    t = re.sub(r"^ wooden ", " wood ", t)
    en_opcion = {m for g in grupos_de_opciones(primera, materiales) for m in g}
    mats = [m for m in {_norm(x) for x in materiales if x}
            if f" {m} " in t and m not in en_opcion]
    # sin los que cubre uno más largo ('wood' dentro de 'rosewood' no aplica: palabras)
    mats = sorted(mats, key=lambda m: t.find(f" {m} "))
    if len(mats) != 2:
        return None
    frase = f"{mats[0]} and {mats[1]}"
    v = max(int((vol.get(f"{frase} {cabeza}") or {}).get("volume") or 0),
            int((vol.get(f"{mats[1]} and {mats[0]} {cabeza}") or {}).get("volume") or 0))
    return (frase, v) if v >= minimo else None


def h1_por_datos(nombre: str, marca: str, tipo: str, vol_nombre: Optional[int],
                 rasgos: Iterable[tuple[str, int]], umbral: int = UMBRAL_NOMBRE,
                 opciones: Iterable[str] = (), marca_ajena: str = "",
                 combinado: Optional[tuple[str, int]] = None) -> dict:
    """{'h1', 'regla', 'rasgo', 'fijo'}. `rasgos`: (material, volumen de '{material}
    {tipo}') solo con materiales que la ficha confirma. `fijo`: el H1 ya está decidido
    y el redactor no lo cambia. `opciones`: materiales que la ficha ofrece como
    alternativa de la parte principal. `marca_ajena`: marca de otro fabricante en el
    nombre; su volumen no cuenta como «el nombre ya se busca». Los códigos de
    catálogo no van («SC1019», «19800»: Alex los saca en su referencia)."""
    rasgos = list(rasgos)
    por = f" by {marca}" if marca else ""
    base = " ".join(w for w in _partes_del_nombre(sin_codigos(nombre))
                    if not es_codigo(w.strip(",.;:")))
    base = re.sub(r"\s+", " ", base).strip(" -–—|")
    suf = sufijo_del_nombre(nombre, marca, tipo)
    suf = f" {suf}" if suf else ""
    nota = (f"; el volumen del nombre ({vol_nombre}/mes) es de la marca {marca_ajena}, "
            "no de esta pieza") if marca_ajena and vol_nombre else ""
    if vol_nombre and vol_nombre >= umbral and not marca_ajena:
        return {"h1": f"{base}{por}", "regla": f"el nombre ya se busca ({vol_nombre}/mes)",
                "rasgo": "", "fijo": True}
    if not tipo:
        return {"h1": f"{base}{por}", "regla": "sin tipo de producto: nombre + marca" + nota,
                "rasgo": "", "fijo": True}
    modelo = modelo_de(nombre, marca) or base
    ops = {_norm(o) for o in opciones}
    mejor_op = max(((m, v) for m, v in rasgos if v and _norm(m) in ops),
                   key=lambda x: x[1], default=None)
    if len(ops) >= 2 and mejor_op:
        return {"h1": f"{modelo} {_titulo(mejor_op[0])} {_titulo(tipo)}{suf}{por}",
                "regla": (f"opción más buscada: '{mejor_op[0]} {tipo}' ({mejor_op[1]}/mes); "
                          f"la descripción cubre las opciones: {', '.join(sorted(ops))}") + nota,
                "rasgo": mejor_op[0], "fijo": True}
    if combinado:
        frase = _titulo(combinado[0]).replace(" And ", " and ")
        return {"h1": f"{modelo} {frase} {_titulo(tipo)}{suf}{por}",
                "regla": (f"el producto es de {combinado[0]} (primera oración; "
                          f"'{combinado[0]} {cabeza_de(tipo)}' {combinado[1]}/mes)") + nota,
                "rasgo": combinado[0], "fijo": True}
    mejor = max(((m, v) for m, v in rasgos if v), key=lambda x: x[1], default=None)
    if mejor:
        return {"h1": f"{modelo} {_titulo(mejor[0])} {_titulo(tipo)}{suf}{por}",
                "regla": f"rasgo más buscado: '{mejor[0]} {tipo}' ({mejor[1]}/mes)" + nota,
                "rasgo": mejor[0], "fijo": False}
    return {"h1": f"{modelo} {_titulo(tipo)}{suf}{por}",
            "regla": "ningún rasgo con volumen: modelo + tipo" + nota, "rasgo": "", "fijo": True}


def rasgos_con_volumen(materiales: Iterable[str], tipo: str, vol: dict) -> list[tuple[str, int]]:
    """(material, volumen de '{material} {tipo}') para cada material de la ficha."""
    out = []
    for m in materiales:
        v = (vol.get(f"{m} {tipo}".lower()) or {}).get("volume") or 0
        out.append((m, int(v)))
    return out


def genericas_opcionales(materiales: Iterable[str], nucleo: str, vol: dict,
                         minimo: int = MIN_VOL_GENERICA, n: int = 8) -> list[tuple[str, int, str]]:
    """(keyword, volumen, material) con volumen, armadas solo con materiales de la
    ficha: '{m} {tipo}', '{m} {tipo corto}', '{tipo} in {m}' y de a dos materiales
    '{m1} and {m2} {tipo corto}'. El redactor suma las del material de SU H1
    (genericas_para_h1)."""
    mats = [_norm(m) for m in materiales if m]
    cabeza = cabeza_de(nucleo)
    formas: list[tuple[str, str]] = []
    for m in mats:
        formas += [(f"{m} {nucleo}", m), (f"{nucleo} in {m}", m)]
        if cabeza:
            formas.append((f"{m} {cabeza}", m))
    if cabeza:
        for i, m1 in enumerate(mats):
            for m2 in mats[i + 1:]:
                formas += [(f"{m1} and {m2} {cabeza}", f"{m1} {m2}"),
                           (f"{m2} and {m1} {cabeza}", f"{m1} {m2}")]
    out, vistas = [], set()
    for kw, material in formas:
        kw = _norm(kw)
        v = int((vol.get(kw) or {}).get("volume") or 0)
        if v >= minimo and kw not in vistas:
            vistas.add(kw)
            out.append((kw, v, material))
    return sorted(out, key=lambda x: -x[1])[:n]


def genericas_para_h1(h1: str, opcionales, maximo: int = 2) -> list[tuple[str, int, str]]:
    """Las genéricas que corresponden a ESTE H1, como Alex: su material es exactamente
    el del H1 (Cleopatra «Wood and Leather» → 'wood and leather chair', no 'wood chair'),
    no repiten el H1 tal cual (Bakkarat: 'dining table in glass' y 'glass table', no
    'glass dining table'), una por combinación de palabras, en el orden del H1."""
    h1n = f" {_norm(h1)} "
    h1w = set(h1n.split())
    mats_h1 = {w for _, _, mat in opcionales for w in _norm(mat).split() if w in h1w}
    if not mats_h1:
        return []
    out, vistas = [], set()

    def _orden(item):
        kw, v, _ = item
        # primero la que sigue el orden del H1 ('wood and leather' antes que 'leather and wood')
        palabras = [w for w in kw.split() if w in mats_h1]
        en_orden = palabras == sorted(palabras, key=lambda w: h1n.find(f" {w} "))
        return (not en_orden, -v)

    for kw, v, mat in sorted(opcionales, key=_orden):
        clave = frozenset(kw.split())
        if (set(_norm(mat).split()) != mats_h1 or f" {kw} " in h1n or clave in vistas):
            continue
        vistas.add(clave)
        out.append((kw, v, mat))
        if len(out) >= maximo:
            break
    return out


def generica_usada(descripcion_plana: str, h1: str, opcionales):
    """(keyword, volumen, ok) de la primera genérica opcional que usó el redactor, o
    None. ok = todas las palabras de su material están en el H1."""
    usadas = genericas_usadas(descripcion_plana, h1, opcionales)
    return usadas[0] if usadas else None


def genericas_usadas(descripcion_plana: str, h1: str, opcionales) -> list[tuple[str, int, bool]]:
    """Todas las genéricas opcionales que usó el redactor: (keyword, volumen, ok)."""
    texto, h1w = _norm(descripcion_plana), set(_norm(h1).split())
    out = []
    for kw, v, material in opcionales:
        if re.search(rf"(?<![a-z]){re.escape(_norm(kw))}(?![a-z])", texto):
            out.append((kw, v, set(_norm(material).split()) <= h1w))
    return out


_RELLENO = frozenset({"and", "with", "in", "for", "the", "a", "of", "by"})


def candidatas_de_competencia(rankeadas: Iterable[dict], *, h1: str, nombre: str, marca: str,
                              tipo: str, texto_ficha: str, minimo: int = 0,
                              origen: str = "competidor") -> list[dict]:
    """Keywords que la competencia rankea con el MISMO producto (DataForSEO
    ranked_keywords, hasta 3 competidores) que esta ficha puede usar, con los filtros de
    Alex: nombran el tipo sin volverlo otro producto ('leather table' de una mesa de
    pool no), no son el tipo suelto ('coffee table'), la ficha respalda cada palabra,
    no repiten el H1 y tienen volumen. Primero las que rankean más competidores."""
    minimo = minimo or MIN_VOL_GENERICA
    nucleo = _norm(tipo)
    nucleo = nucleo[len("outdoor "):] if nucleo.startswith("outdoor ") else nucleo
    cabeza = cabeza_de(nucleo)
    tipo_w = {_singular(w) for w in nucleo.split()}
    tipos = set(nucleo.split()) | {"couch", "light", "lamp"}
    h1n = f" {_norm(h1)} "
    nombre_n = nombre_de_busqueda(nombre)
    out, vistas = [], set()
    for c in rankeadas or []:
        kw = _norm(c.get("keyword") or "")
        v = int(c.get("volume") or c.get("volumen") or 0)
        palabras = kw.split()
        sing = [_singular(w) for w in palabras]
        # termina en el tipo, como una frase normal en inglés: «foam bed king» no (23-nov)
        nombra_tipo = ((cabeza and sing and sing[-1] == _singular(cabeza))
                       or (not cabeza and kw.endswith(nucleo)))
        resto = [w for w, s_ in zip(palabras, sing) if s_ not in tipo_w and w not in _RELLENO]
        if len(set(sing)) < len(sing) or {"a", "an", "the"} & set(palabras):
            continue                     # «steinway piano piano», «steinway a piano»
        if (not kw or kw in vistas or v < minimo or not nombra_tipo or not resto
                or not re.fullmatch(r"[a-z0-9' &-]+", (c.get("keyword") or "").lower())
                or f" {kw} " in h1n or kw == nombre_n
                or palabras_sin_respaldo(kw, texto_ficha, tipos)):
            continue
        vistas.add(kw)
        out.append({"keyword": kw, "origen": origen, "volumen": v,
                    "competidores": int(c.get("competidores") or 1),
                    "mejor_posicion": c.get("mejor_posicion")})
    return sorted(out, key=lambda c: (-c["competidores"], -c["volumen"]))


def elegir_keywords(candidatas: list[dict], *, nombre: str, marca: str, tipo: str,
                    h1: str, rasgo: str, texto_ficha: str,
                    opciones: Optional[list[dict]] = None, marca_ajena: str = "",
                    genericas_h1: Optional[list[dict]] = None,
                    competencia: Optional[list[dict]] = None) -> dict:
    """{'elegidas': [...], 'descartadas': [{keyword, motivo}]} sin LLM.
    `opciones`: keywords '{opción} {tipo}' (keywords_de_opciones); entran todas después
    de Search Console, aunque el H1 diga una. `marca_ajena`: no cambia la elección
    (Alex usa la marca como keyword: «steinway and sons pianos»)."""
    opciones = opciones or []
    genericas_h1 = genericas_h1 or []
    # las genéricas del H1 ya decidido ocupan su lugar entre las 3, no se suman como
    # cuarta (Cleopatra con 4 keywords y dos líneas de texto: keyword stuffing, 23-nov)
    max_gsc = 1 if len(opciones) + len(genericas_h1) >= 2 else 2
    if marca_ajena:
        texto_ficha = f"{texto_ficha} {NOMBRE_COMPLETO.get(marca_ajena, marca_ajena)}"
    h1n = _norm(h1)
    nombre_n = nombre_de_busqueda(nombre)
    modelo_n = _norm(modelo_de(nombre, marca))
    marca_n = _norm(marca)
    tipos = set(_norm(tipo).split()) | {"couch", "light", "lamp"}
    elegidas: list[dict] = []
    descartadas: list[dict] = []
    vistas: set[str] = set()

    def _clave(k: str) -> str:
        k = (k or "").replace("&", " and ")
        return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w
                        for w in _norm(k).replace("'s ", " ").split())

    def _agregar(c: dict, por: str) -> bool:
        # las mismas palabras en otro orden son la misma keyword («chair shibari»)
        k = " ".join(sorted(_clave(c["keyword"]).split()))
        if k in vistas or len(elegidas) >= MAX_KEYWORDS:
            return False
        vistas.add(k)
        elegidas.append({**c, "por_que": por})
        return True

    modelo_w = set(modelo_n.split())
    nombre_w = nombre_n.split()

    def _nombra(kw: str) -> int:
        w = set(kw.split())
        return 2 if w & modelo_w else (1 if marca_n and marca_n in kw else 0)

    # 1) Search Console: ya trae impresiones; primero las variantes del nombre
    def _motivo_gsc(c: dict, relajado: bool = False) -> Optional[str]:
        kw = _norm(c["keyword"])
        imp = c.get("impresiones") or 0
        minimo_gen = MIN_IMPRESIONES if relajado else MIN_IMPRESIONES_GENERICA
        if not re.fullmatch(r"[a-z0-9' &-]+", (c["keyword"] or "").lower()):
            return "tiene símbolos que no son de una búsqueda escrita"
        if imp < MIN_IMPRESIONES or (not _nombra(kw) and imp < minimo_gen):
            return "pocas impresiones"
        if len(kw.split()) < len(nombre_w) and nombre_w[:len(kw.split())] == kw.split():
            return "es el nombre recortado"
        if kw in h1n or kw in (nombre_n, modelo_n):
            return "ya lo dice el H1 o es el nombre tal cual"
        if kw == marca_n or (marca_ajena and _clave(kw) in {
                _clave(marca_ajena), _clave(NOMBRE_COMPLETO.get(marca_ajena, marca_ajena))}):
            return "es solo la marca"
        sin = palabras_sin_respaldo(kw, texto_ficha, tipos)
        if sin:
            return "la ficha no dice " + ", ".join(f"'{w}'" for w in sin)
        return None

    gsc = sorted((c for c in candidatas if c.get("origen") == "gsc"),
                 key=lambda c: (-_nombra(_norm(c["keyword"])), "&" in (c["keyword"] or ""),
                                -(c.get("impresiones") or 0)))
    flojas: list[dict] = []
    reservas: list[dict] = []          # pasan todos los filtros pero no entraron
    for c in gsc:
        motivo = _motivo_gsc(c)
        if motivo is None:
            if len([e for e in elegidas if e["origen"] == "gsc"]) >= max_gsc:
                reservas.append({**c, "por_que": f"ya aparece en Google ({c.get('impresiones')} impresiones)"})
                motivo = ("ya hay una de Search Console y las opciones de la ficha"
                          if max_gsc == 1 else "ya hay dos de Search Console")
            elif _agregar(c, f"ya aparece en Google ({c.get('impresiones')} impresiones)"):
                continue
            else:
                motivo = "repite otra elegida"
        elif motivo == "pocas impresiones":
            flojas.append(c)
        descartadas.append({"keyword": c["keyword"], "motivo": motivo})

    # 2) una por cada opción de la parte principal (Rock: mármol y madera)
    for c in opciones:
        _agregar(c, f"opción de la ficha ({c.get('volumen')}/mes)")

    for c in genericas_h1:
        _agregar(c, f"el material del H1 con el tipo ({c.get('volumen')}/mes)")

    # 3) marca + tipo, con volumen
    if marca_n:
        for c in sorted((c for c in candidatas if c.get("origen") == "generica"
                         and _norm(c["keyword"]).startswith(marca_n + " ")),
                        key=lambda c: -(c.get("volumen") or 0)):
            resto = set(_norm(c["keyword"])[len(marca_n):].split())
            if (c.get("volumen") or 0) >= MIN_VOL_MARCA and resto & {_clave(t) for t in tipos} | resto & tipos \
                    and _norm(c["keyword"]) not in h1n:
                if any(e.get("por_que", "").startswith("marca + tipo") for e in elegidas):
                    reservas.append({**c, "por_que": f"marca + tipo ({c.get('volumen')}/mes)"})
                elif not _agregar(c, f"marca + tipo ({c.get('volumen')}/mes)"):
                    reservas.append({**c, "por_que": f"marca + tipo ({c.get('volumen')}/mes)"})

    # 3b) el tipo de producto específico y «italian + tipo», como Alex («wall sconce»,
    #     «wall light» en Illan; «italian piano» en Steinway). Nunca el tipo de una palabra
    nucleo_t = _norm(tipo)
    nucleo_t = nucleo_t[len("outdoor "):] if nucleo_t.startswith("outdoor ") else nucleo_t
    from .criterio_seo import _SINONIMOS
    frases_tipo = {nucleo_t, _norm(tipo), *(_norm(x) for x in _SINONIMOS.get(_norm(tipo), [])),
                   *(_norm(x) for x in _SINONIMOS.get(nucleo_t, []))}
    if re.search(r"\b(italy|italian)\b", _plano(texto_ficha)):
        frases_tipo.add(f"italian {cabeza_de(nucleo_t) or nucleo_t.split()[-1]}")
    de_tipo = sorted((c for c in candidatas if c.get("origen") == "generica"
                      and _norm(c["keyword"]) in frases_tipo and len(_norm(c["keyword"]).split()) >= 2
                      and (c.get("volumen") or 0) >= MIN_VOL_GENERICA),
                     key=lambda c: -(c.get("volumen") or 0))
    for c in de_tipo:
        if len(elegidas) >= MAX_KEYWORDS:
            reservas.append({**c, "por_que": f"el tipo de producto ({c.get('volumen')}/mes)"})
            continue
        _agregar(c, f"el tipo de producto ({c.get('volumen')}/mes)")

    # 4) relleno: lo que la competencia rankea con el mismo producto, si quedó lugar
    competencia = competencia or []
    def _por_que_relleno(c: dict, extra: str = "") -> str:
        if c.get("origen") == "sugerencia":
            return f"se busca con el nombre o el fabricante ({c.get('volumen')}/mes{extra})"
        return (f"la rankean {c.get('competidores', 1)} competidores con el mismo producto "
                f"({c.get('volumen')}/mes{extra})")

    for c in competencia:
        if len(elegidas) >= MAX_KEYWORDS:
            break
        if (c.get("volumen") or 0) >= MIN_VOL_GENERICA:
            _agregar(c, _por_que_relleno(c))

    # 5) mínimo de 3: se afloja el umbral, nunca la coherencia. Primero
    #    Search Console con 2+ impresiones, después la competencia con menos volumen
    if len(elegidas) < MIN_KEYWORDS:
        for c in flojas:
            if len(elegidas) >= MIN_KEYWORDS:
                break
            if _motivo_gsc(c, relajado=True) is None and _agregar(
                    c, f"ya aparece en Google ({c.get('impresiones')} impresiones; para llegar "
                       f"al mínimo de {MIN_KEYWORDS})"):
                descartadas[:] = [d for d in descartadas if d["keyword"] != c["keyword"]]
        for c in competencia:
            if len(elegidas) >= MIN_KEYWORDS:
                break
            _agregar(c, _por_que_relleno(c, f"; para llegar al mínimo de {MIN_KEYWORDS}"))

    # reservas: lo que pasa todos los filtros y no entró, en el mismo orden de
    # prioridad; si el redactor omite una por no entrar natural, se prueba la siguiente
    for c in flojas:
        if _motivo_gsc(c, relajado=True) is None:
            reservas.append({**c, "por_que": f"ya aparece en Google ({c.get('impresiones')} impresiones)"})
    for c in competencia:
        reservas.append({**c, "por_que": _por_que_relleno(c)})
    usadas = {" ".join(sorted(_clave(e["keyword"]).split())) for e in elegidas}
    reservas_ok = []
    for c in reservas:
        k = " ".join(sorted(_clave(c["keyword"]).split()))
        if k not in usadas:
            usadas.add(k)
            reservas_ok.append(c)

    # las genéricas por material no se eligen acá: dependen del H1 que escribe el
    # redactor (genericas_para_h1) o de la opción del H1 (keywords_de_opciones)
    elegidas_k = {e["keyword"] for e in elegidas}
    descartadas += [{"keyword": c["keyword"], "motivo": "no cumple las reglas del SEO"}
                    for c in candidatas if c["keyword"] not in elegidas_k
                    and c["keyword"] not in {d["keyword"] for d in descartadas}]
    return {"elegidas": elegidas, "descartadas": descartadas, "reservas": reservas_ok[:6]}
