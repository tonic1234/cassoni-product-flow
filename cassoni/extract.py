# -*- coding: utf-8 -*-
"""Extractor de URL → slug. Determina si la URL es producto, categoría o tag."""
from __future__ import annotations

from urllib.parse import urlparse
from typing import Optional

# Bases de rutas por idioma (es, en, pt, fr) que indican tipo de contenido.
# En WooCommerce el slug siempre es un solo segmento tras la base.
PRODUCT_BASES = {"product", "producto", "produit", "produto", "products"}
CATEGORY_BASES = {"product-category", "categoria-producto", "categorie-produit",
                  "categoria-produto", "categorias"}
TAG_BASES = {"product-tag", "etiqueta-producto", "etiqueta", "tag"}

KNOWN_BASES = PRODUCT_BASES | CATEGORY_BASES | TAG_BASES


class ExtractionError(Exception):
    """No se pudo determinar el tipo de la URL."""


def extract_slug(url: str) -> tuple[str, str]:
    """Devuelve (slug, tipo) donde tipo ∈ {product, category, tag, unknown}.

    Lanza ExtractionError si la URL no tiene un slug reconocible (p.ej. home).
    """
    path = urlparse(url).path.rstrip("/")
    segs = [s for s in path.split("/") if s and s != "index.html"]
    if not segs:
        raise ExtractionError(f"URL sin path: {url}")
    # buscar la primera base conocida para tomar el segmento siguiente
    for i, seg in enumerate(segs):
        lower = seg.lower()
        if lower in PRODUCT_BASES:
            return _take(segs, i, "product", url)
        if lower in CATEGORY_BASES:
            return _take(segs, i, "category", url)
        if lower in TAG_BASES:
            return _take(segs, i, "tag", url)
    # sin base explícita: asumir que el último segmento es el slug de la home
    # de producto (sitios con permalinks tipo /cas-cprn-pedro-sofa-01/)
    if len(segs) == 1:
        return segs[0], "unknown"
    raise ExtractionError(f"No se reconoce base de tipo en: {url}")


def _take(segs: list[str], base_idx: int, tipo: str, url: str) -> tuple[str, str]:
    if base_idx + 1 < len(segs):
        return segs[base_idx + 1], tipo
    raise ExtractionError(f"URL de {tipo} sin slug: {url}")


def is_product_url(url: str) -> bool:
    try:
        return extract_slug(url)[1] == "product"
    except ExtractionError:
        return False