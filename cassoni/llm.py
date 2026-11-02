# -*- coding: utf-8 -*-
"""Cliente LLM OpenAI-compatible (Gemini Flash, DeepSeek, Claude usan el mismo
formato/mismo cliente HTTP, como remarca la sección 10 del informe)."""
from __future__ import annotations

import json
import logging
from typing import Optional

import httpx

from .config import Config
from . import costos

log = logging.getLogger("cassoni.llm")


class LLMError(Exception):
    pass


class LLMClient:
    def __init__(self, config: Config, client: Optional[httpx.Client] = None):
        self.cfg = config
        self._http = client or httpx.Client(timeout=90)
        self.usage: list[dict] = []      # una entrada por llamada (usage crudo)

    def consumo(self) -> dict:
        """Tokens y USD acumulados en este cliente (todas sus llamadas)."""
        return costos.sumar([costos.costo_de_usage(u) for u in self.usage])

    def ping(self) -> int:
        """GET /models sin gastar tokens. Devuelve el código HTTP."""
        if not (self.cfg.llm_base_url and self.cfg.llm_api_key):
            raise LLMError("Config LLM incompleta (llm_base_url/api_key)")
        r = self._http.get(self.cfg.llm_base_url.rstrip("/") + "/models",
                           headers={"Authorization": f"Bearer {self.cfg.llm_api_key}"})
        return r.status_code

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
            if isinstance(data.get("usage"), dict):
                self.usage.append(data["usage"])
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
                      temperature: float = 0.2, max_tokens: int = 8000) -> dict:
        """JSON estricto. max_tokens generoso (>=8000) porque los modelos
        razonadores (deepseek-v4-flash) consumen presupuesto en reasoning_content
        y a veces dejan content vacío; si pasa, se REINTENTA una vez con el doble
        (varianza real observada en el piloto Connor, 18-sep). Errores claros."""
        for intent, mt in ((1, max_tokens), (2, max_tokens * 2)):
            raw = self.complete(system, user + (
                "\n\nResponde SOLO con JSON válido."), model=model,
                temperature=temperature, max_tokens=mt)
            if raw and raw.strip():
                try:
                    return json.loads(raw)
                except json.JSONDecodeError as exc:
                    if intent == 1:
                        # JSON truncado o roto: se reintenta con más presupuesto
                        # (pasó en el piloto del 2-nov: 'Unterminated string')
                        log.warning("JSON inválido en el intento 1 (%s) -> reintento "
                                    "con %s tokens", exc, mt * 2)
                        continue
                    raise LLMError(
                        f"El modelo no devolvió JSON válido (primeros 120 chars: "
                        f"{raw[:120]!r}): {exc}") from exc
            if intent == 1:
                log.warning("Content vacío en el intento 1 (max_tokens=%s) -> "
                            "reintento con %s", max_tokens, mt * 2)
        raise LLMError(
            "El modelo devolvió content vacío en 2 intentos (presupuesto de tokens "
            "agotado en el razonamiento): aumentar max_tokens o simplificar el prompt)")