# -*- coding: utf-8 -*-
"""Selección de las 3 keywords objetivo (regla SEO 3-nov-2026)."""
from cassoni.keywords import elegir_keywords

DESC = "<p>Elegant leather sofa with oak legs.</p>"
PRODUCTO = "Pedro Sofa Sofas Cassoni Material: Leather"


def _kw(k, vol=None, impr=100):
    return {"keyword": k, "volume": vol, "impressions": impr}


def _elegir(cands, **kw):
    base = dict(descripcion=DESC, texto_producto=PRODUCTO)
    base.update(kw)
    return elegir_keywords(cands, **base)


def test_descarta_las_que_ya_estan_en_la_descripcion():
    out = _elegir([_kw("leather sofa", 900), _kw("pedro chesterfield", 100)])
    assert [e["keyword"] for e in out["elegidas"]] == ["pedro chesterfield"]
    assert any(d["motivo"] == "ya está en la descripción" for d in out["descartadas"])


def test_ordena_por_volumen():
    out = _elegir([_kw("pedro modular", 50), _kw("sofa chesterfield", 900),
                   _kw("leather recliner", 300)])
    assert [e["keyword"] for e in out["elegidas"]] == \
        ["sofa chesterfield", "leather recliner", "pedro modular"]


def test_maximo_tres():
    out = _elegir([_kw("sofa alpha", 100), _kw("leather beta", 90),
                   _kw("pedro gamma", 80), _kw("cassoni delta", 70)])
    assert len(out["elegidas"]) == 3 and out["faltan"] == 0


def test_volumen_bajo_se_descarta_pero_sin_dato_vale_la_demanda_de_gsc():
    out = _elegir([_kw("pedro tufted", 5), _kw("sofa velvet", None, impr=80),
                   _kw("leather nuevo", None, impr=3)], min_volume=10)
    assert [e["keyword"] for e in out["elegidas"]] == ["sofa velvet"]


def test_no_relevantes_afuera():
    out = _elegir([_kw("geef foto", 9000)])
    assert out["elegidas"] == [] and out["faltan"] == 3


def test_una_por_palabra_compartida():
    out = _elegir([_kw("sofa chesterfield", 900), _kw("sofa modular", 800)])
    assert [e["keyword"] for e in out["elegidas"]] == ["sofa chesterfield"]


def test_canibalizacion_con_h1_de_hermanas_y_categoria():
    out = _elegir([_kw("sofas", 9000), _kw("pedro chesterfield", 100),
                   _kw("belinda sofa", 500)],
                  h1_hermanas=["Belinda Sofa"], categorias=["Sofas"])
    assert [e["keyword"] for e in out["elegidas"]] == ["pedro chesterfield"]


def test_ya_escrita_en_otra_ficha_solo_si_no_queda_otra():
    asignadas = {"sofa chesterfield": "https://x/otra"}
    out = _elegir([_kw("sofa chesterfield", 900), _kw("pedro modular", 50)],
                  asignadas=asignadas)
    kws = {e["keyword"]: e for e in out["elegidas"]}
    # se completa con la compartida, pero marcada
    assert kws["sofa chesterfield"]["compartida_con"] == "https://x/otra"
    assert "pedro modular" in kws


def test_ya_escrita_no_entra_si_sobran_alternativas():
    asignadas = {"sofa chesterfield": "https://x/otra"}
    out = _elegir([_kw("sofa chesterfield", 900), _kw("pedro modular", 50),
                   _kw("leather recliner", 40), _kw("cassoni lounge", 30)],
                  asignadas=asignadas)
    assert "sofa chesterfield" not in [e["keyword"] for e in out["elegidas"]]
