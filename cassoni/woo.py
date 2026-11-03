# -*- coding: utf-8 -*-
"""Cliente WooCommerce REST API v3 — lectura + edición GATED.

Seguridad del proyecto:
- GSC se lee, nunca se escribe (módulo gsc.py no tiene update).
- WooCommerce se EDITA (name + long description) en el entorno que diga
  `--env`, solo cuando el validador aprobó y se corrió con `--write`
  (`config.write_enabled == True`). `update_product()` nunca escribe en dry_run.
  Config.validate() frena un env=staging que apunte a la tienda real.
- Cualquier error de red o HTTP sale como WooError: una ficha que falla no
  puede tumbar el lote entero.
"""
from __future__ import annotations

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
        self._session.headers.update({"Content-Type": "application/json"})

    def _url(self, endpoint: str) -> str:
        return f"{self.cfg.wc_base.rstrip('/')}/wp-json/wc/v3/{endpoint}"

    def _get(self, endpoint: str, params: Optional[dict] = None) -> Any:
        try:
            r = self._session.get(self._url(endpoint), params=params,
                                  auth=(self.cfg.wc_key, self.cfg.wc_secret), timeout=45)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as exc:
            raise WooError(f"GET {endpoint}: {exc}") from exc

    def get_product_by_slug(self, slug: str) -> dict:
        items = self._get("products", {"slug": slug})
        if not items:
            raise WooError(f"No se encontró producto con slug '{slug}'")
        return items[0]

    def get_product_by_id(self, product_id: int) -> dict:
        return self._get(f"products/{product_id}")

    def products_by_category(self, category_id: int, per_page: int = 100) -> list[dict]:
        """Fichas de una categoría (id, name, slug) — para conocer los H1 ya usados
        en otras fichas (input del filtro anti-canibalización). Solo lectura."""
        items = []
        page = 1
        while True:
            got = self._get("products", {
                "category": category_id, "per_page": per_page, "page": page,
                "status": "publish", "fields": "id,name,slug",
            })
            if not got:
                break
            items.extend([{"id": p["id"], "name": p.get("name", ""),
                           "slug": p.get("slug", "")} for p in got])
            if len(got) < per_page:
                break
            page += 1
        return items

    def get_product_by_url(self, url: str) -> dict:
        slug, _ = extract_slug(url)
        return self.get_product_by_slug(slug)

    def get_variations(self, product: dict) -> list[dict]:
        """Variaciones de un producto variable (vacío si no es variable)."""
        if product.get("type") != "variable":
            return []
        return self._get(f"products/{product['id']}/variations", {"per_page": 100})

    def update_product(self, product_id: int, *, name: str, description: str,
                       short_description: Optional[str] = None,
                       allowed: bool = True) -> Optional[dict]:
        """Edita H1 (name), long description y (opcional) descripción corta.
        Bloqueado salvo que el gate esté abierto (`write_enabled` y `allowed`).
        Dry-run ⇒ no toca la API. `short_description=None` = NO se toca el campo."""
        payload = {"name": name, "description": description}
        if short_description is not None:
            payload["short_description"] = short_description
        if not self.cfg.write_enabled:
            return {"dry_run": True, "id": product_id, "apply": payload}
        if not allowed:
            raise WooError("Gate cerrado: no se permite escribir en WooCommerce")
        try:
            r = self._session.post(self._url(f"products/{product_id}"),
                                   json=payload,
                                   auth=(self.cfg.wc_key, self.cfg.wc_secret),
                                   timeout=45)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as exc:
            raise WooError(f"POST products/{product_id}: {exc}") from exc