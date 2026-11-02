# -*- coding: utf-8 -*-
"""La página de la muestra: que no salga a medias ni con marcadores sin completar."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.generar_muestra import generar  # noqa: E402


def _ficha(nombre="Club Sofa", aprobado=True):
    return {
        "url": "https://cassoni.com/product/x/", "nombre": nombre, "slug": "x",
        "categorias": ["Sofas & Sectionals"], "marca": "Rugiano", "imagen": "",
        "atributos": ["Size: 122\"W", "Collection: New Glamour Collection"],
        "gsc": {"keyword": "club sofa", "position": 7.466, "impressions": 1360,
                "clicks": 0, "opportunity": "materialize_demand", "score": 80},
        "h1_antes": "Club Sofa", "h1_despues": "Rugiano Club Sofa",
        "desc_antes": "<p>Texto original.</p>",
        "desc_despues": "<p>Texto original. Ampliado.</p>",
        "medido": {"palabras_antes": 54, "palabras_despues": 211,
                   "conservacion": 1.0, "h2": 2},
        "validacion": {"aprobado": aprobado, "issues": ["observación"] if not aprobado else []},
        "intentos": 1, "costo": {"usd": 0.0207, "tokens_in": 8400, "tokens_out": 1800},
    }


def test_genera_una_tarjeta_por_ficha():
    html = generar([_ficha("Uno"), _ficha("Dos", aprobado=False)])
    assert html.count('<article class="ficha">') == 2
    assert "Uno" in html and "Dos" in html


def test_no_quedan_marcadores_sin_completar():
    html = generar([_ficha()])
    for resto in ("{f.get", "{i:02d}", "{len(filas)}", "{usd:"):
        assert resto not in html


def test_muestra_el_antes_y_el_despues():
    html = generar([_ficha()])
    assert "Club Sofa" in html and "Rugiano Club Sofa" in html
    assert "conservación del original" in html


def test_un_rechazo_se_ve_como_rechazo():
    html = generar([_ficha(aprobado=False)])
    assert "Rechazada por el validador" in html
    assert "Observaciones del validador" in html


def test_el_costo_aparece_por_ficha_y_en_total():
    html = generar([_ficha(), _ficha()])
    assert "US$ 0.0207" in html          # por ficha
    assert "US$ 0.04" in html            # total (0.0414 redondeado)


def test_declara_los_limites():
    html = generar([_ficha()])
    assert "No edita la descripción corta" in html
    assert "No publica" in html
