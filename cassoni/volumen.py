# -*- coding: utf-8 -*-
"""Volumen de búsqueda con caché (DataForSEO como ENRIQUECIMIENTO, no filtro).

- GSC dice qué keywords tiene cada ficha; DataForSEO solo les suma volumen.
- Un pedido de hasta 1.000 keywords cuesta lo mismo que uno de 10: por eso se
  junta todo lo del lote del día y se pide UNA vez (`precargar`).
- La caché vive en la base (`cassoni_keyword_volume`) y vence a los N días: el
  volumen es mensual, no tiene sentido pagarlo dos veces.
- `None` = DataForSEO no lo informa. NO es cero: la keyword puede tener
  impresiones reales en GSC.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional

log = logging.getLogger("cassoni.volumen")


def _norm(kw: str) -> str:
    return " ".join((kw or "").lower().split())


class Volumenes:
    def __init__(self, config, db, fetcher):
        self.cfg = config
        self.db = db
        self.fetcher = fetcher          # DataForSEOFetcher (o fake en tests)
        self._mem: dict[str, Optional[dict]] = {}

    @property
    def costo_usd(self) -> float:
        return float(getattr(self.fetcher, "costo_usd", 0.0) or 0.0)

    def obtener(self, keywords: Iterable[str]) -> dict[str, Optional[dict]]:
        """{kw normalizada: {volume, cpc, competition} | None}. Consulta a la API
        solo lo que no está en memoria ni en caché vigente, en un único pedido."""
        pedidas = list(dict.fromkeys(_norm(k) for k in keywords if _norm(k)))
        faltan = [k for k in pedidas if k not in self._mem]
        if faltan:
            cache = self.db.volumenes_frescos(faltan, self.cfg.dfs_location_code,
                                              self.cfg.dfs_cache_dias)
            self._mem.update(cache)
            faltan = [k for k in faltan if k not in cache]
        if faltan and self.fetcher is not None:
            try:
                filas = self.fetcher.search_volume(faltan)
            except Exception as exc:       # sin volumen se sigue con GSC
                log.warning("DataForSEO no respondió (%s): sigo sin volumen", exc)
                filas = [None] * len(faltan)
            nuevos = {kw: fila for kw, fila in zip(faltan, filas)}
            self._mem.update(nuevos)
            # solo se cachea lo que la API contestó: un fallo no se guarda como dato
            self.db.guardar_volumenes({k: v for k, v in nuevos.items() if v is not None},
                                      self.cfg.dfs_location_code)
        return {k: self._mem.get(k) for k in pedidas}

    def anotar(self, filas: list[dict]) -> list[dict]:
        """Copia de `filas` con `volume` (None si no hay dato)."""
        vol = self.obtener(f.get("keyword", "") for f in filas)
        out = []
        for f in filas:
            d = vol.get(_norm(f.get("keyword", ""))) or {}
            # si la fila ya trae volumen (investigación, competidores) se respeta
            volumen = f["volume"] if f.get("volume") is not None else d.get("volume")
            out.append({**f, "volume": volumen, "spell": d.get("spell")})
        return out
