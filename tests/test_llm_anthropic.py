# -*- coding: utf-8 -*-
"""Modelos claude-* van por el SDK de Anthropic (comparación de modelos, 13-nov)."""
from types import SimpleNamespace as NS

import pytest

from cassoni.llm import LLMClient, LLMError


class FakeMessages:
    def __init__(self, resp):
        self.resp, self.kwargs = resp, None

    def create(self, **kw):
        self.kwargs = kw
        return self.resp


def _cliente(cfg, resp):
    c = LLMClient(cfg)
    msgs = FakeMessages(resp)
    c._anthropic = NS(beta=NS(messages=msgs))
    return c, msgs


def _resp(texto, stop="end_turn"):
    return NS(content=[NS(type="thinking", thinking=""), NS(type="text", text=texto)],
              stop_reason=stop, stop_details=None,
              usage=NS(input_tokens=1000, output_tokens=500, cache_read_input_tokens=4000,
                       cache_creation_input_tokens=0))


def test_claude_va_por_el_sdk_y_devuelve_json(cfg):
    c, msgs = _cliente(cfg, _resp('```json\n{"ok": true}\n```'))
    assert c.complete_json("sistema", "usuario", model="claude-sonnet-5-5") == {"ok": True}
    kw = msgs.kwargs
    assert kw["model"] == "claude-sonnet-5-5" and "temperature" not in kw
    assert kw["output_config"] == {"effort": cfg.anthropic_effort}
    assert kw["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert kw["fallbacks"] == "default"
    consumo = c.consumo()
    # 1000 × $2 + 4000 × $0,10 + 500 × $10, por millón
    assert consumo["usd"] == pytest.approx((1000 * 2 + 4000 * 0.10 + 500 * 10) / 1e6)


def test_un_rechazo_es_un_error_claro(cfg):
    c, _ = _cliente(cfg, _resp("", stop="refusal"))
    with pytest.raises(LLMError, match="rechazó"):
        c.complete("s", "u", model="claude-sonnet-5-5")
