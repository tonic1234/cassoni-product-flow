# -*- coding: utf-8 -*-
"""Editor LLM — incorpora keywords en el H1 y la long description de forma
quirúrgica, preservando el tono de lujo de Cassoni y el HTML original."""
from __future__ import annotations

from .config import Config
from .llm import LLMClient, LLMError

SYSTEM_PROMPT = """Sos un editor SEO senior especializado en muebles de lujo.
Editás el H1 y la descripción larga de productos de una tienda de mobiliario
(premium/lujo) incorporando keywords de forma natural, sin exagerar y sin
perder la redacción ni el tono originales.

Reglas estrictas:
- Inserta la keyword principal (la más descriptiva) en el H1 de forma natural.
- Incorpora las keywords restantes en la descripción larga sin forzarlas.
- Preserva el tono de lujo, elegante y sobrio de Cassoni.
- NO repitas conceptos que ya estén en el texto original.
- Mantén TODO el HTML y formato existentes (párrafos, listas, strong, etc.).
- No inventes datos: nunca agregues precios, materiales o medidas que no estén.
- Si el H1 ya contiene la keyword exacta, no lo cambies innecesariamente.
"""


class Editor:
    def __init__(self, config: Config, llm: LLMClient):
        self.cfg = config
        self.llm = llm

    def edit(self, *, url: str, current_h1: str, current_description: str,
             keywords: list[dict]) -> dict:
        """Devuelve {h1, description, used_keywords:[...]} o lanza LLMError."""
        if not keywords:
            raise LLMError("Sin keywords válidas para editar")
        key_rows = "\n".join(
            f"- {k['keyword']} (volumen {k.get('volume','?')})" for k in keywords)
        user = f"""Producto: {url}

H1 actual:
{current_h1}

Descripción larga actual (HTML):
{current_description}

Keywords a incorporar (de mayor a menor volumen):
{key_rows}

Edita el H1 y la descripción. Responde SOLO con JSON:
{json_schema()}"""
        result = self.llm.complete_json(SYSTEM_PROMPT, user,
                                        model=self.cfg.llm_editor_model)
        return {
            "h1": result["h1"],
            "description": result["description"],
            "used_keywords": result.get("used_keywords", []),
            "selection_reason": result.get("selection_reason", ""),
        }


def json_schema() -> str:
    return ('{"h1": "<H1 editado>", "description": "<descripción editada, con HTML>", '
            '"used_keywords": ["<kw que insertaste>"], '
            '"selection_reason": "<por qué elegiste esa para el H1>"}')