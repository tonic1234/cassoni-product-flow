# -*- coding: utf-8 -*-
"""Devoluciones del 18-nov-2026 sobre las reglas del SEO:

- Rock: la tapa viene en mármol o en madera. El H1 lleva la opción más buscada
  («Rock Marble Coffee Table») y la descripción cubre LAS DOS, con una genérica de
  cada una («marble coffee table», «wood coffee table»).
- Steinway: el volumen de «steinway piano» es el de la marca Steinway, no el de esta
  pieza de Riva Mobili D'Arte. Un nombre que es marca ajena + tipo no cuenta como
  «el nombre ya se busca». La búsqueda de la marca SÍ puede ser keyword: Alex usa
  «steinway and sons pianos» en su referencia (23-nov).
"""
from cassoni.reglas_seo import (elegir_keywords, h1_por_datos, keywords_de_opciones,
                                marca_ajena_en, opciones_de_material)

ROCK = ("The Italian Rock coffee table features a stylish shaped top available in Decoro "
        "decorated painted wood or in a wide range of marble options. This versatile low "
        "table, available in two different sizes, has two refined legs made of bronzed "
        "brass metal.")


# --- opciones de material -------------------------------------------------------

def test_rock_la_tapa_viene_en_madera_o_marmol():
    assert set(opciones_de_material(ROCK, ["marble", "brass", "wood"])) == {"wood", "marble"}


def test_un_material_fijo_y_otro_de_la_pata_no_son_opciones():
    texto = "A marble top on a brass base. The legs are in bronzed brass."
    assert opciones_de_material(texto, ["marble", "brass"]) == []


def test_opciones_con_barra_y_comas():
    texto = "Upholstered in leather or velvet, with a walnut frame."
    assert set(opciones_de_material(texto, ["leather", "velvet", "walnut"])) == {"leather", "velvet"}


def test_or_entre_oraciones_distintas_no_cuenta():
    texto = "The top is in marble. Or you can pair it with the wood sideboard."
    assert opciones_de_material(texto, ["marble", "wood"]) == []


def test_h1_con_opciones_lleva_la_mas_buscada_y_queda_fijo():
    r = h1_por_datos("Rock Coffee Table", "Rugiano", "coffee table", 480,
                     [("marble", 33100), ("brass", 90), ("wood", 27100)],
                     umbral=1000, opciones=["wood", "marble"])
    assert r["h1"] == "Rock Marble Coffee Table by Rugiano"
    assert r["rasgo"] == "marble" and r["fijo"] is True
    assert "opción más buscada" in r["regla"]


def test_si_el_nombre_ya_se_busca_manda_el_nombre_aunque_haya_opciones():
    r = h1_por_datos("Club Sofa", "Rugiano", "sofa", 1300, [("leather", 33100), ("velvet", 9000)],
                     umbral=1000, opciones=["leather", "velvet"])
    assert r["h1"] == "Club Sofa by Rugiano"


def test_keywords_de_opciones_una_por_opcion_con_volumen():
    vol = {"marble coffee table": {"volume": 33100}, "wood coffee table": {"volume": 27100}}
    kws = keywords_de_opciones(["wood", "marble"], "coffee table", vol)
    assert [k["keyword"] for k in kws] == ["marble coffee table", "wood coffee table"]
    assert all(k["origen"] == "opcion" for k in kws)


def test_keywords_de_opciones_sin_volumen_quedan_afuera():
    vol = {"marble coffee table": {"volume": 33100}, "wood coffee table": {"volume": 10}}
    kws = keywords_de_opciones(["wood", "marble"], "coffee table", vol)
    assert [k["keyword"] for k in kws] == ["marble coffee table"]


def test_elegir_keywords_suma_las_de_opciones_despues_de_search_console():
    cands = [{"keyword": "rugiano coffee table", "origen": "gsc", "impresiones": 4, "volumen": 10},
             {"keyword": "rugiano coffee table", "origen": "generica", "volumen": 10}]
    opciones = [{"keyword": "marble coffee table", "origen": "opcion", "volumen": 33100},
                {"keyword": "wood coffee table", "origen": "opcion", "volumen": 27100}]
    sel = elegir_keywords(cands, nombre="Rock Coffee Table", marca="Rugiano",
                          tipo="coffee table", h1="Rock Marble Coffee Table by Rugiano",
                          rasgo="marble", texto_ficha="Rock Rugiano " + ROCK, opciones=opciones)
    assert [e["keyword"] for e in sel["elegidas"]] == [
        "rugiano coffee table", "marble coffee table", "wood coffee table"]


# --- marca ajena en el nombre ---------------------------------------------------

def test_steinway_es_marca_ajena_para_riva():
    assert marca_ajena_en("19800 Steinway Piano", "Riva Mobili D'Arte") == "steinway"


def test_la_marca_propia_no_es_ajena():
    assert marca_ajena_en("Steinway Model D", "Steinway") == ""


def test_un_nombre_comun_no_es_marca_ajena():
    assert marca_ajena_en("Club Sofa", "Rugiano") == ""


def test_steinway_el_volumen_del_nombre_no_cuenta():
    r = h1_por_datos("19800 Steinway Piano", "Riva Mobili D'Arte", "piano", 27100,
                     [("mother of pearl", 110)], umbral=1000, marca_ajena="steinway")
    assert r["rasgo"] == "mother of pearl"
    assert "marca" in r["regla"] and "steinway" in r["regla"]


def test_la_busqueda_de_la_marca_ajena_puede_ser_keyword():
    # «piano steinway» queda afuera por orden invertido (23-nov); la marca sigue valiendo
    cands = [{"keyword": "steinway and sons piano", "origen": "gsc", "impresiones": 18, "volumen": 27100},
             {"keyword": "piano steinway", "origen": "gsc", "impresiones": 300, "volumen": 27100},
             {"keyword": "19800 steinway piano", "origen": "gsc", "impresiones": 38, "volumen": 50}]
    sel = elegir_keywords(cands, nombre="19800 Steinway Piano", marca="Riva Mobili D'Arte",
                          tipo="piano", h1="Mother-of-Pearl Steinway Piano by Riva Mobili D'Arte",
                          rasgo="mother of pearl",
                          texto_ficha="19800 Steinway Piano mother-of-pearl piano",
                          marca_ajena="steinway")
    kws = [e["keyword"] for e in sel["elegidas"]]
    assert "steinway and sons piano" in kws and "piano steinway" not in kws


def test_steinway_and_sons_como_alex():
    cands = [{"keyword": "steinway & sons piano", "origen": "gsc", "impresiones": 22, "volumen": 27100},
             {"keyword": "steinway and sons piano", "origen": "gsc", "impresiones": 18, "volumen": 27100},
             {"keyword": "19800 steinway piano", "origen": "gsc", "impresiones": 38, "volumen": 50}]
    sel = elegir_keywords(cands, nombre="19800 Steinway Piano", marca="Riva Mobili D'Arte",
                          tipo="piano", h1="Mother-of-Pearl Steinway Piano by Riva Mobili D'Arte",
                          rasgo="mother of pearl", texto_ficha="19800 Steinway Piano mother-of-pearl",
                          marca_ajena="steinway")
    kws = [e["keyword"] for e in sel["elegidas"]]
    assert "steinway and sons piano" in kws and "steinway & sons piano" not in kws


def test_la_marca_ajena_sola_no_es_keyword():
    cands = [{"keyword": "steinway and sons", "origen": "gsc", "impresiones": 22, "volumen": 6600},
             {"keyword": "steinway and sons piano", "origen": "gsc", "impresiones": 18, "volumen": 27100},
             {"keyword": "19800 steinway piano", "origen": "gsc", "impresiones": 38, "volumen": 50}]
    sel = elegir_keywords(cands, nombre="19800 Steinway Piano", marca="Riva Mobili D'Arte",
                          tipo="piano", h1="Mother-of-Pearl Steinway Piano by Riva Mobili D'Arte",
                          rasgo="mother of pearl", texto_ficha="19800 Steinway Piano mother-of-pearl",
                          marca_ajena="steinway")
    kws = [e["keyword"] for e in sel["elegidas"]]
    assert kws == ["19800 steinway piano", "steinway and sons piano"]
