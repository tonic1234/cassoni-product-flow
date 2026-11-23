# -*- coding: utf-8 -*-
"""Piso de saldo de DataForSEO: siempre quedan créditos para trabajar (23-nov)."""
from cassoni.config import Config
from cassoni.dataforseo import DataForSEOFetcher


def _f(saldo, piso=5.0):
    c = Config(env="staging")
    c.dfs_saldo_minimo = piso
    f = DataForSEOFetcher(c)
    f.consultas_saldo = 0

    def _saldo():
        f.consultas_saldo += 1
        return {"saldo_usd": saldo}
    f.saldo = _saldo
    return f


def test_con_saldo_sobre_el_piso_se_pide():
    f = _f(20.69)
    assert f._alcanza(0.016) and f._alcanza(0.016)
    assert f.consultas_saldo == 1               # una sola consulta por corrida


def test_en_el_piso_no_se_pide_nada_pago():
    f = _f(4.90)
    assert not f._alcanza(0.016) and f.sin_presupuesto


def test_sin_dato_de_saldo_no_frena():
    assert _f(None)._alcanza(0.016)


def test_piso_cero_desactiva_el_control():
    f = _f(0.5, piso=0)
    assert f._alcanza(0.016) and f.consultas_saldo == 0
