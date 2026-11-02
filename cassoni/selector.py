# -*- coding: utf-8 -*-
"""Selector de trabajo — decide QUÉ fichas se tocan, sin lista escrita a mano.

Puro, sin I/O: recibe las filas de GSC (páginas y consultas) y devuelve un lote
priorizado. La regla de negocio sale de la auditoría del 13-oct-2026:

  - Sólo fichas de producto (`/product/...`): las categorías y las páginas de marca
    concentran el 58,7% de las impresiones, pero el agente no las edita.
  - Se descarta el ruido: posición > 30 y cero clics no es una oportunidad, es cola.
  - La keyword que manda es la de mayor OPORTUNIDAD (demanda que se puede
    materializar o CTR que se puede levantar), no la de más volumen: la consulta
    con 5.000 impresiones en posición 2 no tiene nada que ganar.
  - El lote se ordena por (opportunity_score, impresiones de la página).
"""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Iterable, Optional
from urllib.parse import urlsplit

from .opportunities import annotate as annotate_opportunities

PRODUCTO_PATH = "/product/"
MIN_IMPRESSIONS = 50        # debajo de esto no hay demanda que justifique el trabajo
MAX_POS_SIN_CLICS = 30      # más allá de la página 3 y sin un solo clic: ruido


# palabras que no identifican un producto
_STOP = {
    "the", "and", "for", "with", "from", "that", "this", "into", "luxury", "design",
    "de", "la", "el", "los", "las", "con", "para", "por", "que", "una", "unos",
    "unas", "del", "al", "sus", "mas", "más", "como", "sobre", "cada", "entre",
    "desde", "hasta", "mueble", "muebles", "producto", "productos",
}
_TOKEN_RX = re.compile(r"[a-z0-9]+")


def _tokens(texto: str) -> set[str]:
    """Palabras significativas: >=4 letras, sin números ni códigos internos."""
    plano = unicodedata.normalize("NFKD", (texto or "").lower())
    plano = plano.encode("ascii", "ignore").decode()
    out = set()
    for w in _TOKEN_RX.findall(plano):
        if len(w) < 4 or w.isdigit() or w in _STOP:
            continue
        if len(w) > 4 and w.endswith("s"):
            w = w[:-1]          # 'sofas' y 'sofa' colisionan, igual que en checklist
        out.add(w)
    return out


def relevante(keyword: str, texto_producto: str) -> bool:
    """¿La consulta es de ESTE producto? Exige al menos una palabra significativa
    en común con el nombre, el slug o la categoría.

    Motivo (lote real del 2-nov): GSC devuelve consultas que rankean la página sin
    ser del producto —'liberator lounger' en una silla dining, 'geef foto' en un
    sofá—. Elegirlas por impresiones hace que el editor escriba con una keyword
    ajena, que el validador después rebota.
    """
    return bool(_tokens(keyword) & _tokens(texto_producto))


def es_producto(url: str) -> bool:
    """True si la URL es una ficha de producto (y no una categoría o un blog)."""
    path = urlsplit(url or "").path
    return path.startswith(PRODUCTO_PATH)


def filtrar_paginas(rows: Iterable[dict], *, min_impressions: int = MIN_IMPRESSIONS,
                    max_pos_sin_clics: int = MAX_POS_SIN_CLICS) -> list[dict]:
    """Fichas con demanda real, ordenadas por impresiones desc. No muta la entrada."""
    out = []
    for r in rows:
        url = r.get("url") or ""
        if not es_producto(url):
            continue
        impr = r.get("impressions") or 0
        clicks = r.get("clicks") or 0
        pos = r.get("position") or 0
        if impr < min_impressions:
            continue
        if pos > max_pos_sin_clics and clicks == 0:
            continue
        out.append({"url": url, "impressions": impr, "clicks": clicks,
                    "ctr": r.get("ctr") or 0.0, "position": pos})
    out.sort(key=lambda r: r["impressions"], reverse=True)
    return out


def elegir_keyword(queries: Iterable[dict], *, url: Optional[str] = None) -> Optional[dict]:
    """De las consultas de una ficha, la de mayor oportunidad. El volumen desempata.

    Con `url`, descarta antes las consultas que no son de ese producto.
    Devuelve la fila enriquecida (`opportunity`, `opportunity_score`) o None.
    """
    filas = [dict(q) for q in queries if q.get("keyword")]
    if url:
        filas = [q for q in filas if relevante(q["keyword"], url)]
    if not filas:
        return None
    anotadas = annotate_opportunities(filas)
    anotadas.sort(key=lambda r: (r["opportunity_score"], r.get("impressions") or 0,
                                 -(r.get("position") or 0)), reverse=True)
    return anotadas[0]


def priorizar(paginas: Iterable[dict], queries_por_url: dict[str, list[dict]], *,
              top_n: Optional[int] = None,
              min_impressions: int = MIN_IMPRESSIONS,
              max_pos_sin_clics: int = MAX_POS_SIN_CLICS) -> list[dict]:
    """Arma el lote: una entrada por ficha, con la consulta que define la oportunidad."""
    lote: list[dict] = []
    vistas: set[str] = set()
    for p in filtrar_paginas(paginas, min_impressions=min_impressions,
                             max_pos_sin_clics=max_pos_sin_clics):
        url = p["url"]
        if url in vistas:
            continue
        kw = elegir_keyword(queries_por_url.get(url, []), url=url)
        if kw is None:
            continue          # sin consultas no hay keyword: no se puede editar con kw
        vistas.add(url)
        lote.append({
            "url": url,
            "keyword": kw["keyword"],
            "opportunity": kw["opportunity"],
            "opportunity_score": kw["opportunity_score"],
            # agregados de la página
            "impressions": p["impressions"], "clicks": p["clicks"],
            "ctr": p["ctr"], "position": p["position"],
            # agregados de la consulta elegida
            "kw_impressions": kw.get("impressions") or 0,
            "kw_clicks": kw.get("clicks") or 0,
            "kw_ctr": kw.get("ctr") or 0.0,
            "kw_position": kw.get("position") or 0.0,
        })
    lote.sort(key=lambda c: (c["opportunity_score"], c["impressions"]), reverse=True)
    lote = lote[:top_n] if top_n else lote
    return lote


def lote_a_json(lote: list[dict], *, meta: Optional[dict] = None) -> str:
    """Serializa el lote para guardarlo como evidencia auditable."""
    payload = {"meta": dict(meta or {}), "fichas": lote}
    return json.dumps(payload, ensure_ascii=False, indent=2)
