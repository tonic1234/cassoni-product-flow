# -*- coding: utf-8 -*-
"""Cliente WooCommerce REST API v3 — lectura + edición GATED.

Seguridad del proyecto:
- GSC se lee, nunca se escribe (módulo gsc.py no tiene update).
- WooCommerce se EDITA en STAGING (H1 + long description), solo cuando el
  validador pasó y el orquestador abre el gate (o sea, `config.write_enabled
  == True`). `update_product()` nunca implica write si dry_run.
"""
from __future__ import annotations

import time
import base64
from typing import Any, Optional

import requests

from .config import Config
from .extract import extract_slug


class WooError(Exception):
    pass


class WooCommerce:
    def __init__(self, config: Config, session: Optional[requests.Session] = None):
        self.cfg = config
        self._session = session or requests.Session()
        self._auth = base64.b64encode(
            f"{config.wc_key}:{config.wc_secret}".encode()).decode()
        self._session.headers.update({"Content-Type": "application/json"})

    def _url(self, endpoint: str) -> str:
        return f"{self.cfg.wc_base.rstrip('/')}/wp-json/wc/v3/{endpoint}"

    def _get(self, endpoint: str, params: Optional[dict] = None) -> Any:
        r = self._session.get(self._url(endpoint), params=params,
                              auth=(self.cfg.wc_key, self.cfg.wc_secret), timeout=45)
        r.raise_for_status()
        return r.json()

    def get_product_by_slug(self, slug: str) -> dict:
        items = self._get("products", {"slug": slug})
        if not items:
            raise WooError(f"No se encontró producto con slug '{slug}'")
        return items[0]

    def get_product_by_id(self, product_id: int) -> dict:
        return self._get(f"products/{product_id}")

    def get_product_by_url(self, url: str) -> dict:
        slug, _ = extract_slug(url)
        return self.get_product_by_slug(slug)

    def get_variations(self, product: dict) -> list[dict]:
        """Variaciones de un producto variable (vacío si no es variable)."""
        if product.get("type") != "variable":
            return []
        return self._get(f"products/{product['id']}/variations", {"per_page": 100})

    def update_product(self, product_id: int, *, name: str, description: str,
                       allowed: bool = True) -> Optional[dict]:
        """Edita H1 (name) y long description. Bloqueado salvo que el gate
        esté abierto (`write_enabled` y `allowed`). Dry-run ⇒ no toca la API."""
        if not self.cfg.write_enabled:
            return {"dry_run": True, "id": product_id,
                    "apply": {"name": name, "description": description}}
        if not allowed:
            raise WooError("Gate cerrado: no se permite escribir en WooCommerce")
        payload = {"name": name, "description": description}
        r = self._session.post(self._url(f"products/{product_id}"),
                               json=payload,
                               auth=(self.cfg.wc_key, self.cfg.wc_secret),
                               timeout=45)
        r.raise_for_status()
        return r.json()