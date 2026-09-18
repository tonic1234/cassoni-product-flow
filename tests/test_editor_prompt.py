# -*- coding: utf-8 -*-
"""Tests del contrato del editor (prompt) — regresión de las instrucciones
clave para que no se pierdan en ediciones futuras."""
from cassoni.editor import SYSTEM_PROMPT


class TestPromptContrato:
    def test_candidatas_ya_filtradas(self):
        # el LLM NO puede descartar lo que el filtro determinista ya dejó pasar
        s = SYSTEM_PROMPT.lower()
        assert "ya pasaron" in s and "no las descartes" in s

    def test_no_reescribir(self):
        assert "NUNCA la reescribas desde cero" in SYSTEM_PROMPT

    def test_tono_de_marca(self):
        assert "TONO DE LA MARCA" in SYSTEM_PROMPT or "registro de Cassoni" in SYSTEM_PROMPT

    def test_anti_repeticion(self):
        assert "sofa sofa sofa" in SYSTEM_PROMPT.lower()

    def test_keywords_juntas_mismo_orden(self):
        # criterio del SEO (18-sep): juntas, mismo orden, solo artículo delante
        assert "MISMO orden" in SYSTEM_PROMPT

    def test_alcance_solo_h1_y_long(self):
        assert "SOLO edita H1 y descripción larga" in SYSTEM_PROMPT