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


# --- prueba del 13-nov: 7 de 10 fichas quedaban sin keywords por semillas malas ---
from cassoni.h1 import tipo_ee_uu                       # noqa: E402
from cassoni.investigacion import materiales_del_texto, nucleos   # noqa: E402


def test_tipo_ee_uu_tanda_13_nov():
    assert tipo_ee_uu("Salomé Valet Stand With Mirror", ["accessories", "coat-racks"]) == "valet stand"
    assert tipo_ee_uu("Cristallino for Pirelli Foosball Table",
                      ["entertainment", "game-tables", "foosball-tables"]) == "foosball table"
    assert tipo_ee_uu("Arcadia Stool", ["entertainment", "home-bar", "bar-stools"]) == "bar stool"
    assert tipo_ee_uu("Poseidon Square Bathroom Set", ["bath-counter-sets"]) == "bathroom set"
    assert tipo_ee_uu("Almeria Baskets", ["accessories", "baskets-and-storage"]) == "basket"


def test_materiales_de_la_descripcion_sin_repetir_el_general():
    m = materiales_del_texto("<p>Blown glass diffuser with a satin finish and brass details.</p>")
    assert m[:2] == ["blown glass", "brass"] and "glass" not in m


def test_semillas_usan_el_tipo_y_los_materiales_del_texto():
    s = semillas("Spear Chandelier", "VENICEM", ["Chandeliers"],
                 ("Style: Contemporary", "Dimmer: DALI, TRIAC", "Model: Spear 1"),
                 tipo="chandelier", descripcion="Frame in polished brass.")
    assert s[0] == "brass chandelier" and "contemporary chandelier" in s
    assert not any(x in " ".join(s) for x in ("dali", "triac", "spear 1"))
    assert "chandelier" not in s            # el tipo pelado abre demasiado la búsqueda
    assert semillas("Almeria Baskets", "Pinetti", ["Baskets"], (), tipo="basket",
                    descripcion="Woven regenerated leather.")[0] == "leather basket"


def test_nucleos_para_filtrar_ideas():
    assert nucleos("ceiling lamp") == ["lamp", "light"]
    assert nucleos("foosball table") == ["foosball"]
    assert nucleos("outdoor sofa") == ["sofa", "couch"]


def test_ideas_con_filtro_de_tipo(cfg):
    vistos = {}

    def fake_post(payload):
        vistos.update(payload[0])
        return {"status_code": 20000, "cost": 0.01, "tasks": [{"status_code": 20000,
                "result": [{"items": []}]}]}
    cfg.dfs_max_requests_min = 0
    DataForSEOFetcher(cfg, _post=fake_post).ideas_de_keywords(["brass lamp"],
                                                               contiene=["lamp", "light"])
    assert vistos["filters"] == [["keyword", "like", "%lamp%"], "or",
                                 ["keyword", "like", "%light%"]]


def test_motivo_idea_repuestos_y_tipo_partido():
    from cassoni.investigacion import motivo_idea
    assert "repuesto" in motivo_idea("foosball table rods", "foosball table")
    assert "parte el tipo" in motivo_idea("ceiling living room light", "ceiling lamp")
    assert motivo_idea("blown glass ceiling light", "ceiling lamp") == ""
    assert motivo_idea("glass foosball table", "foosball table") == ""
    assert motivo_idea("metal lounge chair", "lounge chair") == ""
    assert motivo_idea("walnut bar stool", "bar stool") == ""
    assert motivo_idea("stool with backrest", "bar stool") == ""
    assert motivo_idea("chair cushions", "chair") != ""


def test_la_idea_descartada_sale_con_su_motivo():
    from cassoni.keywords import elegir_keywords
    sel = elegir_keywords([{"keyword": "foosball table rods", "volume": 260,
                            "origen": "investigacion", "descartar": "busca un repuesto"}],
                          descripcion="", texto_producto="foosball table")
    assert sel["elegidas"] == []
    assert sel["descartadas"][0]["motivo"] == "busca un repuesto"


def test_motivo_idea_algo_para_el_producto():
    from cassoni.investigacion import motivo_idea
    assert "para un mirror" in motivo_idea("frame for mirror", "wall mirror")
    assert motivo_idea("mirror for living room", "wall mirror") == ""


def test_material_negado_no_cuenta():
    from cassoni.investigacion import materiales_del_texto
    assert "marble" not in materiales_del_texto("Top: Without Marble Top. Wooden structure.")
    assert materiales_del_texto("Wooden structure") == ["wood"]
