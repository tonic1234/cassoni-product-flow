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


# --- 23-nov, después del control real ----------------------------------------------
from cassoni.reglas_seo import h1_por_datos, rasgo_combinado  # noqa: E402

CLEO_DESC = "Wooden chair with leather upholstery. Rosewood, Ebony or Citronier finish."


def test_cleopatra_rasgo_combinado_en_el_orden_del_texto():
    r = rasgo_combinado(CLEO_DESC, ["rosewood", "leather", "ebony", "wood"], "dining chair", CLEOPATRA)
    assert r == ("wood and leather", 1300)


def test_cleopatra_h1_como_alex():
    comb = rasgo_combinado(CLEO_DESC, ["rosewood", "leather", "ebony", "wood"], "dining chair", CLEOPATRA)
    r = h1_por_datos("Cleopatra Chair (SC1019)", "OAK", "dining chair", 320,
                     [("leather", 9900), ("wood", 9900)], umbral=1000, combinado=comb)
    assert r["h1"] == "Cleopatra Wood and Leather Dining Chair by OAK" and r["fijo"] is True


def test_materiales_en_opcion_no_son_combinacion():
    texto = "Coffee table with a top in wood or marble."
    assert rasgo_combinado(texto, ["wood", "marble"], "coffee table",
                           _vol(wood_and_marble_table=720)) is None


def test_combinacion_sin_volumen_no_va():
    assert rasgo_combinado(CLEO_DESC, ["wood", "leather"], "dining chair", _vol()) is None


def test_solo_la_primera_oracion_define_el_producto():
    texto = "A refined armchair. The legs are in brass and the seat in velvet."
    assert rasgo_combinado(texto, ["brass", "velvet"], "armchair",
                           _vol(brass_and_velvet_armchair=500)) is None


def test_illan_la_generica_que_repite_el_h1_no_cuenta():
    ops = genericas_opcionales(["aluminum", "wood"], "wall sconce",
                               _vol(wood_wall_sconce=1900, wood_sconce=1300))
    assert [k for k, _, _ in genericas_para_h1("Illan Wood Wall Sconce by Luceplan", ops)] == ["wood sconce"]


def test_la_generica_del_h1_fijo_ocupa_un_lugar_de_tres():
    from cassoni.reglas_seo import elegir_keywords
    cands = [{"keyword": k, "origen": "gsc", "impresiones": i, "volumen": 20} for k, i in
             [("cleopatra chair design", 27), ("cleopatra wooden chair", 15)]] + \
            [{"keyword": "oak dining chair", "origen": "generica", "volumen": 2400}]
    sel = elegir_keywords(cands, nombre="Cleopatra Chair (SC1019)", marca="OAK", tipo="dining chair",
                          h1="Cleopatra Wood and Leather Dining Chair by OAK", rasgo="wood and leather",
                          texto_ficha="Cleopatra OAK wooden chair design with leather",
                          genericas_h1=[{"keyword": "wood and leather chair", "origen": "generica",
                                         "volumen": 1300}])
    kws = [e["keyword"] for e in sel["elegidas"]]
    assert len(kws) == 3 and "wood and leather chair" in kws and "oak dining chair" not in kws


def test_redactor_sabe_el_nombre_completo_de_la_marca_ajena():
    from cassoni.redactor import _bloque_marca_ajena
    b = _bloque_marca_ajena({"marca_ajena": "steinway", "marca": "Riva Mobili D'Arte"})
    assert "Steinway And Sons" in b or "Steinway and Sons" in b.replace("And", "and")
    assert _bloque_marca_ajena({"marca_ajena": ""}) == ""
