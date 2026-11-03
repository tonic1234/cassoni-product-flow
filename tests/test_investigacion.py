# -*- coding: utf-8 -*-
"""Investigación de keywords: las que la ficha TODAVÍA no atrae (SEO, 3-nov-2026).

GSC solo trae búsquedas por las que la ficha ya aparece (casi siempre su
nombre, que el H1 nuevo ya cubre). El valor está en tipo + material/acabado/
estilo que la ficha tiene y la gente busca."""
from cassoni.investigacion import semillas, tipo_compuesto, valores_de_atributos
from cassoni.keywords import elegir_keywords
from cassoni.dataforseo import DataForSEOFetcher

ATTRS_ROCK = ("Collection: New Glamour Collection", "Style: Glamour",
              'Size: 20"W x 21"5/8D x 14"1/8H', "Filter by Typology: Coffee Table",
              "Filter by Base Material: Metal", "Filter by Top Material: Wood, Marble",
              "Filter by Top Shape: Irregular")


def test_tipo_compuesto():
    assert tipo_compuesto("Rock Coffee Table") == "coffee table"
    assert tipo_compuesto("Cleopatra Chair (SC1019)") == "chair"
    assert tipo_compuesto("Illan Wall Lamp") == "wall lamp"
    assert tipo_compuesto("Club Sofa") == "club sofa"


def test_valores_sin_medidas_ni_colecciones_ni_ruido():
    v = valores_de_atributos(ATTRS_ROCK + ("Filter by Backrest Height: High",
                                           "Filter by Base Type: Legs"))
    assert v == ["glamour", "metal", "wood", "marble", "irregular"]


def test_semillas_reales():
    s = semillas("Rock Coffee Table", "Rugiano", ["Coffee & Side Tables"], ATTRS_ROCK)
    assert "marble coffee table" in s and "metal coffee table" in s
    assert "rugiano coffee table" in s
    assert not any("20" in x or "collection" in x for x in s)
    out = semillas("Cruise Teak Sofa", "Talenti", ["Outdoor Sofas"], ("Material: Teak",))
    assert "outdoor teak sofa" in out and "outdoor sofa" in out


def test_lee_la_respuesta_de_keyword_ideas(cfg):
    def fake_post(payload):
        assert payload[0]["keywords"] == ["marble coffee table"]
        return {"status_code": 20000, "cost": 0.0123, "tasks": [{"status_code": 20000, "result": [{
            "items": [{"keyword": "black marble coffee table",
                       "keyword_info": {"search_volume": 2400, "cpc": 1.1},
                       "keyword_properties": {"keyword_difficulty": 22},
                       "search_intent_info": {"main_intent": "commercial"}}]}]}]}
    cfg.dfs_max_requests_min = 0
    f = DataForSEOFetcher(cfg, _post=fake_post)
    out = f.ideas_de_keywords(["Marble Coffee Table", "marble coffee table"])
    assert out == [{"keyword": "black marble coffee table", "volume": 2400, "cpc": 1.1,
                    "difficulty": 22, "intent": "commercial", "origen": "investigacion"}]
    assert f.costo_usd == 0.0123


def _idea(k, vol, kd=20, intent="commercial"):
    return {"keyword": k, "volume": vol, "difficulty": kd, "intent": intent,
            "origen": "investigacion"}


def _elegir(cands):
    return elegir_keywords(cands, descripcion="<p>The Rock coffee table with marble top.</p>",
                           texto_producto="Rock Coffee Table Rugiano Coffee & Side Tables "
                                          "Top Material: Wood, Marble Base Material: Metal",
                           texto_especifico="Rock Coffee Table Rugiano Top Material: Wood, "
                                            "Marble Base Material: Metal",
                           nombre="Rock Coffee Table", marca="Rugiano",
                           categorias=["Coffee & Side Tables"], min_volume=50)


def test_las_ideas_con_material_de_la_ficha_entran_por_volumen():
    out = _elegir([_idea("marble coffee table", 9900, kd=45),
                   _idea("metal and wood coffee table", 1300), _idea("wood coffee table", 6600)])
    kws = [e["keyword"] for e in out["elegidas"]]
    assert "wood coffee table" in kws and "marble coffee table" in kws


def test_filtros_de_las_ideas():
    out = _elegir([_idea("how to style a marble coffee table", 900, intent="informational"),
                   _idea("glass coffee table", 40000),             # la ficha no es de vidrio
                   _idea("marble coffee table set", 5000, kd=85),  # muy competida
                   _idea("metal coffee table", 30)])               # bajo el piso
    motivos = {d["keyword"]: d["motivo"] for d in out["descartadas"]}
    assert "informativa" in motivos["how to style a marble coffee table"]
    assert "material" in motivos["glass coffee table"]
    assert "competida" in motivos["marble coffee table set"]
    assert "volumen" in motivos["metal coffee table"]
    assert out["elegidas"] == []
