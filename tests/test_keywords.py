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


def test_descarta_errores_de_tipeo():
    """Prueba real 3-nov: 'rock coffe table' terminó escrito en la ficha."""
    from cassoni.keywords import parece_typo
    assert parece_typo("rock coffe table", "Rock Coffee Table Rugiano")
    assert not parece_typo("rock coffee table", "Rock Coffee Table Rugiano")
    assert not parece_typo("marble coffee table", "Rock Coffee Table Rugiano")
    out = _elegir([_kw("pedro leathr", 900)])
    assert out["descartadas"][0]["motivo"] == "parece un error de tipeo"


def test_la_categoria_se_separa_en_partes():
    """Prueba real 3-nov: 'sectionals' (74.000/mes) en la ficha de un club sofa
    de la categoría 'Sofas & Sectionals'."""
    out = _elegir([_kw("sectionals", 74000), _kw("pedro chesterfield", 100)],
                  categorias=["Sofas & Sectionals"])
    assert [e["keyword"] for e in out["elegidas"]] == ["pedro chesterfield"]


def test_genericas_de_categoria_afuera_si_no_nombran_el_producto():
    from cassoni.keywords import es_especifica
    cats = ["Sofas & Sectionals"]
    assert not es_especifica("leather sofas", "Club Sofa Rugiano Material: Brass", cats)
    assert es_especifica("club sofa", "Club Sofa Rugiano Material: Brass", cats)
    assert es_especifica("brass sofa", "Club Sofa Rugiano Material: Brass", cats)
    out = _elegir([_kw("leather sofas", 9000), _kw("pedro leather", 50)],
                  texto_especifico="Pedro Sofa Cassoni Material: Oak",
                  categorias=["Sofas"])
    assert [e["keyword"] for e in out["elegidas"]] == ["pedro leather"]


def test_tipeo_sin_falsos_positivos():
    from cassoni.keywords import parece_typo
    assert not parece_typo("what is a club sofa", "Club Sofa Rugiano")
    assert not parece_typo("steinway grand piano", "19800 Steinway Piano Riva Mobili D'Arte")
    assert not parece_typo("club sofas", "Club Sofa Rugiano")          # plural
    assert parece_typo("club sofs", "Club Sofa Rugiano")


def test_tiene_que_nombrar_el_producto_o_un_atributo():
    """Prueba real 3-nov: 'hermes brand' (Hermès), 'illan meslier stats' (un
    arquero), 'shibari bondage' en una silla, 'cruise chairs' en un sofá."""
    from cassoni.keywords import elegir_keywords
    cands = [_kw("hermes brand", 2900), _kw("maxi home", 320), _kw("hermes bed", 90),
             _kw("velvet headboard", 50)]
    out = elegir_keywords(cands, descripcion="<p>x</p>",
                          texto_producto="Hermes Maxi Bed DV Home Beds Upholstery: Velvet",
                          texto_especifico="Hermes Maxi Bed DV Home Upholstery: Velvet",
                          nombre="Hermes Maxi Bed", marca="DV Home", categorias=["Beds"])
    kws = [e["keyword"] for e in out["elegidas"]]
    assert "hermes brand" not in kws and "maxi home" not in kws
    assert "hermes bed" in kws and "velvet headboard" in kws


def test_palabras_sensibles_afuera_siempre():
    out = _elegir([_kw("shibari bondage", 2400)])
    assert out["elegidas"] == []
    from cassoni.keywords import elegir_keywords
    out = elegir_keywords([_kw("shibari bondage", 2400)], descripcion="",
                          texto_producto="Shibari Chair Visionnaire")
    assert out["descartadas"][0]["motivo"] == "contenido sensible"


def test_sinonimos_del_tipo():
    from cassoni.keywords import nombra_el_tipo, tipo_de_producto
    t = tipo_de_producto("Cruise Teak Sofa Talenti", ["Outdoor Sofas"])
    assert nombra_el_tipo("cruise couch", t)
    assert not nombra_el_tipo("cruise chairs", t)
    assert "chair" in tipo_de_producto("Cleopatra Chair (SC1019)")
