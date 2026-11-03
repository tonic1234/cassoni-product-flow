# -*- coding: utf-8 -*-
"""Herramientas de la revisión para SEO: exportar y meter en la landing."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from exportar_revision import bloques, competidores, descartadas  # noqa: E402
from landing_con_revision import inyectar  # noqa: E402

ORIG = "<h2>Design</h2><p>Soft rounded volumes. Made in Italy.</p>"
EDIT = "<h2>Design</h2><p>Soft rounded volumes. A modular seating piece. Made in Italy.</p>"


def test_marca_solo_las_oraciones_agregadas():
    b = bloques(EDIT, ORIG)
    assert b[0] == {"tipo": "h2", "frases": [{"t": "Design", "nueva": False}]}
    assert [f["nueva"] for f in b[1]["frases"]] == [False, True, False]


def test_sin_edicion_nada_es_nuevo():
    assert not any(f["nueva"] for bl in bloques(ORIG, ORIG) for f in bl["frases"])


def test_lee_descartadas_y_competidores_de_la_traza():
    sel = ("elegidas: club sofa (gsc, vol 880) | competidores: https://a.com/p, https://b.com/q"
           " | descartadas: geef foto (no es de este producto); sofas (compite con la página de categoría)")
    assert competidores(sel) == ["https://a.com/p", "https://b.com/q"]
    assert descartadas(sel) == [{"keyword": "geef foto", "motivo": "no es de este producto"},
                                {"keyword": "sofas", "motivo": "compite con la página de categoría"}]


def test_el_json_no_puede_cerrar_el_script():
    html = '<script type="application/json" id="revision-data">{}</script><script>x()</script>'
    out = inyectar(html, {"fichas": [{"t": "</script><script>alert(1)</script>"}]})
    assert out.count("</script>") == 2
    assert "<\\/script>" in out


def test_valor_cuenta_lo_que_aporta_el_h1_y_las_keywords():
    import json
    from exportar_revision import valor
    fila = {"original_h1": "Illan Wall Lamp", "status": "processed",
            "gsc_keywords": json.dumps([
                {"keyword": "luceplan illan", "impressions": 120},
                {"keyword": "illan luceplan", "impressions": 30},
                {"keyword": "illan wall lamp", "impressions": 400},   # el H1 viejo ya la cubría
                {"keyword": "designer wall sconces", "impressions": 9}]),
            "selected_keywords": json.dumps([{"keyword": "contemporary wall lamp", "volume": 880},
                                             {"keyword": "led wall sconce", "volume": 1300}])}
    v = valor(fila, "Luceplan")
    assert [b["keyword"] for b in v["h1_busquedas"]] == ["luceplan illan", "illan luceplan"]
    assert v["h1_impresiones"] == 150
    assert v["volumen_nuevo"] == 2180
    assert valor(dict(fila, status="rejected"), "Luceplan")["volumen_nuevo"] == 0
