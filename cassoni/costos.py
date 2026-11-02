# -*- coding: utf-8 -*-
"""Costo real de una llamada al LLM a partir del `usage` que devuelve la API.

Precios oficiales de `deepseek-flash` (api-docs.deepseek.com/quick_start/pricing,
consultado el 2-nov-2026), en USD por 1M tokens:

  entrada cache hit  $0.006 (peak) / $0.003 (off-peak)
  entrada cache miss $0.30  (peak) / $0.15  (off-peak)
  salida             $1.20  (peak) / $0.60  (off-peak)

Se usa el precio PEAK por defecto: es el peor caso, así el número que se le pasa al
cliente no queda corto. Los precios se pueden pisar por .env.
"""
from __future__ import annotations

PRECIOS_PEAK = {
    "entrada_cache": 0.006,
    "entrada_normal": 0.30,
    "salida": 1.20,
}


def costo_de_usage(usage: dict | None, precios: dict | None = None) -> dict:
    """Devuelve tokens y USD de una respuesta. Sin `usage` => todo en cero."""
    p = {**PRECIOS_PEAK, **(precios or {})}
    u = usage or {}
    entrada = int(u.get("prompt_tokens") or 0)
    salida = int(u.get("completion_tokens") or 0)
    hit = u.get("prompt_cache_hit_tokens")
    miss = u.get("prompt_cache_miss_tokens")
    if hit is None and miss is None:
        # la API no informó caché: se cobra todo como cache miss (conservador)
        hit, miss = 0, entrada
    else:
        hit, miss = int(hit or 0), int(miss or 0)
        if hit + miss < entrada:      # completar lo que no informó
            miss += entrada - (hit + miss)
    usd = (hit * p["entrada_cache"] + miss * p["entrada_normal"]
           + salida * p["salida"]) / 1_000_000
    return {"tokens_in": entrada, "tokens_out": salida,
            "cache_hit": hit, "cache_miss": miss, "usd": round(usd, 8)}


def sumar(consumos: list[dict]) -> dict:
    """Suma una lista de consumos (una por llamada)."""
    total = {"tokens_in": 0, "tokens_out": 0, "cache_hit": 0, "cache_miss": 0,
             "usd": 0.0, "llamadas": 0}
    for c in consumos:
        for k in ("tokens_in", "tokens_out", "cache_hit", "cache_miss"):
            total[k] += int(c.get(k) or 0)
        total["usd"] += float(c.get("usd") or 0)
        total["llamadas"] += 1
    total["usd"] = round(total["usd"], 8)
    return total
