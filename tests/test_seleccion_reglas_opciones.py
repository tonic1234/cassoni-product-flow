# -*- coding: utf-8 -*-
"""_seleccion_reglas con las dos fichas reales de la devolución del 18-nov
(descripciones tal cual de evidencia/2026-11-17-control-reglas3.json)."""
from cassoni.config import Config
from cassoni.orchestrator import Pipeline

ROCK_DESC = ("<p>The Italian Rock coffee table features a stylish shaped top available in "
             "Decoro decorated painted wood or in a wide range of marble options. This "
             "versatile low table, available in two different sizes, has two refined legs "
             "made of bronzed brass metal. An innovative and functional coffee table to "
             "complement sophisticated sofas. Designed by Rugiano. Made in Italy.</p>\n")
PIANO_DESC = ("<p>Piano of extraordinary elegance that is a true masterpiece of fine "
              "craftsmanship. The hand-carved decorations embody timeless artistry. The "
              "surface is embellished with mother-of-pearl inlays, a noble and luminous "
              "material. Made in Italy.</p>\n")


class _Vol:
    def __init__(self, vol):
        self.vol = vol

    def obtener(self, consultas):
        return {k: {"volume": v} for k, v in self.vol.items() if k in consultas}


def _pipe(vol):
    p = object.__new__(Pipeline)
    p.cfg = Config(env="staging")
    p.volumenes = _Vol(vol)
    p._genericas = lambda product: []
    return p


def _ctx(nombre, marca, tipo, desc, kw_rows):
    return {"nombre": nombre, "marca": marca, "tipo": tipo, "atributos": (),
            "categorias": (), "desc_orig": desc, "kw_rows": kw_rows}


def test_rock_h1_marmol_y_keywords_de_las_dos_tapas():
    pipe = _pipe({"rock coffee table": 480, "marble coffee table": 33100,
                  "wood coffee table": 27100, "brass coffee table": 1600})
    ctx = _ctx("Rock Coffee Table", "Rugiano", "coffee table", ROCK_DESC,
               [{"keyword": "rock coffee table", "impressions": 649, "position": 4.8},
                {"keyword": "rugiano coffee table", "impressions": 4, "position": 2}])
    sel = pipe._seleccion_reglas("u", {}, ctx)
    assert ctx["h1_fijo"] == "Rock Marble Coffee Table by Rugiano"
    assert set(ctx["opciones"]) == {"wood", "marble"}
    assert ctx["genericas_opcionales"] == []
    kws = [e["keyword"] for e in sel["elegidas"]]
    assert "marble coffee table" in kws and "wood coffee table" in kws


def test_steinway_el_h1_no_queda_en_el_nombre_de_la_marca():
    pipe = _pipe({"steinway piano": 27100, "mother of pearl piano": 110})
    ctx = _ctx("19800 Steinway Piano", "Riva Mobili D'Arte", "piano", PIANO_DESC,
               [{"keyword": "steinway piano", "impressions": 486, "position": 4.8},
                {"keyword": "piano steinway", "impressions": 120, "position": 6},
                {"keyword": "19800 steinway piano", "impressions": 38, "position": 1.2}])
    sel = pipe._seleccion_reglas("u", {}, ctx)
    assert ctx["h1_fijo"] == ""                       # el redactor pone el rasgo
    assert ctx["h1_rasgos"] == [("mother of pearl", 110)]
    assert "steinway" in ctx["h1_regla"]
    assert [e["keyword"] for e in sel["elegidas"]] == ["19800 steinway piano"]
