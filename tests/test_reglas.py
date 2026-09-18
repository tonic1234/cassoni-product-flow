# -*- coding: utf-8 -*-
"""Test de la espec del agente (reglas.py) — las reglas del documento del cliente
como fuente única de constantes y textos."""
import pytest

from cassoni import reglas


class TestConstantes:
    def test_h1_max_60(self):
        assert reglas.H1_MAX_CHARS == 60

    def test_desc_larga_150_300(self):
        assert reglas.LARGA_MIN_WORDS == 150
        assert reglas.LARGA_MAX_WORDS == 300

    def test_h2_maximo_2(self):
        assert reglas.MAX_H2 == 2

    def test_secundarias_2_a_3(self):
        assert reglas.SEC_MIN == 2
        assert reglas.SEC_MAX == 3

    def test_secundaria_max_2_usos(self):
        assert reglas.SEC_MAX_USOS == 2


class TestTextos:
    def test_textos_referencian_la_spec(self):
        # el prompt se arma desde acá: la spec no puede vivir solo en un .md
        txt = "\n".join(v for k, v in vars(reglas).items()
                        if k.isupper() and isinstance(v, str))
        for s in ("60", "150", "300", "canibalización", "keyword principal"):
            assert s in txt