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
            short_description="Sofá de cuero negro, elegancia para el living.",
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

    def test_desc_corta_sin_h2(self):
        e = self._editado(short_description="<h2>Hola</h2>texto")
        assert any("corta" in i and "H2" in i for i in checklist.check_reglas(e))

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

    def test_keyword_principal_exacta_en_h1_y_desc_corta_pasa(self):
        e = self._editado(h1="Sofá de Cuero Negro modelo Belinda",
                          keyword_principal="sofá de cuero negro",
                          short_description="Sofá de cuero negro: elegancia para el living.")
        assert checklist.check_reglas(e) == []


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