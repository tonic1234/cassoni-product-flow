# -*- coding: utf-8 -*-
"""Con las reglas del 17-nov, las keywords de la competencia (el mismo producto en hasta 3
competidores, DataForSEO ranked_keywords) se consultaban en la precarga pero nunca
llegaban a la elección. Ahora completan hasta 3, después de lo que Alex prioriza (23-nov)."""
from cassoni.reglas_seo import candidatas_de_competencia, elegir_keywords

FROG = "Frog Glass Coffee Table by Sovet Italia"
TEXTO_FROG = "Frog coffee table Sovet Italia with a tempered glass top and a curved glass base. Modern design."


def _c(kw, vol, n=1):
    return {"keyword": kw, "volume": vol, "competidores": n, "origen": "competidor"}


def test_filtra_y_ordena_las_de_la_competencia():
    rank = [_c("coffee table", 301000, 3), _c("glass coffee table", 22200, 1),
            _c("curved glass coffee table", 320, 2), _c("professional coffee table", 90, 2),
            _c("frog glass coffee table", 30, 1), _c("modern glass coffee table", 1900, 2),
            _c("glass table", 6600, 1), _c("sovet frog", 20, 1), _c("glass lamp", 8100, 2)]
    out = [c["keyword"] for c in candidatas_de_competencia(rank, h1=FROG, nombre="Frog Coffee Table",
                                                           marca="Sovet Italia", tipo="coffee table",
                                                           texto_ficha=TEXTO_FROG)]
    # más competidores primero; afuera: el tipo suelto, lo que la ficha no dice, lo que
    # repite el H1, otro tipo de producto y sin volumen suficiente
    assert out == ["modern glass coffee table", "curved glass coffee table", "glass table"]


def test_dandy_no_da_leather_table_aunque_la_rankee_la_competencia():
    rank = [_c("leather table", 1000, 2), _c("leather pool table", 90, 2)]
    out = [c["keyword"] for c in candidatas_de_competencia(
        rank, h1="Dandy Leather Pool Table by Vismara", nombre="Dandy Pool Table", marca="Vismara",
        tipo="pool table", texto_ficha="Dandy pool table covered in leather, slate top")]
    assert out == []        # «leather pool table» repite el H1; «leather table» es otro producto


def test_rellena_solo_los_lugares_libres():
    gsc = [{"keyword": "frog table", "origen": "gsc", "impresiones": 40, "volumen": 30}]
    comp = [{"keyword": "modern glass coffee table", "origen": "competidor", "volumen": 1900, "competidores": 2},
            {"keyword": "curved glass coffee table", "origen": "competidor", "volumen": 320, "competidores": 2},
            {"keyword": "glass table", "origen": "competidor", "volumen": 6600, "competidores": 1}]
    sel = elegir_keywords(gsc, nombre="Frog Coffee Table", marca="Sovet Italia", tipo="coffee table",
                          h1=FROG, rasgo="glass", texto_ficha=TEXTO_FROG + " table", competencia=comp)
    kws = [e["keyword"] for e in sel["elegidas"]]
    # mínimo 3, más si son coherentes (23-nov): entran las tres de la competencia
    assert kws == ["frog table", "modern glass coffee table", "curved glass coffee table", "glass table"]
    assert sel["elegidas"][1]["por_que"].startswith("la rankean 2 competidores")


def test_con_el_techo_lleno_no_entra_la_competencia():
    gsc = [{"keyword": k, "origen": "gsc", "impresiones": 40, "volumen": 30}
           for k in ("frog table", "frog glass table")]
    marca = [{"keyword": "sovet italia coffee table", "origen": "generica", "volumen": 50}]
    from cassoni.reglas_seo import MAX_KEYWORDS
    comp = [{"keyword": "modern glass coffee table", "origen": "competidor", "volumen": 1900, "competidores": 3}]
    sel = elegir_keywords(gsc + marca, nombre="Frog Coffee Table", marca="Sovet Italia",
                          tipo="coffee table", h1=FROG, rasgo="glass",
                          texto_ficha=TEXTO_FROG + " table", competencia=comp,
                          lugares_reservados=MAX_KEYWORDS - 3)
    assert "modern glass coffee table" not in [e["keyword"] for e in sel["elegidas"]]


# --- objetivo 3, mínimo 2 (23-nov): se afloja el umbral, nunca la coherencia ---------

def test_con_una_sola_se_afloja_el_volumen_de_la_competencia():
    gsc = [{"keyword": "frog table", "origen": "gsc", "impresiones": 40, "volumen": 30}]
    comp = [{"keyword": "curved glass coffee table", "origen": "competidor", "volumen": 20, "competidores": 1}]
    sel = elegir_keywords(gsc, nombre="Frog Coffee Table", marca="Sovet Italia", tipo="coffee table",
                          h1=FROG, rasgo="glass", texto_ficha=TEXTO_FROG + " table", competencia=comp)
    assert [e["keyword"] for e in sel["elegidas"]] == ["frog table", "curved glass coffee table"]
    assert "mínimo de 3" in sel["elegidas"][1]["por_que"]


def test_con_tres_no_entra_la_de_poco_volumen():
    gsc = [{"keyword": "frog table", "origen": "gsc", "impresiones": 40, "volumen": 30}]
    comp = [{"keyword": "modern glass coffee table", "origen": "competidor", "volumen": 1900, "competidores": 2},
            {"keyword": "glass table", "origen": "competidor", "volumen": 6600, "competidores": 1},
            {"keyword": "curved glass coffee table", "origen": "competidor", "volumen": 20, "competidores": 3}]
    sel = elegir_keywords(gsc, nombre="Frog Coffee Table", marca="Sovet Italia", tipo="coffee table",
                          h1=FROG, rasgo="glass", texto_ficha=TEXTO_FROG + " table", competencia=comp)
    assert [e["keyword"] for e in sel["elegidas"]] == ["frog table", "modern glass coffee table", "glass table"]


def test_con_una_sola_entra_search_console_con_menos_impresiones():
    gsc = [{"keyword": "frog table", "origen": "gsc", "impresiones": 40, "volumen": 30},
           {"keyword": "curved glass table", "origen": "gsc", "impresiones": 3, "volumen": 90}]
    sel = elegir_keywords(gsc, nombre="Frog Coffee Table", marca="Sovet Italia", tipo="coffee table",
                          h1=FROG, rasgo="glass", texto_ficha=TEXTO_FROG + " table")
    assert [e["keyword"] for e in sel["elegidas"]] == ["frog table", "curved glass table"]
    assert "curved glass table" not in [d["keyword"] for d in sel["descartadas"]]


def test_el_minimo_nunca_mete_una_incoherente():
    gsc = [{"keyword": "frog table", "origen": "gsc", "impresiones": 40, "volumen": 30}]
    comp = [{"keyword": "professional glass coffee table", "origen": "competidor", "volumen": 20, "competidores": 3}]
    sel = elegir_keywords(gsc, nombre="Frog Coffee Table", marca="Sovet Italia", tipo="coffee table",
                          h1=FROG, rasgo="glass", texto_ficha=TEXTO_FROG + " table",
                          competencia=candidatas_de_competencia(
                              [{"keyword": "professional glass coffee table", "volume": 20, "competidores": 3}],
                              h1=FROG, nombre="Frog Coffee Table", marca="Sovet Italia",
                              tipo="coffee table", texto_ficha=TEXTO_FROG, minimo=10))
    assert [e["keyword"] for e in sel["elegidas"]] == ["frog table"]


def test_la_keyword_de_la_competencia_termina_en_el_tipo():
    rank = [_c("foam bed king", 260, 2), _c("upholstered foam king bed", 90, 1)]
    out = [c["keyword"] for c in candidatas_de_competencia(
        rank, h1="Hermes Maxi Upholstered King Bed by DV Home Collection", nombre="Hermes Maxi Bed",
        marca="DV Home Collection", tipo="king bed",
        texto_ficha="Hermes double bed, upholstered, polyurethane foam, king size")]
    assert out == ["upholstered foam king bed"]


def test_cache_de_competencia_en_la_base(tmp_path):
    from cassoni.config import Config
    from cassoni.db import DB
    c = Config(env="staging")
    c.db_url = f"sqlite:///{tmp_path}/c.db"
    db = DB(c)
    assert db.competencia_fresca("rock coffee table rugiano", 2840, 30) is None
    db.guardar_competencia("rock coffee table rugiano", 2840, [{"url": "x"}], [{"keyword": "k"}])
    assert db.competencia_fresca("rock coffee table rugiano", 2840, 30) == ([{"url": "x"}], [{"keyword": "k"}])
