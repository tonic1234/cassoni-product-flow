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
- una genérica solo si falta, y solo el rasgo del H1 con el tipo completo
  ('marble coffee table', nunca 'marble table' ni 'leather table').
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
MAX_KEYWORDS = 3


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


def keywords_de_opciones(opciones: Iterable[str], nucleo: str, vol: dict,
                         minimo: int = 0) -> list[dict]:
    """'{opción} {tipo}' con volumen, una por opción, de la más buscada a la menos:
    la descripción las cubre a todas (Rock: 'marble coffee table', 'wood coffee table')."""
    minimo = minimo or MIN_VOL_GENERICA
    out = []
    for m in opciones:
        kw = f"{m} {nucleo}".lower()
        v = int((vol.get(kw) or {}).get("volume") or 0)
        if v >= minimo:
            out.append({"keyword": kw, "origen": "opcion", "volumen": v, "material": m})
    return sorted(out, key=lambda k: -k["volumen"])


def h1_por_datos(nombre: str, marca: str, tipo: str, vol_nombre: Optional[int],
                 rasgos: Iterable[tuple[str, int]], umbral: int = UMBRAL_NOMBRE,
                 opciones: Iterable[str] = (), marca_ajena: str = "") -> dict:
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
                         minimo: int = MIN_VOL_GENERICA, n: int = 4) -> list[tuple[str, int, str]]:
    """('{material} {tipo}', volumen, material) con volumen, para que el redactor sume
    UNA y solo la del material que puso en el H1 ('Bakkarat Glass Dining Table' →
    'glass dining table')."""
    out = []
    for m in materiales:
        kw = f"{m} {nucleo}".lower()
        v = int((vol.get(kw) or {}).get("volume") or 0)
        if v >= minimo:
            out.append((kw, v, m))
    return sorted(out, key=lambda x: -x[1])[:n]


def generica_usada(descripcion_plana: str, h1: str, opcionales):
    """(keyword, volumen, ok) de la genérica opcional que usó el redactor, o None.
    ok = todas las palabras de su material están en el H1."""
    texto, h1w = _norm(descripcion_plana), set(_norm(h1).split())
    for kw, v, material in opcionales:
        if re.search(rf"(?<![a-z]){re.escape(_norm(kw))}(?![a-z])", texto):
            return kw, v, set(_norm(material).split()) <= h1w
    return None


def elegir_keywords(candidatas: list[dict], *, nombre: str, marca: str, tipo: str,
                    h1: str, rasgo: str, texto_ficha: str,
                    opciones: Optional[list[dict]] = None, marca_ajena: str = "") -> dict:
    """{'elegidas': [...], 'descartadas': [{keyword, motivo}]} sin LLM.
    `opciones`: keywords '{opción} {tipo}' (keywords_de_opciones); entran todas después
    de Search Console, aunque el H1 diga una. `marca_ajena`: no cambia la elección
    (Alex usa la marca como keyword: «steinway and sons pianos»)."""
    opciones = opciones or []
    max_gsc = 1 if len(opciones) >= 2 else 2
    h1n = _norm(h1)
    nombre_n = nombre_de_busqueda(nombre)
    modelo_n = _norm(modelo_de(nombre, marca))
    marca_n = _norm(marca)
    tipos = set(_norm(tipo).split()) | {"couch", "light", "lamp"}
    elegidas: list[dict] = []
    descartadas: list[dict] = []
    vistas: set[str] = set()

    def _clave(k: str) -> str:
        return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w
                        for w in _norm(k).replace("'s ", " ").split())

    def _agregar(c: dict, por: str) -> bool:
        k = _clave(c["keyword"])
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
    for c in sorted((c for c in candidatas if c.get("origen") == "gsc"),
                    key=lambda c: (-_nombra(_norm(c["keyword"])), -(c.get("impresiones") or 0))):
        kw = _norm(c["keyword"])
        sin = palabras_sin_respaldo(kw, texto_ficha, tipos)
        imp = c.get("impresiones") or 0
        if not re.fullmatch(r"[a-z0-9' &-]+", (c["keyword"] or "").lower()):
            motivo = "tiene símbolos que no son de una búsqueda escrita"
        elif imp < MIN_IMPRESIONES or (not _nombra(kw) and imp < MIN_IMPRESIONES_GENERICA):
            motivo = "pocas impresiones"
        elif len(kw.split()) < len(nombre_w) and nombre_w[:len(kw.split())] == kw.split():
            motivo = "es el nombre recortado"
        elif kw in h1n or kw in (nombre_n, modelo_n):
            motivo = "ya lo dice el H1 o es el nombre tal cual"
        elif kw == marca_n:
            motivo = "es solo la marca"
        elif sin:
            motivo = "la ficha no dice " + ", ".join(f"'{w}'" for w in sin)
        elif len([e for e in elegidas if e["origen"] == "gsc"]) >= max_gsc:
            motivo = ("ya hay una de Search Console y las opciones de la ficha"
                      if max_gsc == 1 else "ya hay dos de Search Console")
        elif _agregar(c, f"ya aparece en Google ({c.get('impresiones')} impresiones)"):
            continue
        else:
            motivo = "repite otra elegida"
        descartadas.append({"keyword": c["keyword"], "motivo": motivo})

    # 2) una por cada opción de la parte principal (Rock: mármol y madera)
    for c in opciones:
        _agregar(c, f"opción de la ficha ({c.get('volumen')}/mes)")

    # 3) marca + tipo, con volumen
    if marca_n:
        for c in sorted((c for c in candidatas if c.get("origen") == "generica"
                         and _norm(c["keyword"]).startswith(marca_n + " ")),
                        key=lambda c: -(c.get("volumen") or 0)):
            resto = set(_norm(c["keyword"])[len(marca_n):].split())
            if (c.get("volumen") or 0) >= MIN_VOL_MARCA and resto & {_clave(t) for t in tipos} | resto & tipos \
                    and _norm(c["keyword"]) not in h1n:
                if _agregar(c, f"marca + tipo ({c.get('volumen')}/mes)"):
                    break

    # (sin genéricas por material: «leather table», «marble table» fallaban; Alex,
    # 17-nov: lo que funciona es Search Console + marca y tipo)
    elegidas_k = {e["keyword"] for e in elegidas}
    descartadas += [{"keyword": c["keyword"], "motivo": "no cumple las reglas del SEO"}
                    for c in candidatas if c["keyword"] not in elegidas_k
                    and c["keyword"] not in {d["keyword"] for d in descartadas}]
    return {"elegidas": elegidas, "descartadas": descartadas}
