# -*- coding: utf-8 -*-
"""Paso ② de la pizarra: el mismo producto en competidores mejor posicionados."""
from cassoni.competidores import (Competidores, candidatas_de_competidores,
                                  elegir_competidores, leer_html, ngramas)

SERP = [
    {"rank": 1, "url": "https://tienda-a.com/pedro-sofa", "domain": "tienda-a.com"},
    {"rank": 2, "url": "https://www.pinterest.com/pin/1", "domain": "pinterest.com"},
    {"rank": 3, "url": "https://tienda-b.com/p/pedro", "domain": "tienda-b.com"},
    {"rank": 4, "url": "https://cassoni.com/product/pedro/", "domain": "cassoni.com"},
    {"rank": 5, "url": "https://tienda-c.com/pedro", "domain": "tienda-c.com"},
]


def test_solo_los_que_rankean_por_encima_nuestro():
    out = elegir_competidores(SERP, ["cassoni.com"])
    assert [r["domain"] for r in out] == ["tienda-a.com", "tienda-b.com"]


def test_si_no_aparecemos_toma_los_primeros():
    sin_nos = [r for r in SERP if r["domain"] != "cassoni.com"]
    out = elegir_competidores(sin_nos, ["cassoni.com"], n=3)
    assert [r["domain"] for r in out] == ["tienda-a.com", "tienda-b.com", "tienda-c.com"]


def test_lee_h1_h2_y_texto_sin_menu_ni_scripts():
    html = ("<html><head><title>Pedro Sofa | Tienda</title><script>x='velvet sofa'</script>"
            "</head><body><nav><li>Menu items</li></nav><h1>Pedro Sofa</h1>"
            "<h2>Velvet upholstery</h2><p>Deep seat in velvet upholstery.</p>"
            "<footer><p>Free shipping</p></footer></body></html>")
    d = leer_html(html)
    assert d["h1"] == ["Pedro Sofa"] and d["h2"] == ["Velvet upholstery"]
    assert "Deep seat" in d["texto"]
    assert "Menu" not in d["texto"] and "shipping" not in d["texto"]


def test_ngramas_sin_stopwords_en_los_bordes():
    g = ngramas("The velvet upholstery for the pedro sofa")
    assert "velvet upholstery" in g and "pedro sofa" in g
    assert not any(x.startswith("the ") or x.endswith(" for") for x in g)


PAGINAS = [
    {"title": "Pedro Sofa", "h1": ["Pedro Sofa in Velvet"], "h2": ["Velvet upholstery"],
     "texto": "The pedro sofa has velvet upholstery and walnut legs. Visit tienda store."},
    {"title": "Pedro velvet sofa", "h1": ["Pedro Sofa"], "h2": [],
     "texto": "Velvet upholstery, walnut legs, deep seat. Tienda delivers."},
    {"title": "Other", "h1": ["Pedro"], "h2": [], "texto": "A random lamp."},
]


def test_candidatas_que_se_repiten_y_no_tenemos():
    out = candidatas_de_competidores(
        PAGINAS, descripcion_propia="<p>The Pedro Sofa is elegant.</p>",
        texto_producto="Pedro Sofa velvet walnut", marcas_ajenas=["tienda"])
    kws = [c["keyword"] for c in out]
    assert "velvet upholstery" in kws
    assert "pedro sofa" not in kws            # ya está en nuestra ficha
    assert not any("tienda" in k for k in kws)
    assert all(c["origen"] == "competidor" for c in out)


def test_lo_que_dice_un_solo_competidor_no_alcanza():
    out = candidatas_de_competidores(PAGINAS, descripcion_propia="",
                                     texto_producto="random lamp pedro")
    assert "random lamp" not in [c["keyword"] for c in out]


def test_buscar_respeta_robots_y_tolera_paginas_caidas():
    class Fetcher:
        def serp_organico(self, consulta):
            return SERP

    def http_get(url):
        if "tienda-b" in url:
            raise IOError("timeout")
        return "<h1>Pedro Sofa</h1><p>velvet upholstery</p>"

    comp = Competidores(Fetcher(), propios=["cassoni.com"], http_get=http_get,
                        robots=lambda url: "tienda-a" not in url)
    out = comp.buscar("Pedro Sofa Cassoni")
    assert out == []        # a: robots lo prohíbe, b: caída; c está debajo nuestro
