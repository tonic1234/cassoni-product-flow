# -*- coding: utf-8 -*-
"""La marca del producto se lee del campo `brands` de la API (no de atributos).

Contexto medido el 13-oct-2026 sobre 150 fichas reales de cassoni.com:
  - 150/150 (100%) traen marca en `product['brands']`  →  [{'id':..,'name':'Slide',...}]
  -   0/150 (0%)  traen un atributo llamado 'marca'/'brand'
     (los atributos reales son Size, Designer, Collection, Filter by …)
El editor recibe `Marca: {brand or '(sin dato en la ficha)'}`: con la extracción
vieja recibía SIEMPRE "(sin dato en la ficha)" y por eso ningún H1 llevaba marca,
aunque la regla del cliente la pide ("marca (si aplica) + modelo + categoría").
"""
from cassoni.orchestrator import _brand_y_atributos


def test_marca_desde_el_campo_brands():
    """RED: hoy devuelve ('', ()) porque sólo mira atributos 'marca'/'brand'."""
    p = {"brands": [{"id": 68217, "name": "Slide", "slug": "slide"}], "attributes": []}
    marca, _tec = _brand_y_atributos(p)
    assert marca == "Slide"


def test_marca_desde_brands_con_entidades_html():
    p = {"brands": [{"id": 1, "name": "Adriani &amp; Rossi"}], "attributes": []}
    assert _brand_y_atributos(p)[0] == "Adriani & Rossi"


def test_sigue_funcionando_el_atributo_brand_como_respaldo():
    """Compatibilidad: si algún día la ficha no trae `brands`, se usa el atributo."""
    p = {"attributes": [{"name": "Brand", "options": ["Desalto"]}]}
    assert _brand_y_atributos(p)[0] == "Desalto"


def test_el_campo_brands_gana_sobre_el_atributo():
    p = {"brands": [{"id": 1, "name": "Slide"}],
         "attributes": [{"name": "marca", "options": ["Otra Marca"]}]}
    assert _brand_y_atributos(p)[0] == "Slide"


def test_la_marca_no_se_cuela_entre_los_atributos_tecnicos():
    p = {"brands": [{"id": 1, "name": "Slide"}],
         "attributes": [{"name": "Size", "options": ['17"3/4W']},
                        {"name": "Designer", "options": ["Italo Pertichini"]}]}
    marca, tec = _brand_y_atributos(p)
    assert marca == "Slide"
    assert tec == ('Size: 17"3/4W', "Designer: Italo Pertichini")


def test_sin_marca_no_inventa_y_no_rompe():
    for p in ({}, {"brands": []}, {"brands": None}, {"brands": [{}]},
              {"brands": [{"name": ""}]}, {"attributes": None}):
        assert _brand_y_atributos(p)[0] == ""


def test_con_varias_marcas_toma_la_primera():
    p = {"brands": [{"id": 1, "name": "Paolo Castelli"}, {"id": 2, "name": "Otra"}],
         "attributes": []}
    assert _brand_y_atributos(p)[0] == "Paolo Castelli"
