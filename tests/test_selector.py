# -*- coding: utf-8 -*-
"""Selector de trabajo — puro, sin red. Convierte filas de GSC en un lote priorizado.

Regla de negocio (auditoría 13-oct): el flujo no puede depender de una lista escrita a
mano. La ficha que se toca es la que tiene demanda real y está fuera del top: posición
4-20 con impresiones, o mucho aparecer con CTR bajo. El ruido (posición > 30 y cero
clics) no entra al lote.
"""
from cassoni import selector


def _pagina(url, impressions=1000, clicks=10, ctr=0.01, position=12.0):
    return {"url": url, "impressions": impressions, "clicks": clicks,
            "ctr": ctr, "position": position}


def _q(keyword, impressions=300, clicks=0, ctr=0.0, position=12.0):
    return {"keyword": keyword, "impressions": impressions, "clicks": clicks,
            "ctr": ctr, "position": position}


class TestEsProducto:
    def test_ficha_de_producto(self):
        assert selector.es_producto("https://cassoni.com/product/connor-sofa/")

    def test_categoria_no_es_producto(self):
        assert not selector.es_producto("https://cassoni.com/product-category/sofas/")

    def test_blog_no_es_producto(self):
        assert not selector.es_producto("https://cassoni.com/blog/que-sofa-elegir/")

    def test_pagina_sin_producto_en_el_path(self):
        assert not selector.es_producto("https://cassoni.com/contacto/")


class TestFiltrarPaginas:
    def test_deja_solo_fichas_con_demanda(self):
        rows = [
            _pagina("https://cassoni.com/product/a/", impressions=900),
            _pagina("https://cassoni.com/product/b/", impressions=10),     # poca demanda
            _pagina("https://cassoni.com/product-category/x/", impressions=99999),
        ]
        out = selector.filtrar_paginas(rows, min_impressions=50)
        assert [r["url"] for r in out] == ["https://cassoni.com/product/a/"]

    def test_descarta_ruido_posicion_lejana_sin_clics(self):
        # posición 45 y cero clics: no es oportunidad, es ruido
        rows = [_pagina("https://cassoni.com/product/ruido/", impressions=400,
                        clicks=0, ctr=0.0, position=45.0)]
        assert selector.filtrar_paginas(rows, min_impressions=50) == []

    def test_posicion_lejana_con_clics_se_conserva(self):
        # si igual entra gente, hay algo: no se descarta
        rows = [_pagina("https://cassoni.com/product/raro/", impressions=400,
                        clicks=5, ctr=0.0125, position=45.0)]
        assert len(selector.filtrar_paginas(rows, min_impressions=50)) == 1

    def test_ordena_por_impresiones_desc(self):
        rows = [_pagina("https://cassoni.com/product/b/", impressions=100),
                _pagina("https://cassoni.com/product/a/", impressions=900)]
        out = selector.filtrar_paginas(rows, min_impressions=50)
        assert [r["impressions"] for r in out] == [900, 100]

    def test_no_muta_las_filas_de_entrada(self):
        row = _pagina("https://cassoni.com/product/a/")
        antes = dict(row)
        selector.filtrar_paginas([row], min_impressions=50)
        assert row == antes


class TestElegirKeyword:
    def test_elige_por_oportunidad_no_por_volumen(self):
        # 'sofa de cuero' tiene MÁS impresiones pero ya está en el top (no hay nada que ganar)
        # 'sofa modular lujo' está en posición 12: es la oportunidad
        rows = [_q("sofa de cuero", impressions=5000, clicks=400, ctr=0.08, position=2.0),
                _q("sofa modular lujo", impressions=300, clicks=0, ctr=0.0, position=12.0)]
        elegida = selector.elegir_keyword(rows)
        assert elegida["keyword"] == "sofa modular lujo"
        assert elegida["opportunity"] == "materialize_demand"

    def test_desempata_por_impresiones(self):
        rows = [_q("a", impressions=200, position=10.0),
                _q("b", impressions=900, position=10.0)]
        assert selector.elegir_keyword(rows)["keyword"] == "b"

    def test_sin_filas_devuelve_none(self):
        assert selector.elegir_keyword([]) is None


class TestPriorizar:
    def test_arma_el_lote_con_la_keyword_elegida(self):
        paginas = [_pagina("https://cassoni.com/product/sofa-a/", impressions=900)]
        queries = {"https://cassoni.com/product/sofa-a/": [
            _q("sofa modular", impressions=300, position=12.0),
            _q("sofa de cuero", impressions=5000, clicks=400, ctr=0.08, position=2.0),
        ]}
        lote = selector.priorizar(paginas, queries)
        assert len(lote) == 1
        c = lote[0]
        assert c["url"] == "https://cassoni.com/product/sofa-a/"
        assert c["keyword"] == "sofa modular"
        assert c["opportunity_score"] > 0
        assert c["impressions"] == 900          # de la página
        assert c["kw_impressions"] == 300       # de la consulta elegida

    def test_ordena_por_oportunidad_y_luego_impresiones(self):
        paginas = [
            _pagina("https://cassoni.com/product/top-sofa/", impressions=5000),
            _pagina("https://cassoni.com/product/oportunidad-sofa/", impressions=600),
        ]
        queries = {
            "https://cassoni.com/product/top-sofa/": [
                _q("top sofa", impressions=5000, clicks=500, ctr=0.1, position=1.0)],  # hold_top = 40
            "https://cassoni.com/product/oportunidad-sofa/": [
                _q("oportunidad sofa", impressions=600, position=6.0)],                # materialize > 55
        }
        lote = selector.priorizar(paginas, queries)
        assert lote[0]["url"] == "https://cassoni.com/product/oportunidad-sofa/"

    def test_pagina_sin_consultas_no_entra(self):
        paginas = [_pagina("https://cassoni.com/product/sin-query/")]
        assert selector.priorizar(paginas, {}) == []

    def test_respeta_el_tope_n(self):
        paginas = [_pagina(f"https://cassoni.com/product/sofa-{i}/", impressions=900 - i)
                   for i in range(30)]
        queries = {p["url"]: [_q("sofa", impressions=300, position=12.0)] for p in paginas}
        assert len(selector.priorizar(paginas, queries, top_n=20)) == 20

    def test_no_repite_urls(self):
        paginas = [_pagina("https://cassoni.com/product/sofa-a/", impressions=900),
                   _pagina("https://cassoni.com/product/sofa-a/", impressions=900)]
        queries = {"https://cassoni.com/product/sofa-a/": [_q("sofa", impressions=300, position=12.0)]}
        lote = selector.priorizar(paginas, queries)
        assert len({c["url"] for c in lote}) == len(lote)


class TestLoteAJson:
    def test_serializa_el_lote_para_evidencia(self):
        lote = [{"url": "https://cassoni.com/product/a/", "keyword": "sofa modular",
                 "opportunity": "materialize_demand", "opportunity_score": 77,
                 "impressions": 900, "kw_impressions": 300, "position": 12.0,
                 "kw_position": 12.0, "clicks": 0, "kw_clicks": 0, "ctr": 0.0,
                 "kw_ctr": 0.0}]
        texto = selector.lote_a_json(lote, meta={"dias": 90, "tope": 20})
        assert '"keyword": "sofa modular"' in texto
        assert '"dias": 90' in texto


class TestRelevanciaDeLaConsulta:
    """Hallazgo del lote real (2-nov): el selector eligió 'liberator lounger' para una
    silla dining y 'geef foto' (basura de GSC) para un sofá. Una consulta con
    impresiones no sirve si no es de ESE producto."""

    def test_basura_de_gsc_no_es_relevante(self):
        assert not selector.relevante("geef foto",
                                      "https://cassoni.com/product/cas-mor-pebble-rubble-sofa-01/")

    def test_consulta_de_otro_mueble_no_es_relevante(self):
        assert not selector.relevante("liberator lounger",
                                      "https://cassoni.com/product/cas-oak-sc_1019_chair-01/")

    def test_consulta_del_producto_es_relevante(self):
        assert selector.relevante("club sofa",
                                  "https://cassoni.com/product/cas-rug-club-sofa-01/")

    def test_una_palabra_en_comun_alcanza(self):
        assert selector.relevante("cruise sofa",
                                  "https://cassoni.com/product/cas-tal-cruise-teak-sofa-01/")

    def test_funciona_igual_con_el_nombre_real_del_producto(self):
        # en el orquestador se compara contra name + categorías + marca
        assert selector.relevante("outdoor couch", "Cruise Couch Outdoor Sofa by Talenti")
        assert not selector.relevante("geef foto", "Pebble Rubble Sofa by Moroso")

    def test_nombre_de_marca_solo_tambien_cuenta(self):
        assert selector.relevante("anamon",
                                  "https://cassoni.com/product/anamon-outdoor-luxury-parasol-lamp-royal-botania/")

    def test_palabras_cortas_del_slug_no_cuentan(self):
        # 'cas', '01', 'sc' son códigos internos, no materia de la consulta
        assert not selector.relevante("cas 01", "https://cassoni.com/product/cas-rug-club-sofa-01/")

    def test_elegir_keyword_ignora_las_irrelevantes_y_toma_la_siguiente(self):
        rows = [_q("geef foto", impressions=5000, position=6.0),
                _q("pebble sofa", impressions=400, position=9.0)]
        elegida = selector.elegir_keyword(
            rows, url="https://cassoni.com/product/cas-mor-pebble-rubble-sofa-01/")
        assert elegida["keyword"] == "pebble sofa"
        assert elegida["opportunity"] == "materialize_demand"

    def test_sin_ninguna_relevante_la_ficha_no_entra(self):
        paginas = [_pagina("https://cassoni.com/product/cas-mor-pebble-rubble-sofa-01/")]
        queries = {paginas[0]["url"]: [_q("geef foto", impressions=5000)]}
        assert selector.priorizar(paginas, queries) == []
