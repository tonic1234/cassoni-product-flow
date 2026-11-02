# -*- coding: utf-8 -*-
"""Test del checklist duro (checklist.py) — reglas verificables en código, sin LLM.

La regla de Antonio: el test se basa en la PREGUNTA (la spec del cliente), no en un
valor inventado. Cada caso de acá es una regla literal del documento.
"""
import pytest

from cassoni import checklist
from cassoni import reglas


class TestTextoFueraDeHTML:
    def test_strip_html(self):
        assert "Elegante sofá de cuero" in checklist.strip_html(
            "<p>Elegante <strong>sofá</strong> de cuero.</p>")

    def test_word_count(self):
        # "Elegante sofá de cuero negro." -> 5 palabras
        assert checklist.word_count("<p>Elegante sofá de cuero negro.</p>") == 5

    def test_h2_count(self):
        html = "<h2>Titulo uno</h2><p>texto</p><h2>Titulo dos</h2>"
        assert checklist.h2_count(html) == 2


class TestKeywordExacta:
    def test_exacta_normalizada(self):
        # "Sofá  De CUERO" == "sofá de cuero" (normalización: case + espacios)
        assert checklist.kw_exacta_en("Sofá  De CUERO negro", "sofá de cuero")

    def test_no_parcial(self):
        # no cuenta "sofa" dentro de "sofas" ni prefijos sueltos
        assert not checklist.kw_exacta_en("Nuestros sofás de lujo", "sofá")

    # criterio del SEO (Alexander Valero, 18-sep): "tienen que estar juntas sí.
    # La única variable aceptable es que se antecedan por un artículo (of, the etc)"
    def test_articulo_antes_ok(self):
        assert checklist.kw_exacta_en("the leather sofa is elegant", "leather sofa")
        assert checklist.kw_exacta_en("of the leather sofa collection", "leather sofa")

    def test_palabras_intercaladas_no(self):
        # "leather comfortable sofa" NO es "leather sofa": las palabras van juntas
        assert not checklist.kw_exacta_en("leather comfortable sofa", "leather sofa")

    def test_orden_invertido_no(self):
        assert not checklist.kw_exacta_en("sofa leather", "leather sofa")


class TestReglasDuras:
    _FRASES = [
        "Diseñado en líneas sobrias, este mueble combina estructura de madera maciza con "
        "tapicería de cuero, y cada costura queda rematada a mano.",
        "El respaldo ofrece un descanso profundo, los apoyabrazos redondeados completan "
        "una silueta equilibrada y la pieza aporta presencia sin recargar el ambiente.",
        "Se fabrica bajo pedido, puede personalizarse en distintos acabados y la entrega "
        "incluye montaje en el domicilio y garantía de cinco años.",
        "El cuero madura con los años ganando carácter, mientras la madera de roble "
        "sostiene el conjunto con firmeza y el mantenimiento se reduce a la limpieza habitual.",
        "Las medidas y las fichas técnicas completas figuran al pie de la página, junto "
        "con las opciones de color disponibles de fábrica y los tiempos estimados de entrega.",
        "Cada unidad pasa por un control de calidad previo al despacho, se embala con "
        "protección en todas sus aristas y el transportista coordina la recepción "
        "directamente con el cliente para evitar esperas innecesarias.",
    ]

    def _desc_larga_ok(self) -> str:
        """Descripción larga spec-compliant: 2 H2, sin repetir las secundarias del
        fixture (no menciona 'sofá de cuero de lujo' ni 'sofá negro') y >= 150 palabras."""
        p1 = " ".join(self._FRASES[:3])
        p2 = " ".join(self._FRASES[3:])
        return (f"<h2>Diseño</h2><p>{p1}</p>"
                f"<h2>Materiales y cuidados</h2><p>{p2}</p>")

    def _editado(self, **kw):
        base = dict(
            h1="Sofá de Cuero Negro Modelo Belinda",
            keyword_principal="sofá de cuero negro",
            description=self._desc_larga_ok(),
            secondary_keywords=[{"keyword": "sofá de cuero de lujo", "why": "uso"},
                                {"keyword": "sofá negro", "why": "estilo"}],
            discarded=[],
        )
        base.update({k: v for k, v in kw.items() if v is not None})
        return base

    def test_h1_ok_60(self):
        # 60 caracteres EXACTOS, conteniendo la keyword principal exacta
        principal = "sofá de cuero negro"
        e = self._editado(h1=(principal + " " + "S" * (60 - len(principal) - 1)))
        assert len(e["h1"]) == 60
        assert checklist.check_reglas(e) == []

    def test_h1_mas_de_60_falla(self):
        e = self._editado(h1="S" * 61)
        issues = checklist.check_reglas(e)
        assert any("60" in i and "H1" in i for i in issues)

    def test_desc_larga_bajo_minimo(self):
        e = self._editado(description="<p>Muy corto.</p>")
        issues = checklist.check_reglas(e)
        assert any("150" in i for i in issues)

    def test_desc_larga_sobre_maximo(self):
        e = self._editado(description="<p>" + "palabra " * 301 + "</p>")
        issues = checklist.check_reglas(e)
        assert any("300" in i for i in issues)

    def test_desc_larga_con_3_h2_falla(self):
        e = self._editado(description="<h2>A</h2><p>x</p><h2>B</h2><p>y</p><h2>C</h2><p>z</p>")
        assert any("2" in i and "H2" in i for i in checklist.check_reglas(e))

    def test_secundarias_de_0_a_1_fallan(self):
        e = self._editado(secondary_keywords=[])
        assert any("secundaria" in i.lower() for i in checklist.check_reglas(e))
        e1 = self._editado(secondary_keywords=[{"keyword": "solo una", "why": "x"}])
        assert any("secundaria" in i.lower() for i in checklist.check_reglas(e1))

    def test_secundarias_mas_de_3_fallan(self):
        e = self._editado(secondary_keywords=[{"keyword": f"kw {i}", "why": "x"}
                                              for i in range(4)])
        assert any("secundaria" in i.lower() for i in checklist.check_reglas(e))

    def test_secundaria_usada_mas_de_2_veces_falla(self):
        # la secundaria "canoa de cuero" aparece 3 veces en la desc -> viola máx 2 usos
        desc = "<p>canoa de cuero, canoa de cuero, canoa de cuero y otra canoa.</p>"
        e = self._editado(description=desc,
                          secondary_keywords=[{"keyword": "canoa de cuero", "why": "x"},
                                              {"keyword": "canoa de madera", "why": "y"}])
        issues = checklist.check_reglas(e)
        assert any("2 veces" in i for i in issues)

    def test_sin_porque_en_secundaria_falla(self):
        e = self._editado(secondary_keywords=[{"keyword": "kw", "why": ""},
                                              {"keyword": "kw2", "why": "ok"}])
        assert any("por qu" in i.lower() or "why" in i.lower() for i in checklist.check_reglas(e))

    def test_keyword_principal_no_exacta_en_h1_falla(self):
        # la keyword principal debe estar EXACTA en el H1 (regla del documento)
        e = self._editado(h1="Sofá elegante de lujo",
                          keyword_principal="sofá de cuero negro")
        issues = checklist.check_reglas(e)
        assert any("principal" in i.lower() for i in issues)

    def test_keyword_principal_exacta_en_h1_pasa(self):
        e = self._editado(h1="Sofá de Cuero Negro modelo Belinda",
                          keyword_principal="sofá de cuero negro")
        assert checklist.check_reglas(e) == []


class TestRepeticion:
    """Anti 'sofa sofa sofa' (Antonio 18-sep): si varias keywords comparten una
    palabra, ninguna puede dominar la descripción."""

    def test_palabra_dominante_detectada(self):
        desc = ("<p>Un sofá elegante, sofá moderno, sofá cómodo, sofá de lujo, "
                "sofá para el living, sofá con estructura, sofá de diseño, sofá "
                "italiano, sofá artesanal y sofá exclusivo.</p>")
        assert checklist.palabra_dominante(desc) == "sofá"

    def test_check_reglas_rebota_sofa_repetido(self):
        desc = ("<p>Un sofá elegante, sofá moderno, sofá cómodo, sofá de lujo, "
                "sofá para el living, sofá con estructura, sofá de diseño, sofá "
                "italiano, sofá artesanal y sofá exclusivo, en la colección del "
                "año, con acabados de la casa y cuero de la mejor curtiembre.</p>")
        e = dict(
            h1="Sofá de Cuero Negro Modelo Belinda",
            keyword_principal="sofá de cuero negro",
            description=desc,
            secondary_keywords=[{"keyword": "sofá de cuero de lujo", "why": "uso"},
                                {"keyword": "sofá negro", "why": "estilo"}],
            discarded=[],
        )
        issues = checklist.check_reglas(e)
        assert any("'sofá'" in i for i in issues)

    def test_funcionales_no_cuentan(self):
        # 'de' repetido no dispara (es palabra funcional)
        desc = "<p>" + "de la casa de la marca de la serie " * 6 + ".</p>"
        assert checklist.palabra_dominante(desc) == ""

    def test_desc_compliant_no_dispara(self):
        assert checklist.palabra_dominante(
            "<p>Elegante sofá de cuero negro con estructura de madera maciza de roble.</p>") == ""


class TestConservacion:
    """Requisito de Antonio (18-sep): la descripción larga se EDITA sobre el texto
    actual, nunca se reescribe desde cero — y eso tiene que ser medible."""

    _ORIG = "<p>Elegante sofá de cuero negro. Estructura de madera maciza de roble. " \
            "Tapicería rematada a mano. Garantía de cinco años.</p>"

    def test_conserva_oraciones_intactas(self):
        # edición quirúrgica: 1 oración nueva insertada, las demás intactas
        editado = "<p>Elegante sofá de cuero negro. Estructura de madera maciza de " \
                  "roble. Tapicería rematada a mano. Ideal para living de lujo. " \
                  "Garantía de cinco años.</p>"
        assert checklist.conservacion(self._ORIG, editado) > 0.7

    def test_reescritura_total_ratio_bajo(self):
        nuevo = "<p>Un mueble completamente distinto que no conserva nada de las " \
                "oraciones previas del texto original del producto.</p>"
        assert checklist.conservacion(self._ORIG, nuevo) < 0.3

    def test_check_reglas_rebota_reescritura(self):
        # texto nuevo de 150+ palabras, spec-compliant en lo demás, pero reescrito
        nuevo = ("<h2>Nuevo</h2><p>" + "palabra original nueva " * 40 + "</p>"
                 "<p>" + "otra frase distinta " * 40 + "</p>")
        e = dict(
            h1="Sofá de Cuero Negro Modelo Belinda",
            keyword_principal="sofá de cuero negro",
            description=nuevo,
            secondary_keywords=[{"keyword": "sofá de cuero de lujo", "why": "uso"},
                                {"keyword": "sofá negro", "why": "estilo"}],
            discarded=[],
        )
        issues = checklist.check_reglas(e, original_description=self._ORIG)
        assert any("reescrita" in i.lower() or "conserva" in i.lower() for i in issues)

    def test_check_reglas_ok_con_edicion_quirurgica(self):
        editado = ("<h2>Diseño</h2><p>Elegante sofá de cuero negro. Estructura de "
                   "madera maciza de roble. Tapicería rematada a mano. Ideal para "
                   "living de lujo. Garantía de cinco años.</p>"
                   "<p>Artículos de descripción extendida para superar el mínimo de "
                   "palabras de la regla, manteniendo el tono sobrio y elegante de "
                   "la colección, con materiales nobles y terminaciones cuidadas en "
                   "cada detalle del mueble, pensado para espacios exigentes y "
                   "amantes del diseño clásico contemporáneo, con entrega coordinada "
                   "y un servicio de posventa dedicado, tal como corresponde a una "
                   "pieza de esta categoría dentro del catálogo, con la presencia que "
                   "un ambiente de alta gama requiere y la serenidad visual que "
                   "caracteriza a las piezas de la casa.</p>"
                   "<h2>Materiales</h2><p>Cuero genuino con patas de madera de roble "
                   "maciza y una estructura pensada para durar décadas, manteniendo "
                   "su presencia, su comodidad y el carácter artesanal de la "
                   "colección, con acabados resistentes al uso diario y una "
                   "apariencia que mejora con el paso del tiempo en el hogar, y "
                   "detalles de confección que solo se encuentran en piezas "
                   "trabajadas por artesanos con años de oficio en el rubro.</p>")
        e = dict(
            h1="Sofá de Cuero Negro Modelo Belinda",
            keyword_principal="sofá de cuero negro",
            description=editado,
            secondary_keywords=[{"keyword": "sofá de cuero de lujo", "why": "uso"},
                                {"keyword": "sofá negro", "why": "estilo"}],
            discarded=[],
        )
        assert checklist.check_reglas(e, original_description=self._ORIG) == []


class TestDiversidadSecundarias:
    """Regla de Antonio (18-sep): de todas las keywords que comparten una palabra
    (p. ej. 'sofa') solo se puede usar UNA; hay que completar las 3 secundarias con
    keywords de palabras distintas."""

    def _c(self, *kws):
        return [{"keyword": k, "volume": v} for k, v in kws]

    def test_una_sola_por_palabra_compartida(self):
        cands = self._c(("leather sofa", 2100), ("modular sofa", 900),
                        ("italian luxury sofa", 720), ("sofa de cuero italiano", 390),
                        ("bouclé sofa", 480))
        r = checklist.seleccionar_diversas(cands, max_sec=3)
        elegidas = [e["keyword"] for e in r["elegidas"]]
        assert elegidas == ["leather sofa"]          # la de mayor volumen, y una sola
        assert len(r["omitidas"]) == 4
        assert all("sofa" in o["motivo"].lower() for o in r["omitidas"])

    def test_completa_hasta_3_con_palabras_distintas(self):
        cands = self._c(("leather sofa", 2100), ("modular sofa", 900),
                        ("canaletto walnut base", 320), ("quilted down seating", 180))
        r = checklist.seleccionar_diversas(cands, max_sec=3)
        elegidas = [e["keyword"] for e in r["elegidas"]]
        assert elegidas == ["leather sofa", "canaletto walnut base", "quilted down seating"]
        assert [o["keyword"] for o in r["omitidas"]] == ["modular sofa"]
        assert r["faltantes"] == 0

    def test_reporta_faltantes_si_no_alcanza(self):
        cands = self._c(("leather sofa", 2100), ("canaletto walnut base", 320))
        r = checklist.seleccionar_diversas(cands, max_sec=3)
        assert len(r["elegidas"]) == 2 and r["faltantes"] == 1

    def test_plural_y_acentos_colisionan(self):
        # 'sofa', 'sofas' y 'sofá' son la MISMA palabra a efectos de diversidad
        cands = self._c(("sofa de cuero", 900), ("sofas modernos", 800), ("sofá italiano", 700))
        r = checklist.seleccionar_diversas(cands, max_sec=3)
        assert len(r["elegidas"]) == 1


class TestAntiCanibalizacion:
    def _cands(self):
        return ["sofa de cuero belinda", "sofa negro", "como elegir sofa de lujo",
                "sofas de lujo", "sofas de la coleccion aria"]

    def test_descarta_ya_usada_como_principal(self):
        res = checklist.filtrar_canibalizacion(
            self._cands(),
            principals_ya_usadas={"sofa de cuero belinda"},
            categorias_como_pagina=set(), blogs_guia=set())
        assert "sofa de cuero belinda" not in {k["keyword"] for k in res["aceptadas"]}
        d = {k["keyword"]: k for k in res["descartadas"]}
        assert "sofa de cuero belinda" in d
        assert "principal" in d["sofa de cuero belinda"]["motivo"].lower()

    def test_descarta_que_compite_con_categoria(self):
        res = checklist.filtrar_canibalizacion(
            ["sofas de lujo", "sofa negro capitoné"],
            principals_ya_usadas=set(),
            categorias_como_pagina={"sofas"},
            blogs_guia=set())
        d = {k["keyword"]: k for k in res["descartadas"]}
        assert "sofas de lujo" in d
        assert "categor" in d["sofas de lujo"]["motivo"].lower()
        # la específica del producto sobrevive
        assert any(k["keyword"] == "sofa negro capitoné" for k in res["aceptadas"])

    def test_descarta_que_responde_a_blog(self):
        res = checklist.filtrar_canibalizacion(
            self._cands(),
            principals_ya_usadas=set(),
            categorias_como_pagina=set(),
            blogs_guia={"como elegir sofa de lujo"})
        d = {k["keyword"]: k for k in res["descartadas"]}
        assert "como elegir sofa de lujo" in d
        assert "blog" in d["como elegir sofa de lujo"]["motivo"].lower() or \
               "guía" in d["como elegir sofa de lujo"]["motivo"].lower()

    def test_descartada_registra_pertenece_a(self):
        res = checklist.filtrar_canibalizacion(
            self._cands(),
            principals_ya_usadas={"sofa de cuero belinda"},
            categorias_como_pagina=set(), blogs_guia=set())
        d = {k["keyword"]: k for k in res["descartadas"]}
        assert d["sofa de cuero belinda"]["pertenece_a"]  # apunta a la otra ficha

    def test_acepta_especificas_del_producto(self):
        res = checklist.filtrar_canibalizacion(
            ["sofa negro capitoné", "belinda de cuero"],
            principals_ya_usadas={"sofa de cuero belinda"},
            categorias_como_pagina={"sofas"}, blogs_guia=set())
        kws = {k["keyword"] for k in res["aceptadas"]}
        assert "sofa negro capitoné" in kws or "belinda de cuero" in kws

class TestDiversidadRespetaLaOportunidad:
    """Si dos keywords comparten palabra, sobrevive la de mayor OPORTUNIDAD.

    La diversidad se inventó (18-sep) para no decir 'sofa sofa sofa', y ordenaba
    por volumen. Cuando la principal se elige por oportunidad (2-nov), ordenar acá
    por volumen revertía esa decisión en silencio.
    """

    def test_sobrevive_la_de_mayor_oportunidad_aunque_tenga_menos_volumen(self):
        from cassoni.checklist import seleccionar_diversas
        cands = [
            {"keyword": "sofa de cuero", "volume": 5000, "opportunity_score": 40},
            {"keyword": "sofa modular", "volume": 120, "opportunity_score": 90},
        ]
        out = seleccionar_diversas(cands)
        assert out["elegidas"][0]["keyword"] == "sofa modular"

    def test_sin_scores_sigue_mandando_el_volumen(self):
        from cassoni.checklist import seleccionar_diversas
        cands = [{"keyword": "sofa chico", "volume": 10},
                 {"keyword": "sofa grande", "volume": 900}]
        out = seleccionar_diversas(cands)
        assert out["elegidas"][0]["keyword"] == "sofa grande"


class TestConservacionYPuntuacionDelScraping:
    """El texto original viene del scraping con puntos pegados ('area.Made in Italy.').
    El editor lo corrige al escribirlo bien y la métrica lo contaba como pérdida:
    penalizaba mejorar la puntuación."""

    def test_arreglar_la_puntuacion_cuenta_como_conservar(self):
        from cassoni.checklist import conservacion
        orig = "<p>Una oración original. Otra oración original.Made in Italy.</p>"
        edit = "<p>Una oración original. Otra oración original. Made in Italy. " \
               "Texto nuevo agregado.</p>"
        assert conservacion(orig, edit) == 1.0

    def test_reescribir_de_verdad_sigue_penalizado(self):
        from cassoni.checklist import conservacion
        orig = "<p>Una oración original. Otra oración original.</p>"
        edit = "<p>Texto completamente distinto que no conserva nada.</p>"
        assert conservacion(orig, edit) == 0.0
