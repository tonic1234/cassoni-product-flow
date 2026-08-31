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