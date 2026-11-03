# -*- coding: utf-8 -*-
"""Tests de DataForSEO: dedup preservando origen, bulk, remapeo, filtro."""
import pytest

from cassoni.dataforseo import DataForSEOFetcher, KeywordMapper

VOL = {"sofá de lujo": 100, "sofá milano": 40, "cassoni": 900,
       "luxury furniture": 6600, "sofá parís": 300}


def _fetcher(cfg, delay=0.0):
    def fake_post(payload):
        chunk = payload[0]["keywords"]
        rows = []
        for kw in chunk:
            v = VOL.get(kw)
            if v is None:
                rows.append({"keyword_data": {"google_ads": {"search_volume": 0}}})
            else:
                rows.append({"keyword_data": {"google_ads": {"search_volume": v,
                                                             "cpc": 6.77,
                                                             "competition": 0.8}}})
        return {"status_code": 20000, "tasks": [{"result": rows}]}
    return DataForSEOFetcher(cfg, _post=fake_post)


def test_bulk_order_preserved(cfg):
    f = _fetcher(cfg)
    out = f.search_volume(["sofá de lujo", "sofá milano", "luxury furniture"])
    assert out[0]["volume"] == 100
    assert out[1]["volume"] == 40
    assert out[2]["volume"] == 6600


def test_mapper_dedup_preserves_origin(cfg):
    f = _fetcher(cfg)
    m = KeywordMapper(f, min_volume=50)
    m.ingest({
        "https://a/product/sofa-a": ["sofá de lujo", "luxury furniture"],
        "https://a/product/sofa-b": ["sofá de lujo", "sofá parís"],
    })
    # "sofá de lujo" aparece 1 sola vez, con 2 orígenes
    info = m._agg["sofá de lujo"]
    assert info["origins"] == ["https://a/product/sofa-a", "https://a/product/sofa-b"]
    assert m.total_unique == 3  # sofá de lujo, luxury furniture, sofá parís


def test_mapper_filters_brand_and_volume(cfg):
    f = _fetcher(cfg)
    m = KeywordMapper(f, min_volume=50)
    m.ingest({"https://a/p": ["cassoni", "sofá milano", "sofá de lujo"]})
    kws = m.keywords_for_url("https://a/p")
    # cassoni (marca) y sofá milano (vol bajo) descartados; queda sofá de lujo
    assert [k["keyword"] for k in kws] == ["sofá de lujo"]


def test_mapper_remap_to_url(cfg):
    f = _fetcher(cfg)
    m = KeywordMapper(f, min_volume=0)
    m.ingest({"https://a/1": ["sofá de lujo"], "https://a/2": ["sofá parís"]})
    assert m.keywords_for_url("https://a/1")[0]["keyword"] == "sofá de lujo"
    assert m.keywords_for_url("https://a/2")[0]["keyword"] == "sofá parís"


def test_retry_on_null(cfg):
    calls = {"n": 0}
    def flaky(payload):
        calls["n"] += 1
        if calls["n"] == 1:
            return None  # simula result null intermitente
        rows = [{"keyword_data": {"google_ads": {"search_volume": 123}}} for _ in payload[0]["keywords"]]
        return {"status_code": 20000, "tasks": [{"result": rows}]}
    f = DataForSEOFetcher(cfg, _post=flaky)
    out = f.search_volume(["kw1"], )
    assert out[0]["volume"] == 123
    assert calls["n"] == 2

def test_serp_organico_y_costo(cfg):
    def fake_post(payload):
        assert payload[0]["keyword"] == "pedro sofa"
        return {"status_code": 20000, "cost": 0.002, "tasks": [{"result": [{"items": [
            {"type": "paid", "url": "https://ad.com"},
            {"type": "organic", "rank_absolute": 2, "url": "https://a.com/p",
             "domain": "a.com", "title": "Pedro"}]}]}]}
    f = DataForSEOFetcher(cfg, _post=fake_post)
    f.cfg.dfs_max_requests_min = 0
    out = f.serp_organico("pedro sofa")
    assert out == [{"rank": 2, "url": "https://a.com/p", "domain": "a.com",
                    "title": "Pedro", "description": ""}]
    assert f.costo_usd == 0.002


def test_mercado_desde_la_config(cfg):
    vistos = []

    def fake_post(payload):
        vistos.append(payload[0])
        return {"status_code": 20000, "tasks": [{"result": []}]}
    cfg.dfs_location_code, cfg.dfs_language_code = 2724, "es"
    cfg.dfs_max_requests_min = 0
    DataForSEOFetcher(cfg, _post=fake_post).search_volume(["sofa"])
    assert vistos[0]["location_code"] == 2724 and vistos[0]["language_code"] == "es"


# respuesta REAL de keywords_data/google_ads/search_volume/live (3-nov-2026):
# los campos van en la raíz de cada fila, no en keyword_data.google_ads
def test_formato_real_de_la_api_y_cruce_por_keyword(cfg):
    def fake_post(payload):
        kws = payload[0]["keywords"]
        filas = [{"keyword": k, "search_volume": {"club sofa": 1000, "steinway piano": 590}.get(k),
                  "competition": "MEDIUM", "competition_index": 65, "cpc": 2.27}
                 for k in reversed(kws)]          # la API no garantiza el orden
        return {"status_code": 20000, "cost": 0.09,
                "tasks": [{"status_code": 20000, "result": filas}]}
    cfg.dfs_max_requests_min = 0
    out = DataForSEOFetcher(cfg, _post=fake_post).search_volume(
        ["club sofa", "steinway piano", "rare thing"])
    assert out[0]["volume"] == 1000 and out[1]["volume"] == 590
    assert out[2]["volume"] is None
    assert out[0]["competition"] == 0.65        # numérico, no "MEDIUM"


def test_una_keyword_invalida_no_tumba_el_lote(cfg):
    enviadas = []

    def fake_post(payload):
        enviadas.extend(payload[0]["keywords"])
        return {"status_code": 20000, "tasks": [{"status_code": 20000, "result": [
            {"keyword": k, "search_volume": 10} for k in payload[0]["keywords"]]}]}
    cfg.dfs_max_requests_min = 0
    out = DataForSEOFetcher(cfg, _post=fake_post).search_volume(
        ["sofa", "sofa (white)", "x" * 81, "one two three four five six seven eight nine ten eleven"])
    assert enviadas == ["sofa"]
    assert out[0]["volume"] == 10 and out[1:] == [None, None, None]


def test_tarea_rechazada_no_se_reintenta_en_loop(cfg):
    llamadas = []

    def fake_post(payload):
        llamadas.append(1)
        return {"status_code": 20000, "tasks": [{"status_code": 40501,
                                                 "status_message": "Invalid Field"}]}
    cfg.dfs_max_requests_min = 0
    assert DataForSEOFetcher(cfg, _post=fake_post).search_volume(["sofa"]) == [None]
    assert len(llamadas) == 1


def test_sin_saldo_avisa_y_no_reintenta(cfg):
    """Prueba real 3-nov: el 402 se tragaba en silencio y todo salía sin volumen."""
    import requests
    llamadas = []

    class Resp:
        status_code = 402

    def fake_post(payload):
        llamadas.append(1)
        raise requests.HTTPError("402", response=Resp())
    cfg.dfs_max_requests_min = 0
    f = DataForSEOFetcher(cfg, _post=fake_post)
    assert f.search_volume(["sofa"]) == [None]
    assert f.serp_organico("sofa") == []
    assert "SIN SALDO" in f.sin_saldo
    assert len(llamadas) == 2            # uno por método, sin reintentos


def test_cuenta_sin_verificar_avisa_con_el_mensaje_de_la_api(cfg):
    """Prueba real 3-nov: cuenta nueva, 403 'Please verify your account'."""
    import requests

    class Resp:
        status_code = 403
        def json(self):
            return {"status_message": "Please verify your account before using the API."}

    def fake_post(payload):
        raise requests.HTTPError("403", response=Resp())
    cfg.dfs_max_requests_min = 0
    f = DataForSEOFetcher(cfg, _post=fake_post)
    assert f.serp_organico("sofa") == []
    assert "verify your account" in f.sin_saldo


def test_presupuesto_por_corrida(cfg):
    """Cuenta de prueba con US$ 1: no se puede pasar del tope."""
    llamadas = []

    def fake_post(payload):
        llamadas.append(payload)
        return {"status_code": 20000, "cost": 0.09, "tasks": [{"status_code": 20000,
                "result": [{"keyword": k, "search_volume": 1} for k in payload[0].get("keywords", [])]}]}
    cfg.dfs_max_requests_min = 0
    cfg.dfs_presupuesto_usd = 0.10
    f = DataForSEOFetcher(cfg, _post=fake_post)
    assert f.search_volume(["a"])[0]["volume"] == 1          # 0.09: entra
    assert f.search_volume(["b"]) == [None]                  # 0.18: no entra
    assert f.serp_organico("x") == [] or f.costo_usd <= 0.10   # 0.092: entra justo
    assert f.sin_presupuesto is True
    assert len(llamadas) <= 2


def test_cuenta_pausada_dentro_de_la_respuesta(cfg):
    """Prueba real 3-nov: HTTP 200 con tarea 40201 'temporarily paused access'."""
    llamadas = []

    def fake_post(payload):
        llamadas.append(1)
        return {"status_code": 20000, "cost": 0, "tasks": [{"status_code": 40201,
                "status_message": "We have temporarily paused access as a precaution."}]}
    cfg.dfs_max_requests_min = 0
    f = DataForSEOFetcher(cfg, _post=fake_post)
    assert f.serp_organico("sofa") == []
    assert "40201" in f.sin_saldo and "paused" in f.sin_saldo
    assert f.search_volume(["sofa"]) == [None]
    assert len(llamadas) == 2                     # sin reintentos
