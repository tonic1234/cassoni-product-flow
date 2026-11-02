# -*- coding: utf-8 -*-
"""Punto de partida y revisión del efecto.

Lo que faltaba (auditoría 13-oct): la DB guardaba el texto editado pero no la
posición/impresiones de la consulta objetivo, así que no había forma de decir si
la edición sirvió. Acá: baseline al momento de editar + comparación a 14/28 días.
"""
from sqlalchemy import inspect, text

from cassoni.config import Config
from cassoni.db import DB
from cassoni import revisar


def _cfg(tmp_path, name="rev.db"):
    c = Config(env="staging", dry_run=True)
    c.db_url = f"sqlite:///{tmp_path}/{name}"
    c.gsc_service_account_file = str(tmp_path / "x")
    return c


class FakeGSC:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def queries_for_page(self, url, *, days=90, row_limit=200):
        self.calls.append({"url": url, "days": days, "row_limit": row_limit})
        return list(self.rows)


class TestBaselineEnLaBase:
    def test_guarda_y_lee_la_linea_base(self, tmp_path):
        db = DB(_cfg(tmp_path))
        pid = db.enqueue("https://cassoni.com/product/a/", "a")
        db.record(pid, baseline_keyword="sofa modular", baseline_position=12.0,
                  baseline_impressions=300, baseline_clicks=0, baseline_ctr=0.0,
                  baseline_window="2026-08-04..2026-11-02")
        row = db.get_state("https://cassoni.com/product/a/")
        assert row.baseline_keyword == "sofa modular"
        assert row.baseline_position == 12.0
        assert row.baseline_impressions == 300

    def test_migracion_idempotente_en_base_vieja(self, tmp_path):
        # base creada por la versión anterior: sin columnas de baseline
        cfg = _cfg(tmp_path, "vieja.db")
        db = DB(cfg)
        db.engine.dispose()
        with db.engine.begin() as conn:
            conn.execute(text("ALTER TABLE cassoni_processed_products "
                              "DROP COLUMN baseline_keyword"))
        # volver a abrir debe re-agregarla sin explotar
        db2 = DB(cfg)
        cols = {c["name"] for c in inspect(db2.engine).get_columns("cassoni_processed_products")}
        assert "baseline_keyword" in cols
        assert "baseline_position" in cols

    def test_tabla_de_revisiones_existe(self, tmp_path):
        db = DB(_cfg(tmp_path))
        assert "cassoni_reviews" in inspect(db.engine).get_table_names()


class TestComparar:
    def _b(self, pos=12.0, clics=0, impr=300):
        return {"position": pos, "clicks": clics, "impressions": impr,
                "ctr": (clics / impr) if impr else 0.0}

    def test_sube_de_posicion_es_mejora(self):
        v = revisar.comparar(self._b(pos=12.0), self._b(pos=6.0, clics=4, impr=400))
        assert v["verdict"] == "subio"
        assert v["delta_position"] == -6.0

    def test_baja_de_posicion_es_empeoramiento(self):
        v = revisar.comparar(self._b(pos=6.0, clics=5, impr=400), self._b(pos=12.0))
        assert v["verdict"] == "bajo"

    def test_posicion_estable_con_clics_arriba_es_mejora(self):
        v = revisar.comparar(self._b(pos=8.0, clics=10, impr=500),
                             self._b(pos=8.0, clics=20, impr=500))
        assert v["verdict"] == "subio"

    def test_posicion_estable_sin_cambios_es_igual(self):
        v = revisar.comparar(self._b(pos=8.0, clics=10, impr=500),
                             self._b(pos=8.2, clics=10, impr=500))
        assert v["verdict"] == "igual"

    def test_de_cero_clics_a_alguno_es_mejora(self):
        v = revisar.comparar(self._b(pos=12.0, clics=0), self._b(pos=12.0, clics=3))
        assert v["verdict"] == "subio"

    def test_delta_de_impresiones_se_informa(self):
        v = revisar.comparar(self._b(impr=300), self._b(impr=450))
        assert v["delta_impressions"] == 150


class TestRevisarUrl:
    def test_sin_linea_base_avisa_y_no_consulta(self, tmp_path):
        db = DB(_cfg(tmp_path))
        db.enqueue("https://cassoni.com/product/a/", "a")
        gsc = FakeGSC([])
        out = revisar.revisar_url(db, gsc, "https://cassoni.com/product/a/")
        assert out["verdict"] == "sin_baseline"
        assert gsc.calls == []

    def test_compara_contra_la_consulta_objetivo(self, tmp_path):
        db = DB(_cfg(tmp_path))
        url = "https://cassoni.com/product/a/"
        pid = db.enqueue(url, "a")
        db.record(pid, baseline_keyword="sofa modular", baseline_position=12.0,
                  baseline_impressions=300, baseline_clicks=0, baseline_ctr=0.0)
        gsc = FakeGSC([
            {"keyword": "otra cosa", "clicks": 9, "impressions": 999,
             "position": 1.0, "ctr": 0.009},
            {"keyword": "sofa modular", "clicks": 5, "impressions": 420,
             "position": 6.0, "ctr": 0.0119},
        ])
        out = revisar.revisar_url(db, gsc, url, days=14)
        assert out["verdict"] == "subio"
        assert out["keyword"] == "sofa modular"
        assert out["position"] == 6.0
        assert out["days"] == 14
        assert gsc.calls[0]["days"] == 14
        # queda registrada la revisión
        revs = db.reviews_for(url)
        assert len(revs) == 1
        assert revs[0].verdict == "subio"

    def test_si_la_consulta_desaparecio_lo_dice(self, tmp_path):
        db = DB(_cfg(tmp_path))
        url = "https://cassoni.com/product/a/"
        pid = db.enqueue(url, "a")
        db.record(pid, baseline_keyword="sofa modular", baseline_position=12.0,
                  baseline_impressions=300, baseline_clicks=0, baseline_ctr=0.0)
        gsc = FakeGSC([{"keyword": "otra cosa", "clicks": 9, "impressions": 999,
                        "position": 1.0, "ctr": 0.009}])
        out = revisar.revisar_url(db, gsc, url, days=14)
        assert out["verdict"] == "sin_datos"
