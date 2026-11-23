# -*- coding: utf-8 -*-
"""El H1 no pierde términos del nombre (revisión de la tanda de 30, 23-nov-2026).

TARS anotó H1 que pierden códigos de modelo y ediciones. Tres causas:
- D-026 marcaba como «marca ajena» nombres que en Cassoni son modelos (Hermes Maxi,
  Tiffany): pasaban a la regla del rasgo sin motivo.
- La regla del rasgo armaba {modelo} {rasgo} {tipo} y perdía lo que va después del
  tipo («Cleopatra Chair Limited Edition» → «Cleopatra Walnut Chair»).

Los códigos de catálogo SÍ se van: Alex los saca en su referencia («Cleopatra Wood
and Leather Dining Chair», sin SC1019; «… Mother-of-Pearl Steinway Piano», sin 19800).
"""
from cassoni.reglas_seo import h1_por_datos, marca_ajena_en, sufijo_del_nombre


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


# --- códigos de catálogo: afuera, como en la referencia de Alex ------------------

def test_sin_codigos_de_catalogo_como_alex():
    r = h1_por_datos("Cleopatra Chair (SC1019)", "OAK", "chair", 10, [], umbral=1000)
    assert "SC1019" not in r["h1"]
    r = h1_por_datos("19800 Steinway Piano", "Riva Mobili D'Arte", "piano", 27100, [],
                     umbral=1000, marca_ajena="steinway")
    assert r["h1"] == "Steinway Piano by Riva Mobili D'Arte"


def test_nombre_que_ya_se_busca_sin_codigo():
    r = h1_por_datos("Club Sofa (CL01)", "Rugiano", "sofa", 1000, [], umbral=1000)
    assert r["h1"] == "Club Sofa by Rugiano"
