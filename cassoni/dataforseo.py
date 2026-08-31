# -*- coding: utf-8 -*-
"""Cliente DataForSEO — búsqueda de volumen con técnica de BULKING.

- Deduplica keywords a nivel global PRESERVANDO el origen (lista de URLs),
  para poder re-mapear el volumen a cada producto tras el bulk.
- Envía requests de hasta `bulk_size` (1.000) keywords, respetando el rate
  limit (máx requests/min) y con retry/backoff ante result=null intermitente.
- La API devuelve volúmenes en el MISMO orden del array de entrada → mapeo
  directo (indice) sin hash.
"""
from __future__ import annotations

import base64
import json
import threading
import time
from typing import Any, Callable, Optional

import requests

from .config import Config


class DataForSEOFetcher:
    """Enfoque limpio de la API real (validado 28-ago)."""

    SEARCH_VOLUME_URL = "https://api.dataforseo.com/v3/keywords_data/google_ads/search_volume/live"
    SERP_URL = "https://api.dataforseo.com/v3/dataforseo_labs/google/serp_tasks_live"  # referencia

    def __init__(self, config: Config, session: Optional[requests.Session] = None,
                 _post: Optional[Callable] = None):
        self.cfg = config
        self._session = session or requests.Session()
        self._post = _post  # inyectable para tests
        self._lock = threading.Lock()
        self._last_req = 0.0

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

    def search_volume(self, keywords: list[str],
                      location_code: int = 2840) -> list[Optional[dict]]:
        """Volumen para una tanda de keywords. Devuelve, en el MISMO orden,
        el resultado de cada keyword (dict) o None si falló tras retries."""
        results: list[Optional[dict]] = [None] * len(keywords)
        for chunk_start in range(0, len(keywords), self.cfg.dfs_bulk_size):
            chunk = keywords[chunk_start: chunk_start + self.cfg.dfs_bulk_size]
            for attempt in range(self.cfg.dfs_retries + 1):
                self._throttle()
                try:
                    payload = [{
                        "location_code": location_code,
                        "language_code": "en",
                        "keywords": chunk,
                        "search_partners": False,
                    }]
                    data = self._request(payload)
                except requests.RequestException as exc:
                    if attempt >= self.cfg.dfs_retries:
                        break
                    time.sleep(2 ** attempt)
                    continue
                if data is None or data.get("status_code") != 20000:
                    if attempt >= self.cfg.dfs_retries:
                        break
                    time.sleep(2 ** attempt)
                    continue
                rows = data.get("tasks", [{}])[0].get("result", [])
                for i, row in enumerate(rows):
                    pos = i
                    if pos < len(chunk):
                        cd = (row or {}).get("keyword_data", {}) or {}
                        g = cd.get("google_ads", {}) or {}
                        results[chunk_start + pos] = {
                            "volume": g.get("search_volume"),
                            "competition": g.get("competition"),
                            "cpc": g.get("cpc"),
                            "competition_index": g.get("competition_index"),
                            "monthly": g.get("monthly_searches"),
                        }
                break
        return results

    def _request(self, payload: list[dict]) -> Optional[dict]:
        if self._post is not None:
            return self._post(payload)
        auth = base64.b64encode(f"{self.cfg.dfs_login}:{self.cfg.dfs_password}"
                                .encode()).decode()
        r = self._session.post(self.SEARCH_VOLUME_URL, json=payload,
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