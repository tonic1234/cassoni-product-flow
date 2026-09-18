# -*- coding: utf-8 -*-
"""Editor LLM — produce el output estructurado de la ficha según las reglas del
cliente (docs/REGLA-SEO-FICHAS.md → cassoni/reglas.py): H1 ≤ 60 con keyword
principal EXACTA, descripción corta, descripción larga 150-300 palabras, 2-3
secundarias con su porqué (anti-canibalización incluida) y descartadas con destino.
"""
from __future__ import annotations

from .config import Config
from .llm import LLMClient, LLMError
from . import reglas

SYSTEM_PROMPT = f"""Sos un editor SEO senior especializado en muebles de lujo.
Editás el H1 y la DESCRIPCIÓN LARGA de un producto, incorporando keywords de forma
natural, sin exagerar y sin perder el tono elegante y sobrio de la marca.

ALCANCE (no negociable):
- El agente SOLO edita H1 y descripción larga. La descripción corta (arriba del
  fold) NO se edita: se conserva tal cual.

REGLAS DEL CLIENTE (obligatorias, no negociables):
{reglas.reglas_completas()}

Además:
- Preservá el tono de lujo y TODO el HTML y formato existentes en la descripción larga.
- No repitas conceptos que ya estén en el texto original.
- No inventes datos: nunca agregues precios, materiales o medidas que no estén en los inputs.
- Respetá semánticamente el filtro anti-canibalización: las keywords ya usadas como H1
  de otras fichas de la misma categoría NO pueden volver como secundarias.
- La keyword principal te la da el input 'keyword principal': va EXACTA en el H1,
  tal cual (misma redacción).
"""


def json_schema() -> str:
    return ('{"h1": "<H1 editado, máx 60 chars, con la keyword principal exacta>", '
            '"description": "<descripción larga 150-300 palabras, HTML, H2 marcados>", '
            '"keyword_principal": "<la keyword principal usada>", '
            '"secondary_keywords": [{"keyword": "<secundaria>", '
            '"why": "<por qué es específica de ESTE producto>"}, ...], '
            '"discarded": [{"keyword": "<descartada>", '
            '"belongs_to": "<a qué contenido pertenece: otra ficha / página de categoría '
            '/ blog o guía>"}], '
            '"used_keywords": ["<kw insertadas>"], '
            '"selection_reason": "<por qué elegiste la principal>"}')


class Editor:
    def __init__(self, config: Config, llm: LLMClient):
        self.cfg = config
        self.llm = llm

    def edit(self, *, url: str, current_h1: str, current_description: str,
             keywords: list[dict],
             current_short_description: str = "",
             categories: tuple = (),
             brand: str = "",
             attributes: tuple = (),
             keywords_ya_usadas: tuple = (),
             keyword_principal: str = "") -> dict:
        """Devuelve el output estructurado de la ficha o lanza LLMError."""
        if not keywords:
            raise LLMError("Sin keywords válidas para editar")

        key_rows = "\n".join(
            f"- {k['keyword']} (volumen {k.get('volume', '?')})" for k in keywords)
        principal = keyword_principal or (keywords[0].get("keyword", "") if keywords else "")

        user = f"""Producto: {url}

Categoría(s): {', '.join(categories) or '(sin datos)'}
Marca: {brand or '(sin dato en la ficha)'}
Atributos técnicos del producto:
{chr(10).join(f'- {a}' for a in attributes) or '(sin atributos en la ficha)'}

H1 actual:
{current_h1}

Descripción corta actual (contexto — NO se edita):
{current_short_description or '(vacía)'}

Descripción larga actual (HTML, la que hay que editar):
{current_description}

KEYWORD PRINCIPAL (obligatoria, EXACTA en el H1):
{principal}

Keywords candidatas (de mayor a menor volumen):
{key_rows}

Keywords ya usadas como H1 en OTRAS fichas de esta categoría (anti-canibalización;
no pueden repetirse como secundarias; si descartás alguna candidata, registrala en
'discarded' con su destino):
{chr(10).join(f'- {k}' for k in keywords_ya_usadas) or '(sin datos de otras fichas)'}

Responde SOLO con JSON:
{json_schema()}"""
        result = self.llm.complete_json(SYSTEM_PROMPT, user,
                                        model=self.cfg.llm_editor_model)
        return {
            "h1": result.get("h1", ""),
            "description": result.get("description", ""),
            "keyword_principal": result.get("keyword_principal", principal),
            "secondary_keywords": result.get("secondary_keywords", []),
            "discarded": result.get("discarded", []),
            "used_keywords": result.get("used_keywords", []),
            "selection_reason": result.get("selection_reason", ""),
        }