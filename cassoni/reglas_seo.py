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

from .h1 import modelo_de, sin_codigos
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


def h1_por_datos(nombre: str, marca: str, tipo: str, vol_nombre: Optional[int],
                 rasgos: Iterable[tuple[str, int]], umbral: int = UMBRAL_NOMBRE) -> dict:
    """{'h1', 'regla', 'rasgo'}. `rasgos`: (material, volumen de '{material} {tipo}')
    solo con materiales que la ficha confirma."""
    por = f" by {marca}" if marca else ""
    base = re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", " ", sin_codigos(nombre or ""))).strip()
    base = re.split(r"\s[-–—]\s", base)[0].strip()
    if vol_nombre and vol_nombre >= umbral:
        return {"h1": f"{base}{por}", "regla": f"el nombre ya se busca ({vol_nombre}/mes)",
                "rasgo": ""}
    if not tipo:
        return {"h1": f"{base}{por}", "regla": "sin tipo de producto: nombre + marca",
                "rasgo": ""}
    modelo = modelo_de(nombre, marca) or base
    mejor = max(((m, v) for m, v in rasgos if v), key=lambda x: x[1], default=None)
    if mejor:
        return {"h1": f"{modelo} {_titulo(mejor[0])} {_titulo(tipo)}{por}",
                "regla": f"rasgo más buscado: '{mejor[0]} {tipo}' ({mejor[1]}/mes)",
                "rasgo": mejor[0]}
    return {"h1": f"{modelo} {_titulo(tipo)}{por}",
            "regla": "ningún rasgo con volumen: modelo + tipo", "rasgo": ""}


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
                    h1: str, rasgo: str, texto_ficha: str) -> dict:
    """{'elegidas': [...], 'descartadas': [{keyword, motivo}]} sin LLM."""
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
        elif len([e for e in elegidas if e["origen"] == "gsc"]) >= 2:
            motivo = "ya hay dos de Search Console"
        elif _agregar(c, f"ya aparece en Google ({c.get('impresiones')} impresiones)"):
            continue
        else:
            motivo = "repite otra elegida"
        descartadas.append({"keyword": c["keyword"], "motivo": motivo})

    # 2) marca + tipo, con volumen
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
