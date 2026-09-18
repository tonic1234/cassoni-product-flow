# -*- coding: utf-8 -*-
"""Test end-to-end del orquestador: ciclo completo con clientes mockeados.

CONTRATO NUEVO (18-sep-2026, spec "Reglas de contenido SEO para fichas de
producto"): el editor devuelve ficha completa {h1, short_description,
description, keyword_principal, secondary_keywords, discarded}; el validador
corre reglas mecánicas (checklist) ANTES del LLM; el update de WooCommerce
incluye short_description; el pipeline recibe categorías/marca/atributos y las
keywords ya usadas de fichas hermanas (anti-canibalización). Los tests viejos se
actualizaron a este contrato con OK explícito: manda la spec.
"""
import pytest

from cassoni.config import Config
from cassoni.db import DB
from cassoni.orchestrator import Pipeline

# --- descripción larga spec-compliant del fake (>=150 palabras, 2 H2, sin
# --- repetir las secundarias) ---
_FRASES = [
    "Diseñado en líneas sobrias, este mueble combina estructura de madera maciza "
    "con tapicería de cuero, y cada costura queda rematada a mano.",
    "El respaldo ofrece un descanso profundo, los apoyabrazos redondeados completan "
    "una silueta equilibrada y la pieza aporta presencia sin recargar el ambiente.",
    "Se fabrica bajo pedido, puede personalizarse en distintos acabados y la entrega "
    "incluye montaje en el domicilio y garantía de cinco años.",
    "El cuero madura con los años ganando carácter, mientras la madera de roble "
    "sostiene el conjunto con firmeza y el mantenimiento se reduce a la limpieza habitual.",
    "Las medidas y las fichas técnicas completas figuran al pie de la página, junto "
    "con las opciones de color disponibles de fábrica y los tiempos estimados de entrega.",
    "Cada unidad pasa por un control de calidad previo al despacho, se embala con "
    "protección en todas sus aristas y el transportista coordina la recepción con el cliente.",
]
_DESC_OK = ("<h2>Diseño</h2><p>" + " ".join(_FRASES[:3]) + "</p>"
            "<h2>Materiales</h2><p>" + " ".join(_FRASES[3:]) + "</p>")


class FakeWoo:
    def __init__(self):
        self.product = {
            "id": 120563, "name": "Pedro Sofá", "slug": "cas-cprn-pedro-sofa-01",
            "status": "publish", "type": "simple",
            "permalink": "https://x.com/product/cas-cprn-pedro-sofa-01",
            "short_description": "Elegante sofá de cuero negro.",
            "description": "<p>Elegante sofá de cuero negro.</p>",
            "categories": [{"id": 5, "name": "Sofás"}],
            "attributes": [{"name": "Marca", "options": ["Cassoni"]},
                           {"name": "Material", "options": ["Cuero"]}],
        }
        self.writes = []
        self.sibling_calls = []
    def get_product_by_slug(self, slug):
        assert slug == "cas-cprn-pedro-sofa-01"
        return self.product
    def get_variations(self, product):
        return [] if product["type"] != "variable" else []
    def products_by_category(self, category_id, per_page=100):
        self.sibling_calls.append(category_id)
        return [{"id": 120563, "name": "Pedro Sofá", "slug": "p1"},
                {"id": 999, "name": "Otro Sofá Belinda", "slug": "p2"}]
    def update_product(self, product_id, *, name, description,
                       short_description=None, allowed=True):
        self.writes.append((name, short_description, description))
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
        self.last_user = ""
        self.editor_user = ""
    def complete(self, system, user, **kw):
        return ""
    def complete_json(self, system, user, *, model=None, temperature=0.2,
                      max_tokens=1800):
        self.calls += 1
        self.last_user = user
        if "control de calidad" in system.lower() or "Eval" in system:
            self.editor_user = self.editor_user  # el call anterior fue el editor
            return {"aprobado": True, "issues": [], "keywords_presentes": ["sofá de cuero"],
                    "tono_lujo": True, "razon": "ok"}
        self.editor_user = user
        return {
            "h1": "Sofá de cuero Cassoni Pedro Sofá",
            "keyword_principal": "sofá de cuero",
            "short_description": "Sofá de cuero: elegancia para el living.",
            "description": _DESC_OK,
            "secondary_keywords": [
                {"keyword": "sofá de lujo", "why": "variante de uso"},
                {"keyword": "sofá de cuero negro", "why": "por material y acabado"}],
            "discarded": [{"keyword": "sofá de la colección hermana",
                           "belongs_to": "otra ficha"}],
            "used_keywords": ["sofá de cuero", "sofá de lujo"],
            "selection_reason": "la de mayor volumen",
        }


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
    assert "Sofá de cuero" in res.edited_h1
    assert res.edited_short_description == "Sofá de cuero: elegancia para el living."
    # el FakeWoo no recibió writes porque el orquestador en dry_run no llama update
    assert pipe.woo.writes == []
    # DB guardó antes/despues (incluye desc corta)
    row = pipe.db.get_state(res.url)
    assert row.edited_h1 == res.edited_h1
    assert row.edited_short_description == res.edited_short_description
    assert row.original_h1 == "Pedro Sofá"


def test_e2e_write_enabled(tmp_path):
    pipe = _pipeline(tmp_path, dry_run=False)
    res = pipe.process("https://x.com/product/cas-cprn-pedro-sofa-01/")
    assert res.status == "processed"
    assert res.aplicado is True
    assert len(pipe.woo.writes) == 1
    name, short, desc = pipe.woo.writes[0]
    assert name == res.edited_h1
    assert short == res.edited_short_description
    assert desc == res.edited_description


def test_e2e_editor_recibe_contexto_anti_canibalizacion(tmp_path):
    # (spec 18-sep) el editor recibe fichas hermanas para no canibalizar
    pipe = _pipeline(tmp_path, dry_run=True)
    pipe.process("https://x.com/product/cas-cprn-pedro-sofa-01/")
    assert pipe.woo.sibling_calls == [5]       # categoría del producto
    assert "Otro Sofá Belinda" in pipe.editor.llm.editor_user
    assert "Categoría(s): Sofás" in pipe.editor.llm.editor_user
    assert "Marca: Cassoni" in pipe.editor.llm.editor_user
    assert "Material: Cuero" in pipe.editor.llm.editor_user


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