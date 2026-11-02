# -*- coding: utf-8 -*-
"""Tests del cliente GSC (sin red: service fake).

Lo que se arregla acá (auditoría 13-oct): la consulta por ficha pedía 365 días y 10
filas, y la API devuelve ordenado por CLICS, así que las consultas con muchas
impresiones y cero clics —justo las oportunidades— quedaban afuera.
"""
import datetime as dt

from cassoni.gsc import GSCClient


class _Req:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _Analytics:
    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.bodies = []

    def query(self, siteUrl=None, body=None):
        self.bodies.append({"siteUrl": siteUrl, "body": dict(body)})
        # la API real devuelve vacío cuando se pasa del final: el fake la imita
        return _Req(self.respuestas.pop(0) if self.respuestas else {"rows": []})


class _Service:
    def __init__(self, respuestas):
        self._a = _Analytics(respuestas)

    def searchanalytics(self):
        return self._a


def _cli(tmp_path, respuestas):
    cfg = type("C", (), {})()
    cfg.gsc_service_account_file = str(tmp_path / "x.json")
    cfg.gsc_site = "sc-domain:cassoni.com"
    c = GSCClient.__new__(GSCClient)
    c.cfg = cfg
    c.service = _Service(respuestas)
    return c


def _fila(keys, impressions=100, clicks=1, ctr=0.01, position=10.0):
    return {"keys": keys, "impressions": impressions, "clicks": clicks,
            "ctr": ctr, "position": position}


class TestPaginas:
    def test_pagina_hasta_agotar(self, tmp_path):
        r1 = {"rows": [_fila(["https://cassoni.com/product/a/"], impressions=500)]}
        r2 = {"rows": [_fila(["https://cassoni.com/product/b/"], impressions=100)]}
        cli = _cli(tmp_path, [r1, r2])
        out = cli.pages(days=90, page_size=1)
        assert [r["url"] for r in out] == ["https://cassoni.com/product/a/",
                                           "https://cassoni.com/product/b/"]
        # la segunda request arranca donde terminó la primera
        assert cli.service._a.bodies[1]["body"]["startRow"] == 1

    def test_paginas_arma_las_filas(self, tmp_path):
        cli = _cli(tmp_path, [{"rows": [_fila(["https://cassoni.com/product/a/"],
                                             impressions=500, clicks=5, ctr=0.01,
                                             position=9.5)]}])
        out = cli.pages(days=90)
        assert out[0] == {"url": "https://cassoni.com/product/a/", "impressions": 500,
                          "clicks": 5, "ctr": 0.01, "position": 9.5}

    def test_paginas_pide_dimension_page_y_ventana(self, tmp_path):
        cli = _cli(tmp_path, [{"rows": []}])
        cli.pages(days=90)
        body = cli.service._a.bodies[0]["body"]
        assert body["dimensions"] == ["page"]
        fin = dt.date.fromisoformat(body["endDate"])
        ini = dt.date.fromisoformat(body["startDate"])
        assert (fin - ini).days == 90
        assert cli.service._a.bodies[0]["siteUrl"] == "sc-domain:cassoni.com"


class TestQueriesForPage:
    def test_pide_90_dias_y_200_filas(self, tmp_path):
        cli = _cli(tmp_path, [{"rows": []}])
        cli.queries_for_page("https://cassoni.com/product/a/")
        body = cli.service._a.bodies[0]["body"]
        assert body["rowLimit"] == 200
        fin = dt.date.fromisoformat(body["endDate"])
        ini = dt.date.fromisoformat(body["startDate"])
        assert (fin - ini).days == 90

    def test_ordena_por_impresiones_no_por_clics(self, tmp_path):
        # la API devuelve primero la de más clics; la oportunidad es la de más impresiones
        filas = [_fila(["sofa de cuero"], impressions=500, clicks=80, ctr=0.16, position=1.0),
                 _fila(["quartz stone dining table"], impressions=740, clicks=0, ctr=0.0,
                       position=22.5)]
        cli = _cli(tmp_path, [{"rows": filas}])
        out = cli.queries_for_page("https://cassoni.com/product/a/")
        assert out[0]["keyword"] == "quartz stone dining table"

    def test_filtra_por_la_pagina_exacta(self, tmp_path):
        cli = _cli(tmp_path, [{"rows": []}])
        cli.queries_for_page("https://cassoni.com/product/a/")
        body = cli.service._a.bodies[0]["body"]
        f = body["dimensionFilterGroups"][0]["filters"][0]
        assert f["dimension"] == "page" and f["operator"] == "equals"
        assert f["expression"] == "https://cassoni.com/product/a/"


class TestContratoViejo:
    def test_top_keywords_sigue_devolviendo_el_mismo_shape(self, tmp_path):
        cli = _cli(tmp_path, [{"rows": [_fila(["sofa modular"], impressions=300,
                                             clicks=0, ctr=0.0, position=12.0)]}])
        out = cli.top_keywords_for_url("https://cassoni.com/product/a/")
        assert out == [{"keyword": "sofa modular", "clicks": 0, "impressions": 300,
                        "position": 12.0, "ctr": 0.0}]

    def test_top_keywords_por_defecto_lee_90_dias_y_200(self, tmp_path):
        cli = _cli(tmp_path, [{"rows": []}])
        cli.top_keywords_for_url("https://cassoni.com/product/a/")
        body = cli.service._a.bodies[0]["body"]
        assert body["rowLimit"] == 200
        ini = dt.date.fromisoformat(body["startDate"])
        fin = dt.date.fromisoformat(body["endDate"])
        assert (fin - ini).days == 90
