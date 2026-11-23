# -*- coding: utf-8 -*-
"""Reglas del SEO (Alex, 17-nov-2026): H1 por lo que la gente busca y keywords de
Search Console + marca y tipo, decididas en código."""
from cassoni.reglas_seo import (elegir_keywords, h1_por_datos, nombre_de_busqueda,
                                rasgos_con_volumen)


def test_nombre_de_busqueda():
    assert nombre_de_busqueda("Cleopatra Chair (SC1019)") == "cleopatra chair"
    assert nombre_de_busqueda("Dandy Pool Table (7, 8 or 9 feet)") == "dandy pool table"


def test_si_el_nombre_ya_se_busca_alcanza_con_nombre_y_marca():
    r = h1_por_datos("Club Sofa", "Rugiano", "sofa", 1000, [("brass", 50), ("leather", 33100)])
    assert r["h1"] == "Club Sofa by Rugiano" and r["rasgo"] == ""


def test_si_no_se_busca_va_el_rasgo_mas_buscado():
    rasgos = rasgos_con_volumen(["marble", "wood"], "coffee table",
                                {"marble coffee table": {"volume": 33100},
                                 "wood coffee table": {"volume": 27100}})
    r = h1_por_datos("Rock Coffee Table", "Rugiano", "coffee table", 20, rasgos)
    assert r["h1"] == "Rock Marble Coffee Table by Rugiano" and r["rasgo"] == "marble"


def test_sin_rasgo_con_volumen_queda_modelo_y_tipo():
    r = h1_por_datos("Arcadia Stool", "Cattelan Italia", "bar stool", None, [("walnut", 0)])
    assert r["h1"] == "Arcadia Bar Stool by Cattelan Italia"


CANDS = [
    {"keyword": "nomon barcelona", "origen": "gsc", "impresiones": 50},
    {"keyword": "barcelona premium wall clock", "origen": "gsc", "impresiones": 30},
    {"keyword": "modern wall clocks manufacturer nj", "origen": "gsc", "impresiones": 2},
    {"keyword": "nomon", "origen": "gsc", "impresiones": 14},
    {"keyword": "wall clock", "origen": "generica", "volumen": 60500},
    {"keyword": "nomon wall clock", "origen": "generica", "volumen": 260},
    {"keyword": "walnut wall clock", "origen": "generica", "volumen": 170},
]
TEXTO = ("Barcelona Premium Wall Clock Nomon walnut box walnut and polished brass hands "
         "fiberglass bezel")


def test_keywords_search_console_y_marca_tipo():
    sel = elegir_keywords(CANDS, nombre="Barcelona Premium Wall Clock", marca="Nomon",
                          tipo="wall clock", h1="Barcelona Premium Wall Clock by Nomon",
                          rasgo="", texto_ficha=TEXTO)
    kws = [e["keyword"] for e in sel["elegidas"]]
    # 23-nov: objetivo 3 y el tipo de producto completa, como «wall sconce» en la
    # referencia de Alex (antes: «wall clock» era «genérica de categoría»)
    assert kws == ["nomon barcelona", "nomon wall clock", "wall clock"]
    assert "nomon" not in kws                                  # la marca sola
    assert "barcelona premium wall clock" not in kws          # es el H1
    assert "modern wall clocks manufacturer nj" not in kws    # la ficha no lo dice


def test_sin_genericas_por_material():
    # Alex, 17-nov: lo que funciona es Search Console + marca y tipo
    cands = [{"keyword": "marble table", "origen": "generica", "volumen": 9900},
             {"keyword": "marble coffee table", "origen": "generica", "volumen": 33100},
             {"keyword": "rock coffee table", "origen": "gsc", "impresiones": 649}]
    sel = elegir_keywords(cands, nombre="Rock Coffee Table", marca="Rugiano",
                          tipo="coffee table", h1="Rock Marble Coffee Table by Rugiano",
                          rasgo="marble", texto_ficha="Rock Coffee Table marble top wood")
    assert [e["keyword"] for e in sel["elegidas"]] == []      # 'rock coffee table' es el nombre


def test_dandy_sin_leather_table():
    cands = [{"keyword": "leather table", "origen": "generica", "volumen": 260},
             {"keyword": "leather pool table", "origen": "generica", "volumen": 20},
             {"keyword": "vismara pool table", "origen": "generica", "volumen": 10}]
    sel = elegir_keywords(cands, nombre="Dandy Pool Table", marca="Vismara",
                          tipo="pool table", h1="Dandy Leather Pool Table by Vismara",
                          rasgo="leather", texto_ficha="Dandy pool table leather slate")
    assert [e["keyword"] for e in sel["elegidas"]] == ["vismara pool table"]


def test_el_name_va_sin_marca_porque_la_tienda_la_agrega_con_logo():
    from cassoni.h1 import nombre_para_woo
    assert nombre_para_woo("Club Sofa by Rugiano", "Rugiano") == "Club Sofa"
    assert nombre_para_woo("Rock Marble Coffee Table by Rugiano", "Rugiano") == \
        "Rock Marble Coffee Table"
    assert nombre_para_woo("Paloma Speakers", "") == "Paloma Speakers"
    assert nombre_para_woo("Hermes Bed by DV Home Collection", "DV Home Collection") == "Hermes Bed"


def test_nombre_recortado_y_simbolos_afuera():
    cands = [{"keyword": "dandy pool", "origen": "gsc", "impresiones": 9},
             {"keyword": "cruise+furniture", "origen": "gsc", "impresiones": 5},
             {"keyword": "dandy table", "origen": "gsc", "impresiones": 3}]
    sel = elegir_keywords(cands, nombre="Dandy Pool Table", marca="Vismara",
                          tipo="pool table", h1="Dandy Leather Pool Table by Vismara",
                          rasgo="leather", texto_ficha="Dandy pool table leather cruise furniture")
    assert [e["keyword"] for e in sel["elegidas"]] == ["dandy table"]


def test_generica_opcional_solo_si_es_el_material_del_h1():
    from cassoni.reglas_seo import generica_usada, genericas_opcionales
    op = genericas_opcionales(["chrome", "glass"], "dining table",
                              {"glass dining table": {"volume": 8100},
                               "chrome dining table": {"volume": 590}})
    assert [k for k, _, _ in op] == ["glass dining table", "chrome dining table"]
    assert generica_usada("A round glass dining table by Tonelli.",
                          "Bakkarat Glass Dining Table by Tonelli Design", op)[2] is True
    assert generica_usada("A chrome dining table base.",
                          "Bakkarat Glass Dining Table by Tonelli Design", op)[2] is False
    assert generica_usada("Nothing here.", "Bakkarat Glass Dining Table", op) is None
