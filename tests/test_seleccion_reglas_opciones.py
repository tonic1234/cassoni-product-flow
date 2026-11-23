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
    p.competidores = None
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
    assert "19800 steinway piano" in [e["keyword"] for e in sel["elegidas"]]


HERMES_DESC = ("<p>Part of the Italian Hermes collection, this double bed is offered with a "
               "multilayer structure covered with non-deformable polyurethane foam.</p><p>The "
               "upholstery is offered in a wide range of fabric or leather options and the large "
               "headboard features a refined vertical quilting. Made in Italy.</p>")
CLUB_DESC = ("<p>This is a designer Italian Sofa, part of the exclusive Club collection. It stands "
             "out for the innovative structure created by refined brushed brass or bronze drawn "
             "tubes that, combined with the upholstered leather or fabric, create a stylish "
             "pattern. Made in Italy.</p>")


def test_hermes_el_tapizado_no_decide_el_h1_como_alex():
    pipe = _pipe({"leather king bed": 1000, "fabric king bed": 480})
    ctx = _ctx("Hermes Maxi Bed", "DV Home Collection", "king bed", HERMES_DESC, [])
    sel = pipe._seleccion_reglas("u", {}, ctx)
    assert ctx["h1_fijo"] == ""                       # «Upholstered» lo pone el redactor
    assert set(ctx["opciones"]) == {"fabric", "leather"}   # la descripción cubre las dos
    assert not any(e["origen"] == "opcion" for e in sel["elegidas"])


def test_club_sofa_dos_grupos_no_tocan_h1_ni_keywords():
    pipe = _pipe({"club sofa": 1000, "leather sofa": 40500, "brass sofa": 90})
    ctx = _ctx("Club Sofa", "Rugiano", "sofa", CLUB_DESC,
               [{"keyword": "club couch", "impressions": 40, "position": 6},
                {"keyword": "club style sofa", "impressions": 25, "position": 7}])
    sel = pipe._seleccion_reglas("u", {}, ctx)
    assert ctx["h1_fijo"] == "Club Sofa by Rugiano"
    kws = [e["keyword"] for e in sel["elegidas"]]
    assert "club couch" in kws and "club style sofa" in kws
    assert not any(e["origen"] == "opcion" for e in sel["elegidas"])


def test_hermes_maxi_no_es_marca_ajena_y_su_nombre_manda():
    pipe = _pipe({"hermes maxi bed": 1300})
    ctx = _ctx("Hermes Maxi Bed", "Cava", "bed", "<p>A leather bed.</p>", [])
    pipe._seleccion_reglas("u", {}, ctx)
    assert ctx["h1_fijo"] == "Hermes Maxi Bed by Cava"


def test_controles_rechazan_un_h1_que_pierde_la_edicion():
    from cassoni.redactor import controles
    ficha = {"nombre": "Cleopatra Chair Limited Edition", "marca": "Jumbo", "tipo": "chair",
             "modelo": "Cleopatra", "sufijo": "Limited Edition", "codigos": [],
             "descripcion": "<p>Cleopatra chair in walnut, limited edition.</p>",
             "atributos": [], "categorias": [], "medidas": []}
    malo = {"h1": "Cleopatra Walnut Chair by Jumbo", "description": "<p>x</p>"}
    bueno = {"h1": "Cleopatra Walnut Chair Limited Edition by Jumbo", "description": "<p>x</p>"}
    assert any("Limited Edition" in i for i in controles(ficha, malo, []))
    assert not any("Limited Edition" in i for i in controles(ficha, bueno, []))


def test_la_competencia_completa_hasta_tres_en_la_seleccion():
    pipe = _pipe({"frog coffee table": 30, "glass coffee table": 22200})
    pipe.competidores = object()
    pipe.cfg.relleno_keywords = "competencia"      # apagada por defecto desde el 23-nov
    pipe._con_volumen = lambda filas: filas
    pipe._paginas_competidores = lambda ctx: (
        [{"url": "https://otra.com/frog"}],
        [{"keyword": "modern glass coffee table", "volume": 1900, "competidores": 2},
         {"keyword": "curved glass coffee table", "volume": 320, "competidores": 2},
         {"keyword": "coffee table", "volume": 301000, "competidores": 3}])
    ctx = _ctx("Frog Coffee Table", "Sovet Italia", "coffee table",
               "<p>Frog coffee table with a tempered glass top and a curved glass base. Modern design.</p>",
               [{"keyword": "frog table", "impressions": 40, "position": 5}])
    sel = pipe._seleccion_reglas("u", {}, ctx)
    assert [e["keyword"] for e in sel["elegidas"]] == [
        "frog table", "modern glass coffee table", "curved glass coffee table"]
    assert sel["competidores_leidos"] == [{"url": "https://otra.com/frog"}]


def test_las_sugerencias_completan_hasta_tres_por_defecto():
    pipe = _pipe({"frog coffee table": 30, "glass coffee table": 22200})
    pipe._sugerencias = lambda ctx: [
        {"keyword": "frog coffee table", "volume": 30},                 # repite el nombre
        {"keyword": "curved glass coffee table", "volume": 320},
        {"keyword": "modern glass coffee table", "volume": 1900},
        {"keyword": "frog legs recipe", "volume": 9900}]                  # ruido
    ctx = _ctx("Frog Coffee Table", "Sovet Italia", "coffee table",
               "<p>Frog coffee table with a tempered glass top and a curved glass base. Modern design.</p>",
               [{"keyword": "frog table", "impressions": 40, "position": 5}])
    sel = pipe._seleccion_reglas("u", {}, ctx)
    assert [e["keyword"] for e in sel["elegidas"]] == [
        "frog table", "modern glass coffee table", "curved glass coffee table"]
    assert sel["elegidas"][1]["origen"] == "sugerencia"
