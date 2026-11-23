# -*- coding: utf-8 -*-
"""Genéricas cortas como en la referencia de Alex (23-nov-2026).

Alex nunca dijo «nunca marble table»: marcó dos errores de DeepSeek, «marble table» en
Palatial (esa versión no tiene mármol) y «leather table» en Dandy (es una mesa de
pool: quien busca «leather table» quiere otro producto). En su referencia usa
genéricas cortas del material del H1 con el tipo corto:
  Rock      «marble table», «wood table»        (la tapa: mármol o madera)
  Bakkarat  «dining table in glass», «glass table» (no repite «Glass Dining Table»)
  Cleopatra «wood and leather chair»            (el H1 dice «Wood and Leather»)
"""
from cassoni.reglas_seo import (cabeza_de, genericas_opcionales, genericas_para_h1,
                                keywords_de_opciones)


def _vol(**kw):
    return {k.replace("_", " "): {"volume": v} for k, v in kw.items()}


BAKKARAT = _vol(glass_dining_table=8100, dining_table_in_glass=8100, glass_table=6600,
                chrome_table=880, chrome_dining_table=590, chrome_and_glass_table=210,
                glass_and_chrome_table=210)
CLEOPATRA = _vol(wood_chair=18100, leather_chair=14800, leather_dining_chair=9900,
                 wood_dining_chair=9900, leather_and_wood_chair=1300,
                 wood_and_leather_chair=1300, rosewood_chair=170, ebony_chair=170)


def test_cabeza_del_tipo():
    assert cabeza_de("coffee table") == "table"
    assert cabeza_de("outdoor sofa") == "sofa"
    assert cabeza_de("pool table") == ""          # una mesa de pool no es una «table»
    assert cabeza_de("armchair") == "armchair"


def test_rock_opciones_en_forma_corta():
    vol = _vol(marble_coffee_table=33100, wood_coffee_table=27100, wood_table=22200,
               marble_table=9900)
    kws = keywords_de_opciones(["wood", "marble"], "coffee table", vol)
    assert {k["keyword"] for k in kws} == {"marble table", "wood table"}


def test_opcion_sin_forma_corta_usa_la_larga():
    vol = _vol(marble_coffee_table=33100, wood_coffee_table=27100)
    kws = keywords_de_opciones(["wood", "marble"], "coffee table", vol)
    assert {k["keyword"] for k in kws} == {"marble coffee table", "wood coffee table"}


def test_bakkarat_como_alex():
    ops = genericas_opcionales(["chrome", "glass"], "dining table", BAKKARAT)
    elegidas = genericas_para_h1("Bakkarat Round Glass Dining Table by Tonelli Design", ops)
    assert [k for k, _, _ in elegidas] == ["dining table in glass", "glass table"]


def test_cleopatra_la_combinacion_del_h1():
    ops = genericas_opcionales(["rosewood", "leather", "ebony", "wood"], "dining chair", CLEOPATRA)
    elegidas = genericas_para_h1("Cleopatra Wood and Leather Dining Chair by OAK", ops)
    assert [k for k, _, _ in elegidas] == ["wood and leather chair"]


def test_sin_material_en_el_h1_no_hay_generica():
    ops = genericas_opcionales(["leather", "fabric"], "king bed",
                               _vol(leather_bed=1900, fabric_bed=1000, leather_king_bed=1000))
    assert genericas_para_h1("Hermes Maxi Upholstered King Bed by DV Home Collection", ops) == []


def test_palatial_sin_marmol_no_tiene_marble_table():
    # la versión no tiene mármol: no está entre sus materiales, no hay genérica
    ops = genericas_opcionales(["wood", "gold leaf"], "dining table",
                               _vol(marble_table=9900, wood_table=22200))
    assert not any("marble" in k for k, _, _ in ops)


def test_dandy_mesa_de_pool_no_da_leather_table():
    ops = genericas_opcionales(["leather", "slate"], "pool table",
                               _vol(leather_table=1000, leather_pool_table=50))
    assert "leather table" not in [k for k, _, _ in ops]


def test_no_repite_el_h1_tal_cual():
    ops = genericas_opcionales(["fabric"], "armchair", _vol(fabric_armchair=320))
    assert genericas_para_h1("Shibari Stretch Fabric Armchair by Visionnaire", ops) == []
