# -*- coding: utf-8 -*-
"""Modo reescritura (devolución SEO 6-nov-2026): H1 v3, intención en Google,
controles de la descripción reescrita y el ciclo redactor → validador."""
import json
from pathlib import Path

import pytest

from cassoni.checklist import check_reescritura, numeros_sin_respaldo
from cassoni.config import Config
from cassoni.h1 import (es_codigo, h1_respaldo, modelo_de, sin_codigos, tipo_ee_uu,
                        verificar_h1)
from cassoni.intencion import veredicto
from cassoni.keywords import cubierta_por_el_h1, elegir_keywords, tipo_de_producto
from cassoni.redactor import medidas_ee_uu
from cassoni.validator import Validator

SERPS = json.loads((Path(__file__).parent.parent / "evidencia" /
                    "2026-11-11-serps-calibracion.json").read_text())


# --- H1 v3 ------------------------------------------------------------------
@pytest.mark.parametrize("nombre,esperado", [
    ("Cleopatra Chair (SC1019)", "Cleopatra Chair"),
    ("19800 Steinway Piano", "Steinway Piano"),
    ("Floyd 3-Seater Sofa", "Floyd 3-Seater Sofa"),     # no es un código
    ("Sofa (Large)", "Sofa (Large)"),
])
def test_sin_codigos(nombre, esperado):
    assert sin_codigos(nombre) == esperado


def test_es_codigo():
    assert es_codigo("SC1019") and es_codigo("SC_1019") and es_codigo("19800")
    assert not es_codigo("3-Seater") and not es_codigo("2")


@pytest.mark.parametrize("nombre,ruta,atributos,tipo", [
    ("Bakkarat Table", ["furniture", "dining-room", "fixed-tables"], [], "dining table"),
    ("Cruise Sofa", ["outdoor", "living-area", "sofas-sectionals-living-area"], [],
     "outdoor sofa"),
    ("Illan Wall Lamp", ["lighting", "wall-lamps-sconces"], [], "wall sconce"),
    ("Tiffany  Mirror", ["accessories", "mirrors"],
     ["Filter by Base Type (Mirrors): Wall-mounted"], "wall mirror"),
    ("Shibari Chair", ["furniture", "dining-room", "chairs-armchairs"],
     ["Filter by Armrest: With Armrests"], "armchair"),
    ("Cleopatra Chair (SC1019)", ["furniture", "dining-room", "chairs-armchairs"],
     ["Filter by Armrest: Armless"], "dining chair"),
    ("Hermes Maxi Bed", ["furniture", "bedroom", "double-beds"],
     ["Filter by Bed Size: King"], "king bed"),
    ("Club Sofa", ["furniture", "living-room", "sofas-sectionals"], [], "sofa"),
    ("Rock Coffee Table", ["furniture", "living-room", "coffee-side-tables"], [],
     "coffee table"),
    ("Anamon", ["outdoor", "umbrellas-sunshades"], [], "outdoor parasol"),
])
def test_tipo_ee_uu(nombre, ruta, atributos, tipo):
    assert tipo_ee_uu(nombre, ruta, atributos) == tipo


def test_h1_respaldo_y_modelo():
    assert modelo_de("Club Sofa", "Rugiano") == "Club"
    assert modelo_de("Hermes Maxi Bed", "DV Home Collection") == "Hermes Maxi"
    assert h1_respaldo("Cleopatra Chair (SC1019)", "OAK", "dining chair") == \
        "Cleopatra Dining Chair by OAK"
    assert h1_respaldo("19800 Steinway Piano", "Riva", "piano") == "Steinway Piano by Riva"


def test_verificar_h1_acepta_rasgos_de_la_ficha():
    ficha = "Bakkarat Table Filter by Top Shape: Round Top Material: Glass extra clear glass"
    assert verificar_h1("Bakkarat Round Glass Dining Table by Tonelli Design",
                        nombre="Bakkarat Table", marca="Tonelli Design",
                        tipo="dining table", texto_ficha=ficha) == []


def test_verificar_h1_rechaza_lo_inventado_codigos_y_falta_de_tipo():
    ficha = "Steinway Piano carvings mother-of-pearl"
    issues = verificar_h1("Grand 19800 Steinway Piano by Riva", nombre="19800 Steinway Piano",
                          marca="Riva", tipo="piano", texto_ficha=ficha)
    assert any("códigos" in i for i in issues)
    assert any("grand" in i for i in issues)
    assert verificar_h1("Hand-Carved Mother-of-Pearl Steinway Piano by Riva",
                        nombre="19800 Steinway Piano", marca="Riva", tipo="piano",
                        texto_ficha="refined carvings, hand-applied mother-of-pearl") == []
    sin_tipo = verificar_h1("Rock Marble by Rugiano", nombre="Rock Coffee Table",
                            marca="Rugiano", tipo="coffee table", texto_ficha="marble")
    assert any("qué es" in i for i in sin_tipo)
    sin_marca = verificar_h1("Rock Coffee Table", nombre="Rock Coffee Table",
                             marca="Rugiano", tipo="coffee table", texto_ficha="")
    assert any("by Rugiano" in i for i in sin_marca)


def test_marca_mas_tipo_no_la_cubre_el_h1():
    assert not cubierta_por_el_h1("rugiano sofas", "Club Sofa", "Rugiano")
    assert cubierta_por_el_h1("club sofa", "Club Sofa", "Rugiano")
    assert cubierta_por_el_h1("luceplan illan", "Illan Wall Lamp", "Luceplan")


def test_variante_forzada_se_descarta():
    sel = elegir_keywords([{"keyword": "table in glass", "volume": 6600,
                            "origen": "competidor"}],
                          descripcion="", texto_producto="Bakkarat Table glass",
                          nombre="Bakkarat Table", marca="Tonelli",
                          texto_ficha="Bakkarat Table glass")
    assert sel["elegidas"] == []
    assert "variante forzada" in sel["descartadas"][0]["motivo"]


# --- intención en Google (calibrado con 16 SERP reales) ----------------------
@pytest.mark.parametrize("kw,nombre,cats,texto,ok", [
    ("wood table", "Rock Coffee Table", ["Coffee & Side Tables"], "wood marble", False),
    ("marble table", "Rock Coffee Table", ["Coffee & Side Tables"], "wood marble", False),
    ("decorative wall mirror", "Tiffany Mirror", ["Mirrors"], "mirror metal", False),
    ("tiffany style mirrors", "Tiffany Mirror", ["Mirrors"], "natural mirror frame", False),
    ("cruise couch", "Cruise Sofa", ["Sofas & Sectionals"], "teak outdoor", False),
    ("cleopatra's chair", "Cleopatra Chair", ["Chairs & Armchairs"], "wood leather", False),
    ("table in glass", "Bakkarat Table", ["Fixed Tables"], "glass", False),
    ("club couch", "Club Sofa", ["Sofas & Sectionals"], "brass", True),
    ("teak outdoor sofa", "Cruise Sofa", ["Sofas & Sectionals"], "teak outdoor", True),
    ("rugiano sofas", "Club Sofa", ["Sofas & Sectionals"], "rugiano", True),
    ("visionnaire chair", "Shibari Chair", ["Chairs & Armchairs"], "visionnaire", True),
    ("hermes bed frame", "Hermes Maxi Bed", ["Double Beds"], "upholstered", True),
])
def test_veredicto_coincide_con_el_seo(kw, nombre, cats, texto, ok):
    v = veredicto(kw, SERPS[kw], tipo_de_producto(nombre, cats), f"{nombre} {texto}")
    assert v["ok"] is ok, v


def test_veredicto_sin_resultados_no_descarta():
    assert veredicto("x sofa", [], {"sofa"})["ok"]


# --- descripción reescrita ---------------------------------------------------
def test_medidas_ee_uu():
    assert medidas_ee_uu(['Size: 102"5/8W x 33"1/2D x 28"H, 122"W x 33"1/2D x 28"H']) == \
        ['102 5/8" W x 33 1/2" D x 28" H', '122" W x 33 1/2" D x 28" H']
    assert medidas_ee_uu(["Style: Glamour"]) == []


def test_numeros_inventados():
    fuentes = 'Size: 102"5/8W x 33"1/2D. LED 2700K, 1,265 lumens'
    assert numeros_sin_respaldo('<p>33 1/2" deep, 2700K, 1265 lm</p>', fuentes) == []
    assert numeros_sin_respaldo("<p>It seats 6 and is 40 deep</p>", fuentes) == ["40", "6"]


_DESC = ("<p>The Rock is a marble coffee table by Rugiano with an irregular top on two "
         "bronzed brass legs. Made in Italy.</p><h2>TWO TOPS</h2><ul><li>Marble top in "
         "several marbles, from Travertino to Calacatta Gold.</li><li>A hand-painted wood "
         "top in the Decoro technique.</li></ul><h2>WHICH SIZE</h2><p>The large sizes are "
         "11\" high, for a low sofa. The small one is 14 1/8\" high and works as a side table "
         "next to an armchair. See all <a href=\"https://cassoni.com/c/\">coffee tables</a>. "
         "Choose the marble first, then the size that fits your sofa and your room.</p>")


def test_check_reescritura_ok_y_fallas():
    fuentes = 'Size: 20"W x 14"1/8H, 46"W x 11"H'
    ok = check_reescritura({"description": _DESC}, keywords=["marble coffee table"],
                           fuentes=fuentes, url_categoria="https://cassoni.com/c/")
    assert ok == [], ok
    mal = check_reescritura({"description": _DESC.replace("14 1/8", "15").replace(
        "https://cassoni.com/c/", "https://otro.com/")}, keywords=["teak sofa"],
        fuentes=fuentes, url_categoria="https://cassoni.com/c/")
    texto = " | ".join(mal)
    assert "15" in texto and "otro.com" in texto and "teak sofa" in texto


# --- ciclo redactor → validador ----------------------------------------------
class _FakeRedactor:
    def __init__(self, salidas):
        self.salidas, self.feedbacks = list(salidas), []

    def redactar(self, *, ficha, keywords, feedback=None):
        self.feedbacks.append(feedback)
        return dict(self.salidas.pop(0))


class _FakeLLM:
    def __init__(self, aprueba=True):
        self.aprueba = aprueba

    def complete_json(self, system, user, **kw):
        return {"aprobado": self.aprueba, "issues": [] if self.aprueba else ["dato x"]}


_FICHA = {"url": "u", "nombre": "Rock Coffee Table", "marca": "Rugiano", "modelo": "Rock",
          "tipo": "coffee table", "categorias": ["Furniture"],
          "url_categoria": "https://cassoni.com/c/",
          "atributos": ['Size: 20"W x 14"1/8H, 46"W x 11"H', "Top Material: Wood, Marble"],
          "medidas": [], "descripcion": "Rock coffee table, irregular top, brass legs, Italian "
          "marble Travertino Calacatta Gold, Decoro painted wood", "corta": "",
          "mismo_nombre": [], "h1_respaldo": "Rock Coffee Table by Rugiano"}


def test_redactar_y_validar_rebota_con_los_motivos_y_aprueba():
    v = Validator(Config(env="staging"), _FakeLLM(True))
    malo = {"h1": "Rock Grand Coffee Table by Rugiano", "description": _DESC}
    bueno = {"h1": "Rock Marble Coffee Table by Rugiano", "description": _DESC}
    red = _FakeRedactor([malo, bueno])
    res = v.redactar_y_validar(ficha=_FICHA, keywords=[], redactor=red)
    assert res["aprobado"] and res["intentos"] == 2
    assert any("grand" in f for f in red.feedbacks[1])


def test_redactar_y_validar_usa_el_h1_de_respaldo_si_el_redactor_no_acierta():
    v = Validator(Config(env="staging"), _FakeLLM(True))
    malo = {"h1": "Rock Grand Coffee Table by Rugiano", "description": _DESC}
    res = v.redactar_y_validar(ficha=_FICHA, keywords=[],
                               redactor=_FakeRedactor([malo, malo, malo]))
    assert res["aprobado"]
    assert res["edited"]["h1"] == "Rock Coffee Table by Rugiano"
    assert res["edited"]["h1_respaldo_usado"]


def test_nucleo_al_final():
    from cassoni.keywords import nucleo_al_final
    tipos = {"mirror", "piano", "bed", "table"}
    assert not nucleo_al_final("mirror home", tipos, "Tiffany Mirror", "DV")
    assert not nucleo_al_final("piano italian", tipos, "Steinway Piano", "Riva")
    assert nucleo_al_final("hermes bed frame", tipos, "Hermes Maxi Bed", "DV")
    assert nucleo_al_final("marble coffee table", tipos, "Rock Coffee Table", "Rugiano")
    assert nucleo_al_final("luceplan illan", {"lamp"}, "Illan Wall Lamp", "Luceplan")


def test_en_reescritura_la_keyword_del_modelo_puede_ir_en_la_descripcion():
    filas = [{"keyword": "shibari chairs", "impressions": 300, "position": 6, "volume": 90}]
    kw = dict(descripcion="", texto_producto="Shibari Chair Visionnaire",
              nombre="Shibari Chair", marca="Visionnaire",
              texto_ficha="Shibari Chair Visionnaire fabric")
    assert elegir_keywords(filas, **kw)["elegidas"] == []
    assert [e["keyword"] for e in elegir_keywords(filas, reescritura=True, **kw)["elegidas"]] \
        == ["shibari chairs"]


def test_variantes_y_sinonimos_en_reescritura():
    from cassoni.keywords import acumula_sinonimos, clave_variante
    assert clave_variante("A Club Sofas") == clave_variante("club sofa") == "club sofa"
    assert acumula_sinonimos("wall light fixture sconce")
    assert not acumula_sinonimos("table lamp") and not acumula_sinonimos("hermes bed frame")
    filas = [{"keyword": "club sofa", "volume": 900, "impressions": 50, "position": 9},
             {"keyword": "club sofas", "volume": 300, "impressions": 20, "position": 9},
             {"keyword": "a club sofa", "volume": 100, "impressions": 5, "position": 9}]
    sel = elegir_keywords(filas, descripcion="", texto_producto="Club Sofa Rugiano brass",
                          nombre="Club Sofa", marca="Rugiano", reescritura=True,
                          texto_ficha="Club Sofa Rugiano brass")
    assert [e["keyword"] for e in sel["elegidas"]] == ["club sofa"]
