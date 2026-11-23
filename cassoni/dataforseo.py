# -*- coding: utf-8 -*-
"""Cliente DataForSEO — búsqueda de volumen con técnica de BULKING.

- Deduplica keywords a nivel global PRESERVANDO el origen (lista de URLs),
  para poder re-mapear el volumen a cada producto tras el bulk.
- Envía requests de hasta `bulk_size` (1.000) keywords, respetando el rate
  limit (máx requests/min) y con retry/backoff ante result=null intermitente.
- La API devuelve volúmenes en el MISMO orden del array de entrada → mapeo
  directo (indice) sin hash.
- `serp_organico` trae los resultados orgánicos de Google para una consulta
  (paso ② de la pizarra: quién rankea mejor que nosotros con el mismo producto),
  sin scrapear Google.
- `costo_usd` acumula el costo real que informa la API en cada respuesta.
"""
from __future__ import annotations

import base64
import json
import logging
import threading
import time
from typing import Any, Callable, Optional

import requests
from urllib.parse import urlsplit

from .config import Config

log = logging.getLogger("cassoni.dataforseo")
# símbolos que Google Ads no acepta en una keyword (documentación de DataForSEO)
_SIMBOLOS_PROHIBIDOS = set(",!@%^()={};~`<>?\\|*")


# costo por pedido medido el 3-nov-2026 (respuesta 'cost' de la API)
COSTO_VOLUMEN_USD = 0.09        # hasta 1.000 keywords por pedido
COSTO_SERP_USD = 0.002          # una búsqueda orgánica
COSTO_RANKED_USD = 0.03         # estimado, por página de competidor
COSTO_SUGERENCIAS_USD = 0.016  # US$ 0,012 + 0,00012 por resultado (30): precio de la cuenta, 23-nov
COSTO_IDEAS_USD = 0.03          # estimado (Labs cobra por pedido + por resultado):
                                # se reemplaza por el real con la primera corrida


def _sin_saldo(exc: Exception) -> str:
    """Problema de CUENTA (no se arregla reintentando): 401 credenciales, 402 sin
    saldo, 403 cuenta sin verificar. Devuelve el motivo, o '' si es otro error.
    Prueba real 3-nov: el 402 y el 403 se tragaban en silencio."""
    resp = getattr(exc, "response", None)
    codigo = getattr(resp, "status_code", None)
    if codigo not in (401, 402, 403):
        return ""
    try:
        detalle = resp.json().get("status_message") or ""
    except Exception:
        detalle = ""
    base = {401: "credenciales inválidas", 402: "SIN SALDO",
            403: "cuenta sin verificar o sin permiso"}[codigo]
    return f"{base} ({codigo}) {detalle}".strip()


def _tarea_bloqueada(tarea: dict) -> str:
    """Códigos de tarea 401xx/402xx/403xx: la cuenta no puede operar (pausada,
    sin saldo, sin verificar). Vienen con HTTP 200, dentro de la respuesta.
    Prueba real 3-nov: 40201 'temporarily paused access' devolvía 0 resultados
    sin ningún aviso."""
    codigo = tarea.get("status_code")
    if "internal" in str(tarea.get("status_message") or "").lower():
        return ""      # prueba real 4-nov: 40101 'Internal SE Server Error' es pasajero
    if isinstance(codigo, int) and 40100 <= codigo < 40400:
        return f"cuenta bloqueada ({codigo}) {tarea.get('status_message') or ''}".strip()
    return ""


def _sin_seguimiento(url: str) -> str:
    """Saca el `srsltid` que Google agrega a los resultados de tiendas: con él,
    DataForSEO Labs no reconoce la página."""
    if "srsltid=" not in url:
        return url
    base, _, query = url.partition("?")
    resto = [q for q in query.split("&") if q and not q.startswith("srsltid=")]
    return base + ("?" + "&".join(resto) if resto else "")


def _desde_breadcrumb(url: str, breadcrumb) -> dict:
    """Google (nov-2026) devuelve muchos resultados como `google.com/goto?url=...`:
    la URL real va cifrada y no se puede seguir. El breadcrumb sí trae el dominio
    real y un tramo de la dirección ("https://x.com › prodotti › cruise-alu-..."),
    con eso se reconstruye {url, domain, patron}. Si el tramo no es la ficha
    (una categoría con espacios, o nada), se marca como no usable."""
    host = (urlsplit(url).hostname or "").lower()
    if not (host == "google.com" or host.endswith(".google.com")) or "/goto" not in url:
        return {}
    partes = [p.strip() for p in str(breadcrumb or "").split("\u203a")]
    dominio = (urlsplit(partes[0]).hostname or "").lower() if partes else ""
    if not dominio:
        return {"url": "", "domain": "", "patron": ""}
    tramo = ""
    for seg in reversed(partes[1:]):
        seg = seg.rstrip(".\u2026").rstrip("-").strip()
        if seg and seg not in ("...", "\u2026") and " " not in seg and "-" in seg:
            tramo = seg
            break
    if not tramo:
        return {"url": "", "domain": dominio, "patron": ""}
    return {"url": f"https://{dominio}/{tramo}", "domain": dominio,
            "patron": f"%{tramo}%"}


class DataForSEOFetcher:
    """Enfoque limpio de la API real (validado 28-ago)."""

    SEARCH_VOLUME_URL = "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live"
    SERP_URL = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
    IDEAS_URL = "https://api.dataforseo.com/v3/dataforseo_labs/google/keyword_ideas/live"
    RANKED_URL = "https://api.dataforseo.com/v3/dataforseo_labs/google/ranked_keywords/live"
    SUGERENCIAS_URL = "https://api.dataforseo.com/v3/dataforseo_labs/google/keyword_suggestions/live"

    def __init__(self, config: Config, session: Optional[requests.Session] = None,
                 _post: Optional[Callable] = None):
        self.cfg = config
        self._session = session or requests.Session()
        self._post = _post  # inyectable para tests
        self._lock = threading.Lock()
        self._last_req = 0.0
        self.costo_usd = 0.0
        self.sin_saldo = ""                # motivo si la cuenta no puede operar
        self.sin_presupuesto = False

    def _alcanza(self, costo: float) -> bool:
        """Tope de gasto por corrida (CASSONI_DFS_PRESUPUESTO_USD; 0 = sin tope).
        Si el próximo pedido lo pasaría, no se hace y se sigue sin ese dato."""
        tope = getattr(self.cfg, "dfs_presupuesto_usd", 0) or 0
        if tope and self.costo_usd + costo > tope + 1e-9:
            if not self.sin_presupuesto:
                log.error("DataForSEO: se alcanzó el presupuesto de la corrida "
                          "(US$ %.3f de %.3f). No se hacen más pedidos.", self.costo_usd, tope)
            self.sin_presupuesto = True
            return False
        return True

    def saldo(self) -> Optional[dict]:
        """{login, saldo_usd} de la cuenta. Gratis (appendix/user_data)."""
        try:
            auth = (self.cfg.dfs_login, self.cfg.dfs_password)
            r = self._session.get("https://api.dataforseo.com/v3/appendix/user_data",
                                  auth=auth, timeout=30)
            res = r.json()["tasks"][0]["result"][0]
            return {"login": res.get("login"),
                    "saldo_usd": (res.get("money") or {}).get("balance")}
        except Exception:
            return None

    def _throttle(self):
        """Máx `dfs_max_requests_min` requests por minuto."""
        if self.cfg.dfs_max_requests_min <= 0:
            return
        interval = 60.0 / self.cfg.dfs_max_requests_min
        with self._lock:
            wait = self._last_req + interval - time.time()
            self._last_req = max(time.time(), self._last_req + interval)
        if wait > 0:
            time.sleep(wait)

    @staticmethod
    def keyword_valida(kw: str) -> bool:
        """Límites de Google Ads: ≤ 80 caracteres, ≤ 10 palabras y sin ciertos
        símbolos. Una sola keyword inválida hace fallar la TAREA entera (todo el
        lote de 1.000), así que las inválidas no se mandan."""
        kw = (kw or "").strip()
        return (0 < len(kw) <= 80 and len(kw.split()) <= 10
                and not any(c in _SIMBOLOS_PROHIBIDOS for c in kw))

    @staticmethod
    def _fila(row: dict) -> dict:
        """Una fila de la respuesta. Formato real de keywords_data/google_ads
        (medido el 3-nov-2026): campos en la raíz. Se acepta también el anidado
        `keyword_data.google_ads` de los endpoints de Labs."""
        g = row
        if "search_volume" not in row:
            g = ((row.get("keyword_data") or {}).get("google_ads") or {})
        idx = g.get("competition_index")
        comp = g.get("competition")
        if not isinstance(comp, (int, float)):
            comp = idx / 100 if isinstance(idx, (int, float)) else None
        return {"volume": g.get("search_volume"), "competition": comp,
                "cpc": g.get("cpc"), "competition_index": idx,
                "monthly": g.get("monthly_searches"), "spell": row.get("spell")}

    def search_volume(self, keywords: list[str],
                      location_code: Optional[int] = None) -> list[Optional[dict]]:
        """Volumen para una tanda de keywords. Devuelve, en el MISMO orden,
        el resultado de cada keyword (dict) o None si no se pudo. El cruce es
        por keyword, no por posición: la API no garantiza el orden."""
        location_code = location_code or self.cfg.dfs_location_code
        results: list[Optional[dict]] = [None] * len(keywords)
        posiciones: dict[str, list[int]] = {}
        validas: list[str] = []
        for i, kw in enumerate(keywords):
            if not self.keyword_valida(kw):
                continue
            clave = " ".join(kw.lower().split())
            if clave not in posiciones:
                validas.append(kw)
            posiciones.setdefault(clave, []).append(i)
        for chunk_start in range(0, len(validas), self.cfg.dfs_bulk_size):
            chunk = validas[chunk_start: chunk_start + self.cfg.dfs_bulk_size]
            if not self._alcanza(COSTO_VOLUMEN_USD):
                return results
            for attempt in range(self.cfg.dfs_retries + 1):
                self._throttle()
                try:
                    payload = [{
                        "location_code": location_code,
                        "language_code": self.cfg.dfs_language_code,
                        "keywords": chunk,
                        "search_partners": False,
                    }]
                    data = self._request(payload)
                except requests.RequestException as exc:
                    motivo = _sin_saldo(exc)
                    if motivo:
                        self.sin_saldo = motivo
                        log.error("DataForSEO: %s. Se sigue sin volumen.", motivo)
                        return results
                    if attempt >= self.cfg.dfs_retries:
                        break
                    time.sleep(2 ** attempt)
                    continue
                if data is None or data.get("status_code") != 20000:
                    if attempt >= self.cfg.dfs_retries:
                        break
                    time.sleep(2 ** attempt)
                    continue
                self.costo_usd += float(data.get("cost") or 0)
                tarea = (data.get("tasks") or [{}])[0]
                if _tarea_bloqueada(tarea):
                    self.sin_saldo = _tarea_bloqueada(tarea)
                    log.error("DataForSEO: %s", self.sin_saldo)
                    return results
                if tarea.get("status_code") not in (None, 20000):
                    log.warning("DataForSEO rechazó la tarea: %s %s",
                                tarea.get("status_code"), tarea.get("status_message"))
                    break
                rows = tarea.get("result", []) or []
                sin_clave = all(not (r or {}).get("keyword") for r in rows)
                for i, row in enumerate(rows):
                    row = row or {}
                    # formato viejo sin keyword en la fila: se cae al orden
                    kw = row.get("keyword") if not sin_clave else (
                        chunk[i] if i < len(chunk) else None)
                    for pos in posiciones.get(" ".join((kw or "").lower().split()), []):
                        results[pos] = self._fila(row)
                break
        return results

    def _tarea(self, payload: list[dict], url: str, costo: float, para: str) -> Optional[dict]:
        """Hace un pedido 'live' y devuelve el primer `result` de la tarea, o None.
        Corta sin reintentar si la cuenta no puede operar (saldo, verificación,
        pausa) o si el pedido pasaría el presupuesto de la corrida."""
        if not self._alcanza(costo):
            return None
        for attempt in range(self.cfg.dfs_retries + 1):
            self._throttle()
            try:
                data = self._request(payload, url=url)
            except requests.RequestException as exc:
                motivo = _sin_saldo(exc)
                if motivo:
                    self.sin_saldo = motivo
                    log.error("DataForSEO: %s. Sin %s.", motivo, para)
                    return None
                data = None
            tarea = ((data or {}).get("tasks") or [{}])[0]
            if _tarea_bloqueada(tarea):
                self.sin_saldo = _tarea_bloqueada(tarea)
                log.error("DataForSEO: %s. Sin %s.", self.sin_saldo, para)
                return None
            if data and data.get("status_code") == 20000 and tarea.get("status_code") in (None, 20000):
                self.costo_usd += float(data.get("cost") or 0)
                return (tarea.get("result") or [{}])[0] or {}
            if "internal" in str(tarea.get("status_message") or "").lower():
                data = None                  # error pasajero de DataForSEO: se reintenta
            elif tarea.get("status_code") not in (None, 20000):
                log.warning("DataForSEO rechazó el pedido de %s: %s %s", para,
                            tarea.get("status_code"), tarea.get("status_message"))
                return None
            if attempt < self.cfg.dfs_retries:
                time.sleep(2 ** attempt)
        return None

    def serp_organico(self, keyword: str, depth: int = 10) -> list[dict]:
        """Resultados orgánicos de Google para `keyword`, en orden:
        [{rank, url, domain, title, description}]. Vacío si la API falla."""
        payload = [{"keyword": keyword, "location_code": self.cfg.dfs_location_code,
                    "language_code": self.cfg.dfs_language_code, "depth": depth}]
        res = self._tarea(payload, self.SERP_URL, COSTO_SERP_USD, "competidores")
        items = (res or {}).get("items") or []
        out = []
        for it in items:
            if it.get("type") != "organic":
                continue
            fila = {"rank": it.get("rank_absolute") or it.get("rank_group"),
                    "url": it.get("url", ""), "domain": it.get("domain", ""),
                    "title": it.get("title", ""), "description": it.get("description", "")}
            fila["url"] = _sin_seguimiento(fila["url"])
            real = _desde_breadcrumb(fila["url"], it.get("breadcrumb"))
            if real:
                fila.update(real)
            out.append(fila)
        return out

    def sugerencias(self, semilla: str, limite: int = 30) -> list[dict]:
        """Búsquedas reales que CONTIENEN la semilla (DataForSEO Labs keyword_suggestions):
        el nombre del producto y el fabricante («talenti cruise», «cruise sofa»), con su
        volumen, sin importar quién rankea (23-nov). [{keyword, volume}]."""
        payload = [{"keyword": semilla, "location_code": self.cfg.dfs_location_code,
                    "language_code": self.cfg.dfs_language_code, "limit": limite,
                    "include_seed_keyword": True,
                    "order_by": ["keyword_info.search_volume,desc"]}]
        res = self._tarea(payload, self.SUGERENCIAS_URL, COSTO_SUGERENCIAS_USD, "sugerencias")
        return [{"keyword": it.get("keyword"),
                 "volume": (it.get("keyword_info") or {}).get("search_volume")}
                for it in (res or {}).get("items") or [] if it.get("keyword")]

    def ranked_keywords(self, url: str, limite: int = 40, max_posicion: int = 20,
                        patron: str = "") -> list[dict]:
        """Búsquedas por las que RANKEA una página (DataForSEO Labs, ranked_keywords):
        lo que a un competidor con el mismo producto le funciona. Solo las que
        tiene en el top `max_posicion`. [{keyword, volume, difficulty, intent,
        posicion_competidor}]."""
        filtro_pos = ["ranked_serp_element.serp_item.rank_group", "<=", max_posicion]
        target, filtros = url, filtro_pos
        if patron:
            # la SERP dio un enlace de Google: se pide por dominio y se filtra por
            # el tramo de la dirección de la página del producto
            target = urlsplit(url).hostname or url
            filtros = [["ranked_serp_element.serp_item.relative_url", "like", patron],
                       "and", filtro_pos]
        payload = [{"target": target, "location_code": self.cfg.dfs_location_code,
                    "language_code": self.cfg.dfs_language_code, "limit": limite,
                    "filters": filtros,
                    "order_by": ["keyword_data.keyword_info.search_volume,desc"]}]
        res = self._tarea(payload, self.RANKED_URL, COSTO_RANKED_USD, "keywords de competidores")
        out = []
        for it in (res or {}).get("items") or []:
            kd = it.get("keyword_data") or {}
            info = kd.get("keyword_info") or {}
            props = kd.get("keyword_properties") or {}
            serp = (it.get("ranked_serp_element") or {}).get("serp_item") or {}
            if not kd.get("keyword"):
                continue
            out.append({"keyword": kd["keyword"], "volume": info.get("search_volume"),
                        "difficulty": props.get("keyword_difficulty"),
                        "intent": (kd.get("search_intent_info") or {}).get("main_intent"),
                        "posicion_competidor": serp.get("rank_group")})
        return out

    def ideas_de_keywords(self, semillas: list[str], limite: int = 200,
                          contiene: Optional[list[str]] = None) -> list[dict]:
        """Investigación de keywords (DataForSEO Labs, keyword_ideas): búsquedas
        relacionadas con las semillas que la ficha TODAVÍA no atrae, con volumen,
        dificultad (0-100) e intención. [{keyword, volume, cpc, difficulty,
        intent}]. Vacío si la API falla o no alcanza el presupuesto."""
        semillas = [k for k in dict.fromkeys(s.strip().lower() for s in semillas)
                    if self.keyword_valida(k)][:20]
        if not semillas:
            return []
        payload = [{"keywords": semillas, "location_code": self.cfg.dfs_location_code,
                    "language_code": self.cfg.dfs_language_code, "limit": limite,
                    "include_serp_info": False}]
        if contiene:
            # solo ideas que nombran el tipo de producto ('%stool%'): sin esto la
            # API devuelve lo más buscado de todo el rubro
            filtros: list = []
            for w in contiene[:4]:
                filtros += (["or"] if filtros else []) + [["keyword", "like", f"%{w}%"]]
            payload[0]["filters"] = filtros if len(filtros) > 1 else filtros[0]
        res = self._tarea(payload, self.IDEAS_URL, COSTO_IDEAS_USD, "investigación de keywords")
        out = []
        for it in (res or {}).get("items") or []:
            info = it.get("keyword_info") or {}
            props = it.get("keyword_properties") or {}
            intent = (it.get("search_intent_info") or {}).get("main_intent")
            if not it.get("keyword"):
                continue
            out.append({"keyword": it["keyword"], "volume": info.get("search_volume"),
                        "cpc": info.get("cpc"), "difficulty": props.get("keyword_difficulty"),
                        "intent": intent, "origen": "investigacion"})
        return out

    def _request(self, payload: list[dict], url: Optional[str] = None) -> Optional[dict]:
        if self._post is not None:
            return self._post(payload)
        auth = base64.b64encode(f"{self.cfg.dfs_login}:{self.cfg.dfs_password}"
                                .encode()).decode()
        r = self._session.post(url or self.SEARCH_VOLUME_URL, json=payload,
                               headers={"Authorization": f"Basic {auth}"},
                               timeout=60)
        r.raise_for_status()
        return r.json()


class KeywordMapper:
    """Dedup + re-mapeo de keywords a sus productos de origen."""

    BRAND_TERMS = {"cassoni", "cassoni.com"}
    GENERIC_LUXURY = {"luxury", "luxury furniture", "furniture", "design"}

    def __init__(self, fetcher: DataForSEOFetcher, *,
                 min_volume: int = 50,
                 drop_brands: bool = True,
                 drop_generic: bool = True):
        self.fetcher = fetcher
        self.min_volume = min_volume
        self.drop_brands = drop_brands
        self.drop_generic = drop_generic
        self._agg: dict[str, dict] = {}     # kw -> {volume, origins[], cpc, comp}

    def ingest(self, url_keywords: dict[str, list[str]]):
        """Recibe {url: [kw...]}, deduplica preservando origen."""
        url_origin: dict[str, list[str]] = {}
        for url, kws in url_keywords.items():
            for kw in kws:
                url_origin.setdefault(kw, []).append(url)
        uniques = list(url_origin.keys())
        self._agg = {}
        for idx, row in enumerate(self.fetcher.search_volume(uniques)):
            if row is None:
                continue
            kw = uniques[idx]
            self._agg[kw] = {"volume": row.get("volume") or 0,
                             "cpc": row.get("cpc"),
                             "competition": row.get("competition"),
                             "origins": url_origin[kw]}
        return self._agg

    def filter(self, kw: str) -> bool:
        """Aplica los criterios de descarte del informe (marcas, genéricos,
        volumen bajo)."""
        low = kw.lower().strip()
        if self.drop_brands and any(b in low for b in self.BRAND_TERMS):
            return False
        if self.drop_generic and low in self.GENERIC_LUXURY:
            return False
        vol = self._agg.get(kw, {}).get("volume", 0)
        if vol < self.min_volume:
            return False
        return True

    def keywords_for_url(self, url: str, limit: int = 10) -> list[dict]:
        """Keywords válidas para una URL, ordenadas por volumen desc."""
        cands = []
        for kw, info in self._agg.items():
            if url in info["origins"] and self.filter(kw):
                cands.append({"keyword": kw, "volume": info["volume"],
                              "cpc": info["cpc"], "competition": info["competition"]})
        cands.sort(key=lambda c: c["volume"], reverse=True)
        return cands[:limit]

    @property
    def total_unique(self) -> int:
        return len(self._agg)

    @property
    def unique_with_volume(self) -> int:
        return sum(1 for i in self._agg.values() if i.get("volume", 0) >= self.min_volume)