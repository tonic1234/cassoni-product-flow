# -*- coding: utf-8 -*-
"""Tests del contrato del editor (prompt) — regresión de las instrucciones
clave para que no se pierdan en ediciones futuras."""
from cassoni.editor import SYSTEM_PROMPT


class TestPromptContrato:
    def test_las_keywords_vienen_elegidas_por_codigo(self):
        # contrato v2: el LLM no elige ni descarta, solo incorpora
        assert "elegidas por código" in SYSTEM_PROMPT

    def test_no_reescribir(self):
        assert "NUNCA la reescribas desde cero" in SYSTEM_PROMPT

    def test_tono_de_marca(self):
        assert "TONO DE LA MARCA" in SYSTEM_PROMPT or "registro de Cassoni" in SYSTEM_PROMPT

    def test_anti_repeticion(self):
        assert "sofa sofa sofa" in SYSTEM_PROMPT.lower()

    def test_keywords_juntas_mismo_orden(self):
        # criterio del SEO (18-sep): juntas, mismo orden, solo artículo delante
        assert "MISMO orden" in SYSTEM_PROMPT

    def test_alcance_solo_descripcion_larga(self):
        assert "Solo editás la descripción larga" in SYSTEM_PROMPT
        assert "El H1 y la descripción corta NO se tocan" in SYSTEM_PROMPT

    def test_html_seguro_en_el_prompt(self):
        assert "no agregues scripts" in SYSTEM_PROMPT

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


def test_el_h1_no_lo_decide_el_llm():
    """Aunque el modelo devuelva un H1, el editor devuelve el de plantilla."""
    llm = _LLMGuion([{"h1": "Otro H1 inventado", "description": "<p>x club sofa</p>",
                      "keywords": [{"keyword": "club sofa", "why": "es un club sofa"}]}])
    out = _editor(None, llm).edit(url="u", h1="Club Sofa by Rugiano",
                                  current_description="<p>x</p>",
                                  keywords=[{"keyword": "club sofa"}])
    assert out["h1"] == "Club Sofa by Rugiano"
    assert "Club Sofa by Rugiano" in llm.llamadas[0]


def test_json_incompleto_se_reintenta_una_vez():
    """Si el modelo omite claves obligatorias (descripción, una keyword), se le
    pide de nuevo con el faltante explícito en vez de aceptar el JSON a medias."""
    incompleto = {"description": "", "keywords": []}
    completo = {"description": "<p>ok</p>",
                "keywords": [{"keyword": "k1", "why": "a"}, {"keyword": "k2", "why": "b"}]}
    llm = _LLMGuion([incompleto, completo])
    out = _editor(None, llm).edit(url="u", h1="H1", current_description="<p>x</p>",
                                  keywords=[{"keyword": "k1"}, {"keyword": "k2"}])
    assert len(llm.llamadas) == 2
    assert "falt" in llm.llamadas[1].lower()      # le dice QUÉ faltó
    assert out["description"] == "<p>ok</p>"
    assert len(out["keywords"]) == 2


def test_sin_keywords_no_llama_al_llm():
    import pytest
    from cassoni.llm import LLMError
    llm = _LLMGuion([])
    with pytest.raises(LLMError):
        _editor(None, llm).edit(url="u", h1="H1", current_description="<p>x</p>",
                                keywords=[])
    assert llm.llamadas == []



def test_prompt_prohibe_medidas_y_relleno():
    """Prueba real 3-nov: el prompt pedía 'completar con medidas' hasta 150 palabras."""
    assert "No agregues medidas" in SYSTEM_PROMPT
    assert "no completes hasta" in SYSTEM_PROMPT
    assert "completá SOLO con datos de los atributos" not in SYSTEM_PROMPT
