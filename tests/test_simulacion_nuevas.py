# -*- coding: utf-8 -*-
"""Fallas encontradas al simular 10 fichas nuevas (23-nov-2026)."""
from cassoni.reglas_seo import elegir_keywords


def test_lounger_y_lounge_chair_son_el_mismo_producto():
    cands = [{"keyword": "therapy lounge chair", "origen": "gsc", "impresiones": 140}]
    sel = elegir_keywords(cands, nombre="Wellness Therapy Lounger", marca="Varaschin", tipo="lounger",
                          h1="Wellness Therapy Fabric Lounger by Varaschin", rasgo="",
                          texto_ficha="Wellness Therapy Lounger Varaschin wellness therapy and SPA")
    assert "therapy lounge chair" in [e["keyword"] for e in sel["elegidas"]]


def test_orden_invertido_del_nombre_no_entra():
    cands = [{"keyword": "couch windsor", "origen": "gsc", "impresiones": 50},
             {"keyword": "sofa windsor", "origen": "gsc", "impresiones": 50}]
    sel = elegir_keywords(cands, nombre="Windsor Sofa", marca="Arketipo", tipo="sofa",
                          h1="Windsor Sofa by Arketipo", rasgo="", texto_ficha="Windsor Sofa Arketipo")
    assert sel["elegidas"] == []
    assert all("invertido" in d["motivo"] for d in sel["descartadas"])


def test_tercera_de_search_console_si_falta_para_el_minimo():
    cands = [{"keyword": k, "origen": "gsc", "impresiones": i} for k, i in
             (("isla sofa", 30), ("isla sectional sofa", 20), ("ditre isla sofa", 10))]
    sel = elegir_keywords(cands, nombre="Isla Sectional", marca="Ditre Italia", tipo="sectional",
                          h1="Isla Sectional by Ditre Italia", rasgo="",
                          texto_ficha="Isla Sectional Ditre Italia sofa sectional")
    assert len(sel["elegidas"]) == 3


def test_generica_de_otro_material_no_rechaza_la_ficha():
    from cassoni.redactor import controles
    ficha = {"nombre": "Soul Bed", "marca": "Turri", "tipo": "bed", "modelo": "Soul",
             "h1_fijo": "Soul Bed by Turri", "descripcion": "<p>Soul bed in wood by Turri.</p>",
             "atributos": [], "categorias": [], "medidas": [],
             "genericas_opcionales": [("wood bed", 5400, "wood")]}
    red = {"h1": "Soul Bed by Turri", "description": "<p>The Soul is a wood bed by Turri.</p>"}
    assert not any("genérica" in i for i in controles(ficha, red, []))


def test_el_nombre_tal_cual_completa_el_minimo_si_el_h1_no_lo_repite():
    cands = [{"keyword": "windsor mirror", "origen": "gsc", "impresiones": 210}]
    sel = elegir_keywords(cands, nombre="Windsor Mirror", marca="DV Home Collection", tipo="mirror",
                          h1="Windsor Stainless Steel Mirror by DV Home Collection", rasgo="",
                          texto_ficha="Windsor Mirror DV Home Collection")
    assert "windsor mirror" in [e["keyword"] for e in sel["elegidas"]]


def test_el_nombre_no_desplaza_cuando_ya_hay_tres():
    import json, re
    from pathlib import Path
    raiz = Path(__file__).resolve().parent.parent
    r = next(f for f in json.loads((raiz / "evidencia/referencia-seo.json").read_text(encoding="utf-8"))
             if f["nombre"].startswith("Rock"))
    opciones = [{"keyword": "marble table", "origen": "opcion", "volumen": 9900},
                {"keyword": "wood table", "origen": "opcion", "volumen": 22200}]
    sel = elegir_keywords(r["candidatas"], nombre=r["nombre"], marca=r["marca"], tipo=r["tipo"],
                          h1="Rock Marble Coffee Table by Rugiano", rasgo="marble",
                          texto_ficha="Rock Coffee Table Rugiano marble wood", opciones=opciones)
    assert "rock coffee table" not in [e["keyword"] for e in sel["elegidas"]]
