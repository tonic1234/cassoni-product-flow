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

    def test_genera_variantes_si_llegan_menos_de_3(self):
        # diversidad (18-sep): si faltan candidatas, las genera desde atributos
        # SIN repetir la palabra ya usada
        assert "MENOS DE 3 candidatas" in SYSTEM_PROMPT
        assert "repetir la palabra ya usada" in SYSTEM_PROMPT

    def test_alcance_solo_h1_y_long(self):
        assert "SOLO edita H1 y descripción larga" in SYSTEM_PROMPT

class _LLMGuion:
    """Devuelve respuestas en orden y cuenta las llamadas."""

    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = []

    def complete_json(self, system, user, **kw):
        self.llamadas.append(user)
        return self.respuestas.pop(0) if self.respuestas else {}


def _editor(monkeypatch, llm):
    from cassoni.config import Config
    from cassoni.editor import Editor
    cfg = Config(env="staging", dry_run=True)
    cfg.llm_editor_model = "deepseek-flash"
    return Editor(cfg, llm)


def test_keyword_principal_vacia_cae_al_default(tmp_path):
    """El piloto real (2-nov) devolvió keyword_principal='' y el checklist lo leyó
    como 'falta la keyword principal' aunque el H1 la tenía."""
    llm = _LLMGuion([{"h1": "Rugiano Club Sofa", "description": "<p>x</p>",
                      "keyword_principal": "", "secondary_keywords": [], "discarded": []}])
    ed = _editor(None, llm)
    out = ed.edit(url="u", current_h1="Club Sofa", current_description="<p>x</p>",
                  keywords=[{"keyword": "club sofa"}], keyword_principal="club sofa")
    assert out["keyword_principal"] == "club sofa"


def test_json_incompleto_se_reintenta_una_vez():
    """Si el modelo omite claves obligatorias (secundarias, descripción), se le
    pide de nuevo con el faltante explícito en vez de aceptar el JSON a medias."""
    incompleto = {"h1": "H1", "description": "", "secondary_keywords": []}
    completo = {"h1": "H1", "description": "<p>ok</p>", "keyword_principal": "k",
                "secondary_keywords": [{"keyword": "s1", "why": "por material"},
                                       {"keyword": "s2", "why": "por uso"}],
                "discarded": []}
    llm = _LLMGuion([incompleto, completo])
    ed = _editor(None, llm)
    out = ed.edit(url="u", current_h1="H1", current_description="<p>x</p>",
                  keywords=[{"keyword": "k"}], keyword_principal="k")
    assert len(llm.llamadas) == 2
    assert "falt" in llm.llamadas[1].lower()      # le dice QUÉ faltó
    assert out["description"] == "<p>ok</p>"
    assert len(out["secondary_keywords"]) == 2
