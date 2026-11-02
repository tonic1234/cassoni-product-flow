# -*- coding: utf-8 -*-
"""Costo de cada llamada al LLM: el número que decide si el lote grande se banca."""
from cassoni import costos


def test_un_millon_de_entrada_y_uno_de_salida():
    c = costos.costo_de_usage({"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000})
    assert c["cache_miss"] == 1_000_000
    assert round(c["usd"], 4) == round(0.30 + 1.20, 4)


def test_la_cache_se_cobra_mucho_mas_barata():
    c = costos.costo_de_usage({"prompt_tokens": 1_000_000, "completion_tokens": 0,
                               "prompt_cache_hit_tokens": 1_000_000,
                               "prompt_cache_miss_tokens": 0})
    assert round(c["usd"], 4) == 0.006


def test_sin_datos_de_cache_se_cobra_todo_como_miss():
    # conservador: si la API no informa el desglose, no se regala descuento
    c = costos.costo_de_usage({"prompt_tokens": 2000, "completion_tokens": 500})
    assert c["cache_hit"] == 0
    assert c["cache_miss"] == 2000


def test_cache_incompleta_se_completa_como_miss():
    c = costos.costo_de_usage({"prompt_tokens": 1000, "completion_tokens": 0,
                               "prompt_cache_hit_tokens": 400})
    assert c["cache_hit"] == 400
    assert c["cache_miss"] == 600


def test_sin_usage_es_cero():
    assert costos.costo_de_usage(None)["usd"] == 0.0
    assert costos.costo_de_usage({})["usd"] == 0.0


def test_precios_configurables():
    c = costos.costo_de_usage({"prompt_tokens": 1_000_000, "completion_tokens": 0},
                              precios={"entrada_normal": 0.15})
    assert round(c["usd"], 4) == 0.15


def test_sumar_llamadas():
    a = costos.costo_de_usage({"prompt_tokens": 1000, "completion_tokens": 100})
    b = costos.costo_de_usage({"prompt_tokens": 2000, "completion_tokens": 200})
    t = costos.sumar([a, b])
    assert t["llamadas"] == 2
    assert t["tokens_in"] == 3000
    assert t["tokens_out"] == 300
    assert round(t["usd"], 8) == round(a["usd"] + b["usd"], 8)
