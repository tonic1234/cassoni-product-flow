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
import unicodedata
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
_SENT_RX = re.compile(r"(?<=[.!?])\s+")   # separador de oraciones
_BLOQUE_RX = re.compile(r"</(?:p|h1|h2|h3|li|div|section|blockquote|tr)>", re.I)
# palabras funcionales que no cuentan para la regla anti-repetición
_FUNCIONALES = {
    "de", "la", "el", "los", "las", "con", "para", "por", "que", "un", "una",
    "unos", "unas", "y", "en", "del", "al", "su", "sus", "se", "no", "más",
    "mas", "the", "and", "for", "with", "its", "this", "that", "are", "can",
    "into", "from", "has", "have", "was", "were", "also", "como", "sobre",
    "cada", "entre", "desde", "hasta", "them", "their", "they", "there",
}


def oraciones(html: str) -> list[str]:
    """Oraciones del texto (sin HTML), normalizadas y no vacías. No cruza
    fronteras de bloque: un texto de H2 no se pega a la oración del párrafo."""
    out = []
    for bloque in _BLOQUE_RX.split(html or ""):
        texto = strip_html(bloque)
        for s in _SENT_RX.split(texto):
            n = norm(s)
            if len(n) > 2:
                out.append(n)
    return out


def conservacion(original: str, editado: str) -> float:
    """Fracción de oraciones del ORIGINAL que siguen intactas en la edición.
    1.0 = nada se tocó; 0.0 = reescritura total. Es la medición de la regla
    'editar sobre el texto actual, nunca reescribir' (requisito Antonio 18-sep)."""
    orig = oraciones(original)
    if not orig:
        return 1.0
    edit_norm = set(oraciones(editado))
    conservadas = [o for o in orig if o in edit_norm]
    return len(conservadas) / len(orig)


def _clave_palabras(kw: str) -> set[str]:
    """Huella de una keyword: palabras significativas, sin acentos y sin plural
    final ('sofa', 'sofas' y 'sofá' colisionan entre sí)."""
    out: set[str] = set()
    for w in strip_html(kw).lower().split():
        w = unicodedata.normalize("NFKD", w).encode("ascii", "ignore").decode()
        w = w.strip(".,;:()[]¡!¿?\"'")
        if len(w) < 4 or w in _FUNCIONALES:
            continue
        if len(w) > 4 and w.endswith("s"):
            w = w[:-1]
        out.add(w)
    return out


def seleccionar_diversas(candidatas: list[dict], max_sec: int = 3) -> dict:
    """Elige hasta `max_sec` keywords que NO compartan palabras entre sí
    (regla de Antonio 18-sep: de todas las que dicen 'sofa' solo se usa UNA),
    priorizando volumen. Devuelve {elegidas, omitidas, faltantes}.

    `faltantes` > 0 = hay que SALIR A BUSCAR más candidatas con palabras
    distintas para completar las secundarias (expansor)."""
    ordenadas = sorted(candidatas,
                       key=lambda c: (c.get("opportunity_score") or 0,
                                      c.get("volume") or 0), reverse=True)
    elegidas: list[dict] = []
    omitidas: list[dict] = []
    usadas: set[str] = set()
    for c in ordenadas:
        kw = c.get("keyword", "")
        claves = _clave_palabras(kw)
        choque = claves & usadas
        if choque:
            otra = next((e["keyword"] for e in elegidas
                         if claves & _clave_palabras(e["keyword"])), "")
            omitidas.append({
                "keyword": kw, "choca_con": otra,
                "motivo": (f"comparte la palabra '{sorted(choque)[0]}' con '{otra}' "
                           f"(solo se usa una por palabra)")})
            continue
        if len(elegidas) < max_sec:
            elegidas.append(c)
            usadas |= claves
        else:
            omitidas.append({"keyword": kw, "choca_con": "",
                             "motivo": f"ya hay {max_sec} secundarias elegidas"})
    return {"elegidas": elegidas, "omitidas": omitidas,
            "faltantes": max(0, max_sec - len(elegidas))}


def palabra_dominante(html: str, max_apariciones: int | None = None) -> str:
    """Devuelve la palabra no funcional más repetida del texto, o '' si ninguna
    pasa el límite. Regla anti 'sofa sofa sofa' (Antonio 18-sep)."""
    limite = max_apariciones if max_apariciones is not None else reglas.REPETICION_MAX_PALABRA
    frec: dict[str, int] = {}
    for w in strip_html(html).lower().split():
        w = w.strip(".,;:()[]¡!¿?\"'")
        if len(w) < 4 or w in _FUNCIONALES:
            continue
        frec[w] = frec.get(w, 0) + 1
    if not frec:
        return ""
    top, n = max(frec.items(), key=lambda kv: kv[1])
    return top if n > limite else ""


def check_reglas(editado: dict, original_description: str = "") -> list[str]:
    """Devuelve la lista de issues (vacía si cumple TODO). `editado` es el output
    estructurado del editor (alcance: SOLO H1 + descripción larga):
    {h1, keyword_principal, description, secondary_keywords:[{keyword,why}],
    discarded:[...]}. `original_description`: si se pasa, también se verifica
    que la edición conserve lo esencial del texto original (no reescribir)."""
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

    # conservación del texto original (nunca reescribir desde cero)
    if original_description:
        ratio = conservacion(original_description, desc)
        if ratio < reglas.CONSERVACION_MIN:
            issues.append(
                f"La descripción larga fue reescrita desde cero: conserva solo "
                f"{ratio:.0%} de las oraciones del original "
                f"(mínimo {reglas.CONSERVACION_MIN:.0%})")

    # anti-repetición: una misma palabra no puede dominar el texto
    dominante = palabra_dominante(desc)
    if dominante:
        issues.append(
            f"La palabra '{dominante}' se repite demasiado en la descripción larga "
            f"(más de {reglas.REPETICION_MAX_PALABRA} veces, 'sofa sofa sofa' está "
            f"prohibido)")

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