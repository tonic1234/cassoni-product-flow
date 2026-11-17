# -*- coding: utf-8 -*-
"""Criterio del SEO (documento del 6-nov-2026): candidatas, ejemplos y la regla
de oro de la prueba: la ficha propia NUNCA está entre los ejemplos."""
from cassoni.criterio_seo import (Referencia, SelectorSEO, candidatas_gsc, clave,
                                  con_volumen, ejemplos_de_redaccion, genericas)

REF = [
    {"url": "https://cassoni.com/product/a/", "nombre": "Cruise Sofa", "marca": "Talenti",
     "tipo": "outdoor sofa", "materiales": ["teak"],
     "candidatas": [{"keyword": "cruise couch", "origen": "gsc", "impresiones": 824,
                     "posicion": 4}],
     "keywords_seo": ["cruise couch"], "h1_seo": "Cruise Teak Outdoor Sofa by Talenti",
     "descripcion_seo": "SECRETO-A The Cruise couch is a three-seater outdoor sofa."},
    {"url": "https://cassoni.com/product/b/", "nombre": "Shibari Chair",
     "marca": "Visionnaire", "tipo": "armchair", "materiales": ["fabric"],
     "candidatas": [{"keyword": "shibari chairs", "origen": "gsc", "impresiones": 100,
                     "posicion": 6}],
     "keywords_seo": ["shibari chairs"], "h1_seo": "Shibari Stretch Fabric Armchair by Visionnaire",
     "descripcion_seo": "SECRETO-B A Visionnaire chair designed by Studiopepe."},
]


class FakeLLM:
    def __init__(self, respuesta):
        self.respuesta, self.prompts = respuesta, []

    def complete_json(self, system, user, **kw):
        self.prompts.append(user)
        return self.respuesta


def test_clave_une_plural_y_posesivo():
    assert clave("Cleopatra's Chair") == clave("cleopatra chair")
    assert clave("shibari chairs") == clave("shibari chair")
    assert clave("glass") == "glass"


def test_candidatas_gsc_como_las_mira_el_seo():
    filas = [
        {"keyword": "cruise couch", "impressions": 824, "position": 4.2, "volume": 90},
        {"keyword": "cruise couch company", "impressions": 167, "position": 5},
        {"keyword": "cruise sofa price", "impressions": 20, "position": 3},
        {"keyword": "shibari bondage", "impressions": 5, "position": 7},
        {"keyword": "specchio tiffany", "impressions": 4, "position": 9},
        {"keyword": "cruise teak", "impressions": 1, "position": 2},      # 1 impresión
        {"keyword": "cruise lounge", "impressions": 9, "position": 45},   # muy lejos
        {"keyword": "maxi bed", "impressions": 31, "position": 4, "volume": 10},
    ]
    kws = [c["keyword"] for c in candidatas_gsc(filas, "Cruise Sofa", "Talenti")]
    assert kws == ["cruise couch", "maxi bed"]        # sin piso de volumen


def test_genericas_solo_con_datos_de_la_ficha():
    g = genericas("Cleopatra Chair", "OAK", "dining chair",
                  ["Finish: Rosewood, Ebony"], "<p>Wooden chair with leather upholstery.</p>")
    assert "wood and leather chair" in g and "leather dining chair" in g
    assert "oak chairs" in g and "dining chair" in g
    g = genericas("Bakkarat Table", "Tonelli Design", "dining table", [],
                  "Extra clear glass top on a chrome base. Made in Italy.")
    assert "dining table in glass" in g and "glass table" in g and "italian table" in g
    assert genericas("Illan Wall Lamp", "Luceplan", "wall sconce", [], "")[:2] == [
        "wall sconce", "wall light"]


def test_con_volumen_descarta_lo_que_nadie_busca():
    out = con_volumen(["glass table", "chrome dining table", "zzz table"],
                      {"glass table": {"volume": 6600}, "chrome dining table": {"volume": 0}})
    assert out == [{"keyword": "glass table", "origen": "generica", "volumen": 6600}]


def test_la_ficha_propia_nunca_es_ejemplo():
    ref = Referencia(REF)
    llm = FakeLLM({"keywords": [{"keyword": "Cruise Couch", "por_que": "ya aparece"}]})
    sel = SelectorSEO(llm, "m", ref).elegir(REF[0], excluir_url="https://cassoni.com/product/a")
    prompt = llm.prompts[0]
    ejemplos = prompt.split("AHORA ESTA FICHA")[0]
    assert "Cruise Sofa" not in ejemplos and "Shibari Chair" in ejemplos
    assert [e["keyword"] for e in sel["elegidas"]] == ["cruise couch"]
    red = ejemplos_de_redaccion(ref, "https://cassoni.com/product/a/")
    assert "SECRETO-A" not in red and "SECRETO-B" in red


def test_el_selector_no_inventa_keywords_fuera_de_la_lista():
    ficha = {"nombre": "Shibari Chair", "marca": "Visionnaire", "tipo": "armchair",
             "candidatas": [{"keyword": "shibari chair", "origen": "gsc", "impresiones": 221},
                            {"keyword": "fabric armchair", "origen": "generica", "volumen": 320}]}
    llm = FakeLLM({"keywords": [{"keyword": "shibari chairs"},       # plural → la de la lista
                                {"keyword": "velvet armchair"},      # no está: afuera
                                {"keyword": "fabric armchair"},
                                {"keyword": "shibari chair"}]})       # repetida: afuera
    sel = SelectorSEO(llm, "m", None).elegir(ficha)
    assert [e["keyword"] for e in sel["elegidas"]] == ["shibari chair", "fabric armchair"]
    assert sel["elegidas"][1]["volume"] == 320


def test_sin_candidatas_no_llama_al_llm():
    llm = FakeLLM({})
    assert SelectorSEO(llm, "m", None).elegir({"candidatas": []}) == {
        "elegidas": [], "descartadas": []}
    assert llm.prompts == []
