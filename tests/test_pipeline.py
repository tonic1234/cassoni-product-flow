# -*- coding: utf-8 -*-
"""Test end-to-end del orquestador: ciclo completo con clientes mockeados."""
import pytest

from cassoni.config import Config
from cassoni.db import DB
from cassoni.orchestrator import Pipeline


class FakeWoo:
    def __init__(self):
        self.product = {
            "id": 120563, "name": "Pedro Sofá", "slug": "cas-cprn-pedro-sofa-01",
            "status": "publish", "type": "simple",
            "permalink": "https://x.com/product/cas-cprn-pedro-sofa-01",
            "description": "<p>Elegante sofá de cuero negro.</p>",
        }
        self.writes = []
    def get_product_by_slug(self, slug):
        assert slug == "cas-cprn-pedro-sofa-01"
        return self.product
    def get_variations(self, product):
        return [] if product["type"] != "variable" else []
    def update_product(self, product_id, *, name, description, allowed=True):
        self.writes.append((name, description))
        return {"id": product_id, "name": name}


class FakeGSC:
    def top_keywords_for_url(self, url, *, days=365, row_limit=10):
        return [{"keyword": "sofá de cuero", "clicks": 5, "impressions": 100,
                 "position": 8, "ctr": 0.05},
                {"keyword": "sofá de lujo", "clicks": 3, "impressions": 80,
                 "position": 10, "ctr": 0.04}]


class FakeLLM:
    def __init__(self):
        self.calls = 0
    def complete(self, system, user, **kw):
        return ""
    def complete_json(self, system, user, *, model=None, temperature=0.2,
                      max_tokens=1800):
        self.calls += 1
        if "control de calidad" in system.lower() or "Eval" in system:
            return {"aprobado": True, "issues": [], "keywords_presentes": ["sofá de cuero"],
                    "tono_lujo": True, "razon": "ok"}
        return {"h1": "Pedro Sofá de Cuero Negro de Lujo", "description": "<p>Elegante sofá de cuero negro, perfecto para living de lujo.</p>",
                "used_keywords": ["sofá de cuero"], "selection_reason": "más descriptiva"}


def _cfg(tmp_path, dry_run=True):
    c = Config(env="staging", dry_run=dry_run)
    c.db_url = f"sqlite:///{tmp_path}/e2e.db"
    c.gsc_service_account_file = str(tmp_path / "x")
    c.llm_editor_model = "editor"
    c.llm_validator_model = "validator"
    return c


def _pipeline(tmp_path, dry_run=True):
    cfg = _cfg(tmp_path, dry_run)
    db = DB(cfg)
    llm = FakeLLM()
    from cassoni.editor import Editor
    editor = Editor(cfg, llm)
    return Pipeline(cfg, db=db, woo=FakeWoo(), gsc=FakeGSC(), llm=llm,
                    editor=editor, dry_run=dry_run)


def test_e2e_dry_run(tmp_path):
    pipe = _pipeline(tmp_path, dry_run=True)
    res = pipe.process("https://x.com/product/cas-cprn-pedro-sofa-01/")
    assert res.status == "processed"
    assert res.aprobado is True
    assert res.aplicado is True          # dry_run registra el intento
    assert "Pedro Sofá de Cuero" in res.edited_h1
    # el FakeWoo no recibió writes porque el orquestador en dry_run no llama update
    assert pipe.woo.writes == []
    # DB guardó antes/despues
    row = pipe.db.get_state(res.url)
    assert row.edited_h1 == res.edited_h1
    assert row.original_h1 == "Pedro Sofá"


def test_e2e_write_enabled(tmp_path):
    pipe = _pipeline(tmp_path, dry_run=False)
    res = pipe.process("https://x.com/product/cas-cprn-pedro-sofa-01/")
    assert res.status == "processed"
    assert res.aplicado is True
    assert len(pipe.woo.writes) == 1
    assert pipe.woo.writes[0][0] == res.edited_h1


def test_e2e_sku_publish_filter(tmp_path):
    pipe = _pipeline(tmp_path, dry_run=True)
    pipe.woo.product["status"] = "draft"
    res = pipe.process("https://x.com/product/cas-cprn-pedro-sofa-01/")
    assert res.status == "skipped"
    assert "draft" in res.reason


def test_e2e_gsc_empty_skips(tmp_path):
    pipe = _pipeline(tmp_path, dry_run=True)
    class SilentGSC:
        def top_keywords_for_url(self, url, **kw):
            return []
    pipe.gsc = SilentGSC()
    res = pipe.process("https://x.com/product/cas-cprn-pedro-sofa-01/")
    assert res.status == "skipped"
    assert "sin keywords" in res.reason


def test_e2e_non_product_url(tmp_path):
    pipe = _pipeline(tmp_path)
    res = pipe.process("https://x.com/product-category/sofas/")
    assert res.status == "skipped"