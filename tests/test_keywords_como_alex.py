# -*- coding: utf-8 -*-
"""Todo tipo de keyword que usa Alex en su referencia, el agente también lo puede usar
(decisión del 23-nov). Con sus fichas reales: candidatas guardadas y su H1."""
import json
import re
from pathlib import Path

from cassoni.reglas_seo import elegir_keywords

RAIZ = Path(__file__).resolve().parent.parent
REFS = {f["nombre"].split()[0].lower(): f for f in
        json.loads((RAIZ / "evidencia/referencia-seo.json").read_text(encoding="utf-8"))}
ORIG = {f["url"]: re.sub("<[^>]+>", " ", f.get("descripcion_original") or "") for f in
        json.loads((RAIZ / "evidencia/2026-11-17-control-reglas3.json").read_text(encoding="utf-8"))["fichas"]}


def _elegir(clave, **extra):
    r = REFS[clave]
    texto = " ".join([r["nombre"], r["marca"], ORIG[r["url"]]])
    return [e["keyword"] for e in elegir_keywords(
        r["candidatas"], nombre=r["nombre"], marca=r["marca"], tipo=r["tipo"], h1=r["h1_seo"],
        rasgo="", texto_ficha=texto, **extra)["elegidas"]]


def test_tiffany_la_variante_del_nombre():
    # «tiffany mirrors» y «tiffany mirror» cuentan como la misma (plural)
    assert {"tiffany mirror", "tiffany mirrors"} & set(_elegir("tiffany"))


def test_shibari_variantes_con_las_mismas_palabras_cuentan_una():
    kws = _elegir("shibari")
    assert "chair shibari" not in kws and "shibari chairs" in kws
    # Alex eligió «visionnaire chair»; el agente, «shibari furniture» (mismas impresiones,
    # nombra el modelo). No se fuerza una regla para una sola ficha.


def test_illan_el_tipo_de_producto_completa():
    kws = _elegir("illan")
    # mínimo 3, más si son coherentes: las tres de Alex están
    assert {"luceplan illan", "wall sconce", "wall light"} <= set(kws) and len(kws) <= 5


def test_steinway_italian_mas_tipo_si_la_ficha_dice_italy():
    assert "italian piano" in _elegir("19800", marca_ajena="steinway")


def test_nunca_el_tipo_suelto_de_una_palabra():
    for clave in REFS:
        kws = _elegir(clave, marca_ajena="steinway" if clave == "19800" else "")
        assert not {"piano", "sofa", "couch", "table", "chair", "armchair", "bed"} & set(kws), clave


def test_club_sofa_sigue_como_alex():
    assert set(_elegir("club")) == {"club style sofa", "club couch", "rugiano sofa"}


def test_cruise_reserva_lugar_para_la_generica_del_h1():
    r = REFS["cruise"]
    texto = " ".join([r["nombre"], r["marca"], ORIG[r["url"]]])
    sel = elegir_keywords(r["candidatas"], nombre=r["nombre"], marca=r["marca"], tipo=r["tipo"],
                          h1="Cruise Teak Outdoor Sofa by Talenti", rasgo="", texto_ficha=texto,
                          lugares_reservados=1)
    kws = [e["keyword"] for e in sel["elegidas"]]
    from cassoni.reglas_seo import MAX_KEYWORDS
    assert len(kws) <= MAX_KEYWORDS - 1                  # queda el lugar de la genérica del H1


def test_el_tipo_de_categoria_no_entra():
    for clave in ("rock", "bakkarat"):
        kws = _elegir(clave)
        assert "coffee table" not in kws and "dining table" not in kws, clave


def test_con_poco_texto_el_techo_es_el_minimo():
    from cassoni.reglas_seo import MIN_KEYWORDS, MAX_KEYWORDS, techo_de_keywords
    assert techo_de_keywords("Wooden chair with leather upholstery. Rosewood, Ebony or Citronier finish.") == MIN_KEYWORDS
    assert techo_de_keywords(" ".join(["word"] * 60)) == MAX_KEYWORDS


def test_sin_tipo_no_se_cae():
    sel = elegir_keywords([{"keyword": "windsor mirror", "origen": "gsc", "impresiones": 200}],
                          nombre="Windsor", marca="DV Home Collection", tipo="", h1="Windsor by DV Home Collection",
                          rasgo="", texto_ficha="Windsor, made in Italy")
    assert isinstance(sel["elegidas"], list)
