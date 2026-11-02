# -*- coding: utf-8 -*-
"""CLI: el agente arranca solo (selecciona), se audita (preflight) y se mide (revisar).

Antes de esto, `--urls` era obligatorio: sin una lista escrita a mano el pipeline no
corría. El objetivo es que un solo comando elija el trabajo desde GSC.
"""
import json

import pytest

from cassoni import cli


class FakeGSC:
    def __init__(self, paginas, queries=None):
        self.paginas = paginas
        self.queries = queries or {}
        self.llamadas = []

    def pages(self, days=90, page_size=25000):
        self.llamadas.append(("pages", days))
        return list(self.paginas)

    def queries_for_page(self, url, days=90, row_limit=200):
        self.llamadas.append(("query", url, days))
        return list(self.queries.get(url, []))


def _pag(n, impressions=500):
    return {"url": f"https://cassoni.com/product/p{n}/", "impressions": impressions,
            "clicks": 1, "ctr": 0.002, "position": 12.0}


def _q(impressions=300):
    return {"keyword": "sofa modular", "impressions": impressions, "clicks": 0,
            "ctr": 0.0, "position": 12.0}


class TestSeleccionar:
    def test_arma_el_lote_sin_lista_escrita_a_mano(self):
        gsc = FakeGSC([_pag(1), _pag(2)], {_pag(1)["url"]: [_q()],
                                           _pag(2)["url"]: [_q()]})
        lote = cli.seleccionar(gsc, n=2, days=90, pausa=0)
        assert len(lote) == 2
        assert all(c["keyword"] == "sofa modular" for c in lote)

    def test_no_consulta_todas_las_paginas_del_sitio(self):
        # 200 páginas candidatas, pedimos 5: sólo se consultan las necesarias
        paginas = [_pag(i, impressions=1000 - i) for i in range(200)]
        queries = {p["url"]: [_q()] for p in paginas}
        gsc = FakeGSC(paginas, queries)
        lote = cli.seleccionar(gsc, n=5, days=90, pausa=0)
        consultas = [c for c in gsc.llamadas if c[0] == "query"]
        assert len(lote) == 5
        assert len(consultas) <= 15          # 3x el tope pedido

    def test_respeta_el_orden_de_prioridad(self):
        paginas = [_pag(1, impressions=100), _pag(2, impressions=900)]
        queries = {_pag(1)["url"]: [{"keyword": "k1", "impressions": 300,
                                     "clicks": 0, "ctr": 0.0, "position": 5.0}],
                   _pag(2)["url"]: [{"keyword": "k2", "impressions": 900,
                                     "clicks": 0, "ctr": 0.0, "position": 18.0}]}
        lote = cli.seleccionar(FakeGSC(paginas, queries), n=2, days=90, pausa=0)
        # pos 5 con 300 imp gana a pos 18 con 900 imp (mismo score -> gana impresiones de página)
        assert lote[0]["keyword"] == "k1"


class TestParser:
    def test_seleccionar_no_exige_urls(self):
        args = cli.parse_args(["--seleccionar", "10"])
        assert args.seleccionar == 10
        assert args.urls is None

    def test_sin_accion_y_sin_urls_es_error_claro(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(cli.Config, "load", staticmethod(lambda **kw: _cfg(tmp_path)))
        assert cli.main([]) == 2
        assert "Falta --urls" in capsys.readouterr().err

    def test_defaults_seguros(self):
        args = cli.parse_args(["--seleccionar", "10"])
        assert args.write is False          # dry-run por defecto
        assert args.days == 90


class TestMainSeleccionar:
    def test_escribe_el_lote_en_json(self, tmp_path, monkeypatch):
        out = tmp_path / "lote.json"
        gsc = FakeGSC([_pag(1)], {_pag(1)["url"]: [_q()]})

        monkeypatch.setattr(cli, "_make_gsc", lambda cfg: gsc)
        monkeypatch.setattr(cli.Config, "load",
                            staticmethod(lambda **kw: _cfg(tmp_path)))
        rc = cli.main(["--seleccionar", "1", "--out", str(out), "--pausa", "0"])
        assert rc == 0
        data = json.loads(out.read_text())
        assert data["meta"]["tope"] == 1
        assert data["meta"]["dias"] == 90
        assert data["fichas"][0]["url"] == _pag(1)["url"]


class TestPreflight:
    def test_no_gasta_y_reporta_cada_pieza(self, tmp_path, monkeypatch):
        class OkGSC:
            def list_sites(self):
                return ["sc-domain:cassoni.com"]

        class OkWoo:
            def _get(self, endpoint, params=None):
                return [{"id": 1}]

        class OkLLM:
            def ping(self):
                return 200

        monkeypatch.setattr(cli, "_make_gsc", lambda cfg: OkGSC())
        monkeypatch.setattr(cli, "_make_woo", lambda cfg: OkWoo())
        monkeypatch.setattr(cli, "_make_llm", lambda cfg: OkLLM())
        res = cli.preflight(_cfg(tmp_path))
        assert res["gsc"]["ok"] is True
        assert res["woo"]["ok"] is True
        assert res["llm"]["ok"] is True
        assert res["ok"] is True


def _cfg(tmp_path):
    from cassoni.config import Config
    c = Config(env="staging", dry_run=True)
    c.db_url = f"sqlite:///{tmp_path}/cli.db"
    c.wc_base = "https://cassoni.com"
    c.wc_key, c.wc_secret = "ck", "cs"
    c.gsc_service_account_file = str(tmp_path / "x")
    c.llm_base_url = "https://api.deepseek.com/v1"
    c.llm_api_key = "k"
    c.llm_editor_model = "deepseek-flash"
    c.dfs_login, c.dfs_password = "l", "p"
    return c
