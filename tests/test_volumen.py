# -*- coding: utf-8 -*-
"""Volumen con caché: un pedido por lote, sin pagar dos veces la misma keyword."""
from cassoni.config import Config
from cassoni.db import DB
from cassoni.volumen import Volumenes


class Fetcher:
    def __init__(self, vol, falla=False):
        self.vol = vol
        self.pedidos = []
        self.falla = falla
        self.costo_usd = 0.0

    def search_volume(self, kws):
        if self.falla:
            raise RuntimeError("dfs caído")
        self.pedidos.append(list(kws))
        self.costo_usd += 0.075
        return [{"volume": self.vol.get(k)} for k in kws]


def _vol(tmp_path, fetcher):
    c = Config(env="staging")
    c.db_url = f"sqlite:///{tmp_path}/v.db"
    db = DB(c)
    return Volumenes(c, db, fetcher), db, c


def test_un_solo_pedido_y_dedup(tmp_path):
    f = Fetcher({"sofa": 100})
    v, _, _ = _vol(tmp_path, f)
    out = v.obtener(["Sofa", "sofa ", "chair"])
    assert f.pedidos == [["sofa", "chair"]]
    assert out["sofa"]["volume"] == 100 and out["chair"]["volume"] is None


def test_la_cache_sobrevive_entre_corridas(tmp_path):
    f = Fetcher({"sofa": 100})
    v, db, c = _vol(tmp_path, f)
    v.obtener(["sofa"])
    f2 = Fetcher({"sofa": 999})
    v2 = Volumenes(c, db, f2)
    assert v2.obtener(["sofa"])["sofa"]["volume"] == 100
    assert f2.pedidos == []


def test_cache_vencida_se_vuelve_a_pedir(tmp_path):
    f = Fetcher({"sofa": 100})
    v, db, c = _vol(tmp_path, f)
    v.obtener(["sofa"])
    c.dfs_cache_dias = -1
    f2 = Fetcher({"sofa": 120})
    assert Volumenes(c, db, f2).obtener(["sofa"])["sofa"]["volume"] == 120


def test_si_dfs_falla_se_sigue_sin_volumen_y_no_se_cachea(tmp_path):
    v, db, c = _vol(tmp_path, Fetcher({}, falla=True))
    assert v.obtener(["sofa"]) == {"sofa": None}
    assert db.volumenes_frescos(["sofa"], c.dfs_location_code, 30) == {}


def test_anotar_suma_volume_sin_filtrar(tmp_path):
    v, _, _ = _vol(tmp_path, Fetcher({"sofa": 100}))
    out = v.anotar([{"keyword": "sofa", "impressions": 5}, {"keyword": "x", "impressions": 9}])
    assert out == [{"keyword": "sofa", "impressions": 5, "volume": 100},
                   {"keyword": "x", "impressions": 9, "volume": None}]
