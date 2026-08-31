# -*- coding: utf-8 -*-
"""Cliente LLM OpenAI-compatible (Gemini Flash, DeepSeek, Claude usan el mismo
formato/mismo cliente HTTP, como remarca la sección 10 del informe)."""
from __future__ import annotations

import json
import logging
from typing import Optional

import httpx

from .config import Config

log = logging.getLogger("cassoni.llm")


class LLMError(Exception):
    pass


class LLMClient:
    def __init__(self, config: Config, client: Optional[httpx.Client] = None):
        self.cfg = config
        self._http = client or httpx.Client(timeout=90)

    def _post(self, model: str, messages: list[dict], temperature: float = 0.3,
              max_tokens: int = 1200) -> str:
        if not (self.cfg.llm_base_url and self.cfg.llm_api_key):
            raise LLMError("Config LLM incompleta (llm_base_url/api_key)")
        headers = {"Authorization": f"Bearer {self.cfg.llm_api_key}",
                   "Content-Type": "application/json"}
        body = {"model": model, "messages": messages,
                "temperature": temperature, "max_tokens": max_tokens}
        url = self.cfg.llm_base_url.rstrip("/") + "/chat/completions"
        try:
            r = self._http.post(url, json=body, headers=headers)
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"].strip()
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            raise LLMError(f"Fallo LLM ({model}): {exc}") from exc

    def complete(self, system: str, user: str, *, model: str | None = None,
                 temperature: float = 0.3, max_tokens: int = 1200) -> str:
        return self._post(model or self.cfg.llm_editor_model,
                          [{"role": "system", "content": system},
                           {"role": "user", "content": user}],
                          temperature=temperature, max_tokens=max_tokens)

    def complete_json(self, system: str, user: str, *, model: str | None = None,
                      temperature: float = 0.2, max_tokens: int = 1800) -> dict:
        raw = self.complete(system, user + (
            "\n\nResponde SOLO con JSON válido."), model=model,
            temperature=temperature, max_tokens=max_tokens)
        return json.loads(raw)