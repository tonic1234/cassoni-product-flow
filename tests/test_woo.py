# -*- coding: utf-8 -*-
"""Tests del cliente WooCommerce: lectura y escritura GATED (dry_run)."""
import pytest

from cassoni.woo import WooCommerce, WooError


def _session_mock():
    import requests
    class S:
        def __init__(self):
            self.requests = []
            self.headers = {}
        def get(self, url, params=None, auth=None, timeout=None):
            self.requests.append(("GET", url))
            class R:
                def raise_for_status(self): pass
                def json(self):
                    if "categories" in url:
                        return [{"id": 5, "name": "Sofas & Sectionals"}]
                    return [{"id": 120563, "name": "Pedro Sofa", "type": "simple",
                             "status": "publish", "price": "15436",
                             "slug": "cas-cprn-pedro-sofa-01",
                             "permalink": "https://x.com/product/pedro-sofa",
                             "description": "<p>Elegante sofá.</p>"}]
            return R()
        def post(self, url, json=None, auth=None, timeout=None):
            self.requests.append(("POST", url, json))
            class R:
                def raise_for_status(self): pass
                def json(self): return {"id": 120563, "name": "Editado", "status": "publish"}
            return R()
    return S()


def test_get_product_by_slug(cfg):
    wc = WooCommerce(cfg, session=_session_mock())
    p = wc.get_product_by_slug("cas-cprn-pedro-sofa-01")
    assert p["id"] == 120563
    assert p["name"] == "Pedro Sofa"


def test_get_variations_simple_empty(cfg):
    wc = WooCommerce(cfg, session=_session_mock())
    assert wc.get_variations({"type": "simple"}) == []


def test_dry_run_no_write(cfg):
    wc = WooCommerce(cfg)  # cfg.dry_run=True
    out = wc.update_product(120563, name="X", description="<p>d</p>")
    assert out["dry_run"] is True
    assert "apply" in out
    assert out["id"] == 120563


def test_write_blocked_by_dry_run(cfg):
    wc = WooCommerce(cfg)
    # aun pasando allowed=True, dry_run manda: no llama a la API
    out = wc.update_product(120563, name="X", description="<p>d</p>", allowed=True)
    assert out["dry_run"] is True


def test_write_gate_closed_raises(cfg_write):
    wc = WooCommerce(cfg_write, session=_session_mock())
    with pytest.raises(WooError):
        wc.update_product(120563, name="X", description="<p>d</p>", allowed=False)


def test_write_ok_when_enabled(cfg_write):
    wc = WooCommerce(cfg_write, session=_session_mock())
    out = wc.update_product(120563, name="Editado", description="<p>d</p>", allowed=True)
    assert out["id"] == 120563
    assert out["name"] == "Editado"