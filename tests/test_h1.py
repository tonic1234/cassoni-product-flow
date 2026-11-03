# -*- coding: utf-8 -*-
"""H1 por plantilla '{Nombre} by {Marca}' (equipo SEO, 3-nov-2026)."""
from cassoni.h1 import h1_plantilla


def test_nombre_by_marca():
    assert h1_plantilla("Tufty-Time Sofa", "B&B Italia") == ("Tufty-Time Sofa by B&B Italia", "")


def test_es_idempotente():
    h1, _ = h1_plantilla("Tufty-Time Sofa", "Slide")
    assert h1_plantilla(h1, "Slide") == (h1, "")


def test_no_duplica_si_ya_termina_en_by_marca_con_otra_caja():
    assert h1_plantilla("Club Sofa BY rugiano", "Rugiano")[0] == "Club Sofa by Rugiano"


def test_la_marca_adelante_pasa_al_final():
    assert h1_plantilla("Slide Tufty-Time Sofa", "Slide")[0] == "Tufty-Time Sofa by Slide"
    assert h1_plantilla("Rugiano - Club Sofa", "Rugiano")[0] == "Club Sofa by Rugiano"


def test_no_corta_palabras_que_empiezan_como_la_marca():
    assert h1_plantilla("Slider Chair", "Slide")[0] == "Slider Chair by Slide"


def test_sin_marca_queda_el_nombre_y_avisa():
    h1, aviso = h1_plantilla("Pedro Sofa", "")
    assert h1 == "Pedro Sofa" and "sin marca" in aviso


def test_entidades_html_y_espacios():
    assert h1_plantilla("Pedro&nbsp; Sofa &amp; Ottoman", "Cassoni")[0] == \
        "Pedro Sofa & Ottoman by Cassoni"


def test_sin_nombre():
    assert h1_plantilla("", "Slide") == ("", "la ficha no tiene nombre")
