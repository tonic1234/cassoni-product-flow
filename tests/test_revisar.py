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
    """`rows` = filas de DESPUÉS; `antes` = filas de la ventana previa."""
    def __init__(self, rows, antes=None):
        self.rows = rows
        self.antes = antes or []
        self.calls = []

    def queries_for_page(self, url, *, days=90, row_limit=200, start=None, end=None):
        self.calls.append({"url": url, "days": days, "start": start, "end": end})
        if start is not None and len(self.calls) == 1:
            return list(self.antes)
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


import datetime as dt

URL = "https://cassoni.com/product/a/"
EDITADA = dt.datetime(2026, 9, 1, 12, 0)


def _escrita(tmp_path, kws=("sofa modular", "club sofa")):
    db = DB(_cfg(tmp_path))
    pid = db.enqueue(URL, "a")
    db.record(pid, applied=1, edited_at=EDITADA, status="processed")
    db.guardar_objetivos(URL, [{"keyword": k} for k in kws], aplicada=True)
    return db


class TestRevisarUrl:
    def test_sin_flujo_v2_avisa_y_no_consulta(self, tmp_path):
        db = DB(_cfg(tmp_path))
        db.enqueue(URL, "a")
        gsc = FakeGSC([])
        out = revisar.revisar_url(db, gsc, URL)
        assert out["verdict"] == "sin_baseline"
        assert gsc.calls == []

    def test_una_corrida_en_seco_no_se_mide(self, tmp_path):
        """Auditoría 3-nov: se medían fichas que nunca se escribieron."""
        db = DB(_cfg(tmp_path))
        pid = db.enqueue(URL, "a")
        db.record(pid, status="processed")
        db.guardar_objetivos(URL, [{"keyword": "sofa modular"}], aplicada=False)
        out = revisar.revisar_url(db, FakeGSC([]), URL)
        assert out["verdict"] == "sin_baseline"

    def test_antes_de_tiempo_queda_pendiente(self, tmp_path):
        db = _escrita(tmp_path)
        gsc = FakeGSC([])
        out = revisar.revisar_url(db, gsc, URL, days=14, hoy=dt.date(2026, 9, 10))
        assert out["verdict"] == "pendiente"
        assert gsc.calls == []

    def test_ventanas_del_mismo_largo(self, tmp_path):
        """Auditoría 3-nov: comparaba la suma de 90 días contra 14."""
        db = _escrita(tmp_path)
        gsc = FakeGSC([])
        revisar.revisar_url(db, gsc, URL, days=14, hoy=dt.date(2026, 10, 1))
        antes, despues = gsc.calls
        assert (antes["end"] - antes["start"]).days == (despues["end"] - despues["start"]).days
        assert antes["end"] < EDITADA.date() < despues["start"]

    def test_mide_cada_keyword_objetivo(self, tmp_path):
        db = _escrita(tmp_path)
        gsc = FakeGSC(
            rows=[{"keyword": "sofa modular", "clicks": 5, "impressions": 420,
                   "position": 6.0, "ctr": 0.0119},
                  {"keyword": "club sofa", "clicks": 1, "impressions": 80,
                   "position": 14.0, "ctr": 0.0125}],
            antes=[{"keyword": "sofa modular", "clicks": 0, "impressions": 300,
                    "position": 12.0, "ctr": 0.0}])
        out = revisar.revisar_url(db, gsc, URL, days=14, hoy=dt.date(2026, 10, 1))
        por_kw = {m["keyword"]: m for m in out["keywords"]}
        assert por_kw["sofa modular"]["verdict"] == "subio"
        assert por_kw["club sofa"]["verdict"] == "subio"      # de 0 clics a 1
        assert out["verdict"] == "subio"
        assert len(db.reviews_for(URL)) == 2

    def test_keyword_que_aparece_por_primera_vez(self, tmp_path):
        db = _escrita(tmp_path, kws=("velvet upholstery",))
        gsc = FakeGSC(rows=[{"keyword": "velvet upholstery", "clicks": 0,
                             "impressions": 50, "position": 30.0, "ctr": 0}])
        out = revisar.revisar_url(db, gsc, URL, days=14, hoy=dt.date(2026, 10, 1))
        assert out["keywords"][0]["verdict"] == "aparecio"

    def test_si_no_hay_datos_lo_dice(self, tmp_path):
        db = _escrita(tmp_path, kws=("sofa modular",))
        out = revisar.revisar_url(db, FakeGSC([]), URL, days=14, hoy=dt.date(2026, 10, 1))
        assert out["keywords"][0]["verdict"] == "sin_datos"

    def test_lote_solo_toma_las_escritas(self, tmp_path):
        db = _escrita(tmp_path)
        db.enqueue("https://cassoni.com/product/seco/", "seco")
        res = revisar.revisar_lote(db, FakeGSC([]), days=14)
        assert [r["url"] for r in res] == [URL]
