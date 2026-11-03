# -*- coding: utf-8 -*-
"""Editor LLM — incorpora las keywords objetivo en la DESCRIPCIÓN LARGA.

Contrato v2 (equipo SEO, 3-nov-2026):
- El H1 NO pasa por acá: es `{Nombre} by {Marca}`, armado por cassoni/h1.py.
- Las keywords ya vienen elegidas por código (cassoni/keywords.py): son las que
  tienen volumen y NO estaban en la descripción. El LLM no elige ni descarta:
  las mete orgánicamente, de forma coherente con lo que la ficha ya dice.
- La descripción se EDITA sobre el texto actual (se mide la conservación),
  nunca se reescribe.
"""
from __future__ import annotations

from .config import Config
from .llm import LLMClient, LLMError
from . import reglas

SYSTEM_PROMPT = f"""Sos un editor SEO senior especializado en muebles de lujo.
Tu única tarea es incorporar KEYWORDS en la DESCRIPCIÓN LARGA de un producto, de
forma natural y coherente con lo que el texto ya dice, sin perder el tono elegante
y sobrio de la marca.

ALCANCE (no negociable):
- Solo editás la descripción larga. El H1 y la descripción corta NO se tocan.
- {reglas.REGLAS_H1}

REGLAS:
- {reglas.REGLAS_KEYWORDS}
- {reglas.REGLAS_KEYWORD_JUNTA}
- PARTÍ DEL TEXTO ACTUAL tal cual viene en el input 'Descripción larga actual':
  tu trabajo es EDITARLO QUIRÚRGICAMENTE (insertar frases donde cada keyword
  encaje natural). NUNCA la reescribas desde cero.
- CÓMO INSERTAR (prueba real del 3-nov): por cada keyword, UNA sola oración
  nueva de 12 a 25 palabras que CONTIENE esa keyword, colocada junto a la
  oración del original con la que tiene relación (nunca después de "Made in
  Italy."). Armala con lo que la ficha YA dice: un material, un acabado, una
  característica o el diseñador que aparecen en la descripción, la descripción
  corta o los atributos. Como máximo 4 palabras con contenido que no estén en
  la ficha. Prohibido el interiorismo genérico: "presence", "to the room",
  "any interior", "tailored", "composed", "conceived for", "brings a",
  "focal point", "statement piece". No agregues NINGUNA otra oración.
- {reglas.REGLAS_SIN_MEDIDAS}
- Si el original es corto, la edición también queda corta: no completes hasta
  ninguna cantidad de palabras.
- Es OBLIGATORIO conservar al menos el {reglas.CONSERVACION_MIN:.0%} de las oraciones
  originales INTACTAS: sumá frases nuevas alrededor, nunca reemplaces una existente.
- {reglas.REGLAS_TONO}
- {reglas.REGLAS_DIVERSIFICAR}
- {reglas.REGLAS_DESC_LARGA}
- {reglas.REGLAS_NO_GO}
- {reglas.REGLAS_HTML}
- Preservá TODO el HTML y el formato existentes en la descripción larga.
- No repitas conceptos que ya estén en el texto original.
"""


def json_schema() -> str:
    return ('{"description": "<descripción larga editada, HTML, H2 marcados>", '
            '"keywords": [{"keyword": "<keyword objetivo, exacta>", '
            '"donde": "<en qué oración o H2 quedó>", '
            '"why": "<por qué encaja en ESTE producto>"}, ...]}')


def _faltantes(result: dict, objetivo: list[str]) -> list[str]:
    """Claves obligatorias que el JSON del editor no trajo (o trajo vacías)."""
    faltan = []
    if not (result.get("description") or "").strip():
        faltan.append("description")
    reportadas = {(k.get("keyword") or "").strip().lower()
                  for k in (result.get("keywords") or []) if isinstance(k, dict)}
    sin_reportar = [k for k in objetivo if k.lower() not in reportadas]
    if sin_reportar:
        faltan.append(f"keywords ({', '.join(sin_reportar)})")
    return faltan


class Editor:
    def __init__(self, config: Config, llm: LLMClient):
        self.cfg = config
        self.llm = llm

    def edit(self, *, url: str, h1: str, current_description: str,
             keywords: list[dict],
             current_short_description: str = "",
             categories: tuple = (),
             brand: str = "",
             attributes: tuple = (),
             feedback: list[str] | None = None) -> dict:
        """Devuelve {h1, description, keywords} o lanza LLMError. El `h1` vuelve
        tal cual entró: el editor no lo decide."""
        objetivo = [k["keyword"] for k in keywords if k.get("keyword")]
        if not objetivo:
            raise LLMError("Sin keywords objetivo para incorporar")

        filas = "\n".join(f"- {k['keyword']} (volumen {k.get('volume') or 's/d'})"
                          for k in keywords)
        bloque_feedback = ""
        if feedback:
            bloque_feedback = (
                "\n\nTU VERSIÓN ANTERIOR FUE RECHAZADA POR ESTOS MOTIVOS "
                "(corregilos TODOS, sin excepción):\n"
                + "\n".join(f"- {i}" for i in feedback))

        user = f"""Producto: {url}
H1 (fijo, NO se edita): {h1}

Categoría(s): {', '.join(categories) or '(sin datos)'}
Marca: {brand or '(sin dato en la ficha)'}
Atributos técnicos del producto:
{chr(10).join(f'- {a}' for a in attributes) or '(sin atributos en la ficha)'}

Descripción corta actual (contexto — NO se edita):
{current_short_description or '(vacía)'}

Descripción larga actual (HTML, la que hay que editar):
{current_description}

KEYWORDS OBJETIVO (todas obligatorias, EXACTAS, 1 o 2 veces cada una; no
están en el texto actual):
{filas}

Responde SOLO con JSON:
{json_schema()}{bloque_feedback}"""
        # presupuesto holgado: los modelos razonadores gastan tokens antes de
        # emitir el JSON y la descripción larga es extensa (se truncó el 2-nov)
        result = self.llm.complete_json(SYSTEM_PROMPT, user,
                                        model=self.cfg.llm_editor_model,
                                        max_tokens=12000)
        faltan = _faltantes(result, objetivo)
        if faltan:
            # JSON a medias (pasó en el piloto del 2-nov): se pide de nuevo
            # diciéndole QUÉ falta, en vez de aceptarlo y que rebote abajo.
            recordatorio = (f"\n\nTu respuesta anterior estuvo incompleta. Falta: "
                            f"{', '.join(faltan)}. Devolvé el JSON COMPLETO.")
            result2 = self.llm.complete_json(SYSTEM_PROMPT, user + recordatorio,
                                             model=self.cfg.llm_editor_model,
                                             max_tokens=12000)
            if len(_faltantes(result2, objetivo)) < len(faltan):
                result = result2
        return {
            "h1": h1,
            "description": result.get("description", ""),
            "keywords": [k for k in (result.get("keywords") or []) if isinstance(k, dict)],
        }
