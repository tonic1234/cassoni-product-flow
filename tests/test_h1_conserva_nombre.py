# -*- coding: utf-8 -*-
"""El H1 no pierde términos del nombre (revisión de la tanda de 30, 23-nov-2026).

TARS anotó H1 que pierden códigos de modelo y ediciones. Tres causas:
- D-026 marcaba como «marca ajena» nombres que en Cassoni son modelos (Hermes Maxi,
  Tiffany): pasaban a la regla del rasgo sin motivo.
- La regla del rasgo armaba {modelo} {rasgo} {tipo} y perdía lo que va después del
  tipo («Cleopatra Chair Limited Edition» → «Cleopatra Walnut Chair»).
- Los números de modelo se borraban como código de catálogo aunque la gente los
  busque («19800 steinway piano»: 38 impresiones en posición 1,2).
"""
from cassoni.h1 import verificar_h1
from cassoni.reglas_seo import (codigos_buscados, h1_por_datos, marca_ajena_en,
                                modelo_para_h1, sufijo_del_nombre)


# --- marca ajena: solo si el modelo ES la marca ------------------------------------

def test_modelos_de_la_tienda_no_son_marca_ajena():
    for nombre, marca in [("Hermes Maxi Bed", "Cava"), ("Tiffany Dining Table", "Rugiano"),
                          ("Harley Lounge Chair", "Baxter"), ("Vespa Bar Cabinet", "Dalvivo"),
                          ("Ferrari Desk", "Formitalia"), ("Dior Armchair", "Versace Home")]:
        assert marca_ajena_en(nombre, marca) == "", nombre


def test_steinway_sigue_siendo_marca_ajena():
    assert marca_ajena_en("19800 Steinway Piano", "Riva Mobili D'Arte") == "steinway"


def test_marca_de_piano_con_modelo_propio_no_es_ajena():
    assert marca_ajena_en("Aurora Steinway Grand Piano", "Riva Mobili D'Arte") == ""


# --- lo que va después del tipo --------------------------------------------------

def test_sufijo_del_nombre():
    assert sufijo_del_nombre("Cleopatra Chair Limited Edition", "Jumbo", "chair") == "Limited Edition"
    assert sufijo_del_nombre("Club Sofa 3-Seater", "Rugiano", "sofa") == "3-Seater"
    assert sufijo_del_nombre("Rock Coffee Table", "Rugiano", "coffee table") == ""
    assert sufijo_del_nombre("Bolero Chair (SC1019)", "Jumbo", "chair") == ""
    assert sufijo_del_nombre("Arcadia Stool", "Cattelan Italia", "bar stool") == ""


def test_regla_del_rasgo_conserva_la_edicion():
    r = h1_por_datos("Cleopatra Chair Limited Edition", "Jumbo", "chair", 10,
                     [("walnut", 900)], umbral=1000)
    assert r["h1"] == "Cleopatra Walnut Chair Limited Edition by Jumbo"


def test_opciones_conservan_la_edicion():
    r = h1_por_datos("Rock Coffee Table Gold Edition", "Rugiano", "coffee table", 10,
                     [("marble", 33100), ("wood", 27100)], umbral=1000,
                     opciones=["marble", "wood"])
    assert r["h1"] == "Rock Marble Coffee Table Gold Edition by Rugiano"


# --- números de modelo que la gente busca --------------------------------------

FILAS = [{"keyword": "19800 steinway piano", "impressions": 38},
         {"keyword": "steinway piano", "impressions": 486},
         {"keyword": "sc1019", "impressions": 1}]


def test_codigos_buscados_solo_con_impresiones():
    assert codigos_buscados("19800 Steinway Piano", FILAS) == ["19800"]
    assert codigos_buscados("Bolero Chair (SC1019)", FILAS) == []


def test_modelo_para_h1_conserva_el_codigo_en_su_lugar():
    assert modelo_para_h1("19800 Steinway Piano", "Riva Mobili D'Arte", ["19800"]) == "19800 Steinway"
    assert modelo_para_h1("Steinway Piano 19800", "Riva Mobili D'Arte", ["19800"]) == "Steinway 19800"
    assert modelo_para_h1("19800 Steinway Piano", "Riva Mobili D'Arte", []) == "Steinway"


def test_h1_por_datos_con_codigo_buscado():
    r = h1_por_datos("19800 Steinway Piano", "Riva Mobili D'Arte", "piano", 27100,
                     [("mother of pearl", 110)], umbral=1000, marca_ajena="steinway",
                     codigos=["19800"])
    assert r["rasgo"] == "mother of pearl" and r["fijo"] is False
    r = h1_por_datos("19800 Steinway Piano", "Riva Mobili D'Arte", "piano", 27100, [],
                     umbral=1000, marca_ajena="steinway", codigos=["19800"])
    assert r["h1"] == "19800 Steinway Piano by Riva Mobili D'Arte"


def test_nombre_que_ya_se_busca_conserva_el_codigo_buscado():
    r = h1_por_datos("K2 Table", "Reflex", "table", 5000, [], umbral=1000, codigos=["K2"])
    assert r["h1"] == "K2 Table by Reflex"


def test_verificar_h1_acepta_el_codigo_buscado():
    h1 = "19800 Steinway Mother-of-Pearl Piano by Riva Mobili D'Arte"
    kw = dict(nombre="19800 Steinway Piano", marca="Riva Mobili D'Arte", tipo="piano",
              texto_ficha="19800 Steinway Piano mother-of-pearl inlays")
    assert any("códigos" in i for i in verificar_h1(h1, **kw))
    assert not any("códigos" in i for i in verificar_h1(h1, **kw, codigos_permitidos=["19800"]))
