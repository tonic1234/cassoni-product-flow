# -*- coding: utf-8 -*-
"""Tests del cliente LLM — regresión del bug encontrado en la prueba real
(18-sep-2026, ficha Connor Sofa): con tope de tokens chico, el modelo razonador
devuelve `content` VACÍO y `complete_json` moría con JSONDecodeError en vez de
un error claro; y el tope default era insuficiente para razonamiento + JSON."""
import json

import pytest

from cassoni.config import Config
from cassoni.llm import LLMClient, LLMError


class FakeResp:
    def __init__(self, content):
        self._content = content
    def raise_for_status(self):
        pass
    def json(self):
        return {"choices": [{"message": {"role": "assistant",
                                         "content": self._content}}]}


class FakeHTTP:
    """Cliente httpx falso: registra el body y devuelve un content fijo."""
    def __init__(self, content):
        self.content = content
        self.last_body = None
    def post(self, url, json=None, headers=None):
        self.last_body = json
        return FakeResp(self.content)


def _cfg():
    c = Config(env="staging", dry_run=True)
    c.llm_base_url = "https://llm.test/v1"
    c.llm_api_key = "k"
    c.llm_editor_model = "m"
    return c


def test_content_vacio_lanza_llmerror_claro():
    # el bug real: content vacío -> antes JSONDecodeError críptico
    llm = LLMClient(_cfg(), client=FakeHTTP(""))
    with pytest.raises(LLMError) as ei:
        llm.complete_json("s", "u")
    assert "vac" in str(ei.value).lower()  # "vacía"


def test_content_no_json_lanza_llmerror():
    llm = LLMClient(_cfg(), client=FakeHTTP("esto no es json"))
    with pytest.raises(LLMError):
        llm.complete_json("s", "u")


def test_json_valido_devuelve_dict():
    llm = LLMClient(_cfg(), client=FakeHTTP('{"h1": "x"}'))
    assert llm.complete_json("s", "u") == {"h1": "x"}


class FakeSecuencia:
    """Devuelve respuestas en orden (para probar reintentos)."""
    def __init__(self, *contents):
        self.contents = list(contents)
        self.bodies = []
    def post(self, url, json=None, headers=None):
        self.bodies.append(json)
        c = self.contents.pop(0)
        return FakeResp(c)


def test_retry_tras_content_vacio():
    # el modelo razonador a veces devuelve content vacío (varianza real del
    # piloto Connor v4): reintento con doble presupuesto salva la llamada
    fake = FakeSecuencia("", '{"ok": true}')
    llm = LLMClient(_cfg(), client=fake)
    assert llm.complete_json("s", "u") == {"ok": True}
    assert fake.bodies[0]["max_tokens"] == 8000
    assert fake.bodies[1]["max_tokens"] == 16000


def test_content_vacio_2_intentos_lanza_llmerror():
    fake = FakeSecuencia("", "")
    llm = LLMClient(_cfg(), client=fake)
    with pytest.raises(LLMError) as ei:
        llm.complete_json("s", "u")
    assert "2 intentos" in str(ei.value)


def test_tope_de_tokens_suficiente_para_razonamiento():
    # con 1800 el razonamiento del modelo consumía el presupuesto y content
    # llegaba vacío: el default tiene que dejar lugar al JSON final
    fake = FakeHTTP('{"ok": true}')
    llm = LLMClient(_cfg(), client=fake)
    llm.complete_json("s", "u")
    assert fake.last_body["max_tokens"] >= 8000