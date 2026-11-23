# -*- coding: utf-8 -*-
"""El cliente LLM se identifica con su propio user agent; con OpenCode manda además
un ID de sesión estable por corrida (lo pide su documentación)."""
from cassoni.config import Config
from cassoni.llm import USER_AGENT, LLMClient


def _cli(base):
    c = Config(env="staging")
    c.llm_base_url, c.llm_api_key = base, "x"
    return LLMClient(c)


def test_user_agent_propio():
    assert _cli("https://api.deepseek.com")._headers()["User-Agent"] == USER_AGENT


def test_sesion_solo_con_opencode_y_estable():
    assert "x-opencode-session" not in _cli("https://api.deepseek.com")._headers()
    cli = _cli("https://opencode.ai/inference/go/openai/v1")
    assert cli._headers()["x-opencode-session"] == cli._headers()["x-opencode-session"]
