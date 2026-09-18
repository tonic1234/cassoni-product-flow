# -*- coding: utf-8 -*-
"""Checklist duro del agente SEO — reglas verificables EN CÓDIGO (sin LLM).

La spec (docs/REGLA-SEO-FICHAS.md + cassoni/reglas.py) tiene dos naturalezas:
- reglas creativas (redacción, tono) → LLM (editor/validador);
- reglas MECÁNICAS (longitudes, conteos, repeticiones, anti-canibalización) → acá,
  deterministas y testeables, para que el gate no dependa de la suerte del prompt.

check_reglas(editado) -> list[str]  (issues; vacío = pasa)
filtrar_canibalizacion(candidatas, principals_ya_usadas, categorias, blogs_guia) -> dict
"""
from __future__ import annotations

import re
from typing import Iterable

from . import reglas

# --- utilidades de texto ---
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(html: str) -> str:
    """Saca tags HTML/entidades; deja el texto plano."""
    text = _TAG_RE.sub(" ", html or "")
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
    return _WS_RE.sub(" ", text).strip()


def word_count(html: str) -> int:
    """Cantidad de palabras del texto (sin HTML)."""
    return len(strip_html(html).split())


def h2_count(html: str) -> int:
    """Cantidad de H2 en el HTML (case-insensitive)."""
    return len(re.findall(r"<h2\b[^>]*>", html or "", flags=re.I))


def norm(s: str) -> str:
    """Normalización para comparar keywords: minúsculas + espacios colapsados."""
    return _WS_RE.sub(" ", (s or "").strip().lower())


def kw_exacta_en(texto: str, kw: str) -> bool:
    """True si `kw` está en `texto` EXACTA (palabra completa, case/espacios
    normalizados). 'sofá' NO matchea dentro de 'sofás'."""
    t, k = norm(texto), norm(kw)
    if not k:
        return False
    return re.search(r"(?<!\w)" + re.escape(k) + r"(?!\w)", t) is not None


def usos_de(kw: str, texto: str) -> int:
    """Cuántas veces aparece `kw` exacta (palabra completa) en `texto`."""
    t, k = norm(texto), norm(kw)
    if not k:
        return 0
    return len(re.findall(r"(?<!\w)" + re.escape(k) + r"(?!\w)", t))


# --- reglas mecánicas ---
def check_reglas(editado: dict) -> list[str]:
    """Devuelve la lista de issues (vacía si cumple TODO). `editado` es el output
    estructurado del editor (alcance: SOLO H1 + descripción larga):
    {h1, keyword_principal, description, secondary_keywords:[{keyword,why}],
    discarded:[...]}."""
    issues: list[str] = []
    h1 = (editado.get("h1") or "").strip()
    principal = norm(editado.get("keyword_principal") or "")
    desc = editado.get("description") or ""
    secs = editado.get("secondary_keywords") or []

    # H1: máx 60 caracteres
    if len(h1) > reglas.H1_MAX_CHARS:
        issues.append(f"H1 supera los {reglas.H1_MAX_CHARS} caracteres "
                      f"(tiene {len(h1)})")

    # keyword principal EXACTA en el H1
    if principal:
        if not kw_exacta_en(h1, principal):
            issues.append("La keyword principal no está EXACTA en el H1")
    else:
        issues.append("Falta la keyword principal (keyword_principal)")

    # descripción larga: 150-300 palabras
    wc = word_count(desc)
    if wc < reglas.LARGA_MIN_WORDS:
        issues.append(f"La descripción larga no llega a las {reglas.LARGA_MIN_WORDS} "
                      f"palabras (tiene {wc})")
    if wc > reglas.LARGA_MAX_WORDS:
        issues.append(f"La descripción larga supera las {reglas.LARGA_MAX_WORDS} "
                      f"palabras (tiene {wc})")

    # descripción larga: máx 2 H2
    h2c = h2_count(desc)
    if h2c > reglas.MAX_H2:
        issues.append(f"La descripción larga tiene más de {reglas.MAX_H2} H2 "
                      f"(tiene {h2c})")

    # secundarias: 2-3, cada una con su porqué y máx 2 usos
    if len(secs) < reglas.SEC_MIN:
        issues.append(f"Se necesitan {reglas.SEC_MIN} a {reglas.SEC_MAX} keywords "
                      f"secundarias (hay {len(secs)})")
    if len(secs) > reglas.SEC_MAX:
        issues.append(f"Máximo {reglas.SEC_MAX} keywords secundarias (hay {len(secs)})")
    plain_desc = strip_html(desc)
    for s in secs:
        kw = (s.get("keyword") or "").strip()
        why = (s.get("why") or "").strip()
        if not kw:
            issues.append("Hay una secundaria sin keyword")
        if not why:
            issues.append(f"La secundaria '{kw}' no explica por qué es específica")
        usos = usos_de(kw, plain_desc) if kw else 0
        if usos > reglas.SEC_MAX_USOS:
            issues.append(f"La secundaria '{kw}' aparece más de {reglas.SEC_MAX_USOS} "
                          f"veces (aparece {usos})")

    return issues


# --- filtro anti-canibalización (determinista) ---
_BLOG_INTENT = ("como elegir", "cómo elegir", "guía de", "guia de", "top ",
                "mejores", "qué es", "que es", "mejor ")


def _es_consulta_de_categoria(norm_cand: str, cats: set[str]) -> bool:
    """True si la candidata compite con la página de categoría: es la categoría
    exacta o la categoría + pocas palabras genéricas (sin señales de producto)."""
    for c in cats:
        nc = norm(c)
        if norm_cand == nc:
            return True
        if norm_cand.startswith(nc + " "):
            extra = len(norm_cand[len(nc) + 1:].split())
            if extra <= 2:  # "sofas de lujo" sí; "sofas de la coleccion aria" no
                return True
    return False


def filtrar_canibalizacion(
        candidatas: Iterable[str],
        principals_ya_usadas: Iterable[str] = (),
        categorias_como_pagina: Iterable[str] = (),
        blogs_guia: Iterable[str] = ()) -> dict:
    """Aplica el filtro anti-canibalización del documento.

    Devuelve:
      {"aceptadas": [{"keyword": k}, ...],
       "descartadas": [{"keyword": k, "motivo": str, "pertenece_a": str}, ...]}
    """
    principals = {norm(p) for p in principals_ya_usadas}
    cats = {norm(c) for c in categorias_como_pagina}
    blogs = {norm(b) for b in blogs_guia}

    aceptadas, descartadas = [], []
    for cand in candidatas:
        nc = norm(cand)
        if not nc:
            continue
        if nc in principals:
            descartadas.append({
                "keyword": cand,
                "motivo": "ya es la keyword principal de otra ficha",
                "pertenece_a": "otra ficha (keyword principal ya utilizada)",
            })
        elif _es_consulta_de_categoria(nc, cats):
            descartadas.append({
                "keyword": cand,
                "motivo": "compite con la página de categoría",
                "pertenece_a": "página de categoría",
            })
        elif nc in blogs or any(p in nc for p in _BLOG_INTENT):
            descartadas.append({
                "keyword": cand,
                "motivo": "responde mejor a un blog o guía de compra que a una ficha",
                "pertenece_a": "blog o guía de compra",
            })
        else:
            aceptadas.append({"keyword": cand})

    return {"aceptadas": aceptadas, "descartadas": descartadas}