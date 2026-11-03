# -*- coding: utf-8 -*-
"""Paso ② de la pizarra: cuando GSC no alcanza para 3 keywords, mirar a la
competencia que vende EL MISMO producto y rankea mejor que nosotros.

    "{Nombre} {Marca}"  → DataForSEO SERP (no se scrapea Google)
      → las 3 primeras páginas de OTROS sitios por encima de cassoni
      → se leen sus H1, H2 y texto (respetando robots.txt)
      → frases de 2-3 palabras que se repiten en ≥2 competidores,
        que son de este producto y que NO están en nuestra ficha
      → se validan con volumen de DataForSEO en el orquestador

Al LLM nunca le llega texto de la competencia: solo las keywords. Así no copia
(contenido duplicado y derechos de autor).
"""
from __future__ import annotations

import logging
import re
import unicodedata
from html.parser import HTMLParser
from typing import Callable, Iterable, Optional
from urllib import robotparser
from urllib.parse import urlsplit

from .checklist import kw_exacta_en, strip_html

log = logging.getLogger("cassoni.competidores")

USER_AGENT = "CassoniSEOBot/1.0 (+https://cassoni.com)"
MAX_BYTES = 2_000_000
# no son fichas de producto de un competidor
DOMINIOS_IGNORADOS = ("youtube.", "pinterest.", "wikipedia.", "reddit.", "instagram.",
                      "facebook.", "tiktok.", "x.com", "twitter.", "linkedin.",
                      "houzz.com/photos", "google.")
_STOP = {
    "the", "and", "for", "with", "from", "that", "this", "into", "your", "our", "you",
    "are", "has", "have", "its", "all", "any", "can", "will", "more", "most", "free",
    "shipping", "delivery", "sale", "shop", "buy", "price", "prices", "cart", "add",
    "reviews", "review", "stock", "order", "orders", "returns", "account", "sign",
    "login", "menu", "search", "home", "contact", "about", "policy", "privacy",
    "cookies", "newsletter", "subscribe", "email", "share", "wishlist", "compare",
    "de", "la", "el", "los", "las", "con", "para", "por", "que", "una", "del", "en", "y",
}
_PALABRA = re.compile(r"[a-z][a-z0-9'-]*")


class _Lector(HTMLParser):
    """Saca title, H1, H2 y el texto de párrafos/listas; ignora script/nav/footer."""
    _OMITIR = {"script", "style", "noscript", "nav", "footer", "header", "form", "svg"}
    _CAPTURA = {"title", "h1", "h2", "h3", "p", "li", "td"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.omitir = 0
        self.pila: list[str] = []
        self.partes: dict[str, list[str]] = {"title": [], "h1": [], "h2": [], "texto": []}

    def handle_starttag(self, tag, attrs):
        if tag in self._OMITIR:
            self.omitir += 1
        elif tag in self._CAPTURA:
            self.pila.append(tag)

    def handle_endtag(self, tag):
        if tag in self._OMITIR and self.omitir:
            self.omitir -= 1
        elif self.pila and self.pila[-1] == tag:
            self.pila.pop()

    def handle_data(self, data):
        if self.omitir or not self.pila or not data.strip():
            return
        tag = self.pila[-1]
        clave = {"h3": "h2", "p": "texto", "li": "texto", "td": "texto"}.get(tag, tag)
        self.partes[clave].append(data.strip())


def leer_html(html: str) -> dict:
    """{title, h1: [..], h2: [..], texto} de una página."""
    p = _Lector()
    try:
        p.feed(html or "")
    except Exception:          # HTML roto: lo que se haya leído hasta ahí
        pass
    return {"title": " ".join(p.partes["title"]), "h1": p.partes["h1"],
            "h2": p.partes["h2"], "texto": " ".join(p.partes["texto"])}


def _plano(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return s.encode("ascii", "ignore").decode()


def ngramas(texto: str, n_min: int = 2, n_max: int = 3) -> set[str]:
    """Frases de 2-3 palabras sin stopwords en los bordes ni números sueltos."""
    palabras = _PALABRA.findall(_plano(texto))
    out = set()
    for n in range(n_min, n_max + 1):
        for i in range(len(palabras) - n + 1):
            g = palabras[i:i + n]
            if g[0] in _STOP or g[-1] in _STOP or any(len(w) < 3 for w in (g[0], g[-1])):
                continue
            out.add(" ".join(g))
    return out


def _dominio_propio(url: str, propios: Iterable[str]) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in propios)


def elegir_competidores(serp: list[dict], propios: Iterable[str], n: int = 3) -> list[dict]:
    """Las primeras `n` páginas de otros sitios que rankean POR ENCIMA nuestro
    (o las primeras `n`, si no aparecemos en el top)."""
    propios = [d.lower() for d in propios]
    nuestro = next((r.get("rank") for r in serp if _dominio_propio(r.get("url", ""), propios)),
                   None)
    out = []
    for r in serp:
        url = r.get("url", "")
        if not url or _dominio_propio(url, propios):
            continue
        if any(d in url for d in DOMINIOS_IGNORADOS):
            continue
        if nuestro is not None and (r.get("rank") or 0) >= nuestro:
            break
        out.append(r)
        if len(out) >= n:
            break
    return out


def candidatas_de_competidores(paginas: list[dict], *, descripcion_propia: str,
                               texto_producto: str, marcas_ajenas: Iterable[str] = (),
                               min_paginas: int = 2) -> list[dict]:
    """Frases que aparecen en ≥ `min_paginas` competidores, de este producto y que
    no están en nuestra ficha. Ordenadas por cuántos competidores la usan y si
    aparece en un título/H1/H2 (más señal que en el cuerpo)."""
    producto = set(_PALABRA.findall(_plano(texto_producto)))
    ajenas = {w for m in marcas_ajenas for w in _PALABRA.findall(_plano(m))}
    nuestro = strip_html(descripcion_propia)
    conteo: dict[str, int] = {}
    en_titulos: dict[str, int] = {}
    for p in paginas:
        titulos = " | ".join([p.get("title", ""), *p.get("h1", []), *p.get("h2", [])])
        g_tit = ngramas(titulos)
        g_all = g_tit | ngramas(p.get("texto", ""))
        for g in g_all:
            conteo[g] = conteo.get(g, 0) + 1
        for g in g_tit:
            en_titulos[g] = en_titulos.get(g, 0) + 1
    out = []
    for g, c in conteo.items():
        if c < min_paginas:
            continue
        palabras = set(g.split())
        if not (palabras & producto):           # tiene que ser de ESTE producto
            continue
        if palabras & ajenas:                    # nombres de otras tiendas/marcas
            continue
        if kw_exacta_en(nuestro, g):
            continue
        out.append({"keyword": g, "competidores": c, "en_titulos": en_titulos.get(g, 0),
                    "origen": "competidor"})
    out.sort(key=lambda r: (r["competidores"], r["en_titulos"], len(r["keyword"])),
             reverse=True)
    return out


class Competidores:
    """Orquesta SERP + lectura de páginas. `http_get(url) -> str` es inyectable."""

    def __init__(self, fetcher, *, propios: Iterable[str],
                 http_get: Optional[Callable[[str], str]] = None,
                 robots: Optional[Callable[[str], bool]] = None):
        self.fetcher = fetcher
        self.propios = list(propios)
        self.http_get = http_get or _http_get
        self.robots = robots or _permitido_por_robots

    def buscar(self, consulta: str, n: int = 3) -> list[dict]:
        """[{url, domain, rank, title, h1, h2, texto}] de hasta `n` competidores."""
        serp = self.fetcher.serp_organico(consulta) if self.fetcher else []
        paginas = []
        for r in elegir_competidores(serp, self.propios, n=n * 2):
            if len(paginas) >= n:
                break
            url = r["url"]
            try:
                if not self.robots(url):
                    log.info("robots.txt no permite %s", url)
                    continue
                datos = leer_html(self.http_get(url))
            except Exception as exc:
                log.warning("No se pudo leer %s (%s)", url, exc)
                continue
            datos["title"] = datos["title"] or r.get("title", "")
            paginas.append({**r, **datos})
        return paginas


def _http_get(url: str) -> str:
    import requests
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20, stream=True)
    r.raise_for_status()
    contenido = r.raw.read(MAX_BYTES, decode_content=True)
    return contenido.decode(r.encoding or "utf-8", errors="replace")


def _permitido_por_robots(url: str) -> bool:
    partes = urlsplit(url)
    rp = robotparser.RobotFileParser(f"{partes.scheme}://{partes.netloc}/robots.txt")
    try:
        rp.read()
    except Exception:
        return True            # sin robots.txt legible: se permite (convención)
    return rp.can_fetch(USER_AGENT, url)
