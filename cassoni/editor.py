# -*- coding: utf-8 -*-
"""Editor LLM — edita H1 y descripción larga según las reglas del cliente
(docs/REGLA-SEO-FICHAS.md → cassoni/reglas.py): H1 ≤ 60 con keyword principal
EXACTA, descripción larga 150-300 palabras, 2-3 secundarias con su porqué
(anti-canibalización incluida) y descartadas con destino. La descripción larga
se EDITA sobre el texto actual (se mide la conservación), nunca se reescribe.
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

REGLA TRANSVERSAL DE LAS DOS TAREAS:
- No inventes datos: nunca agregues precios, materiales o medidas que no estén en los inputs.
- Respetá el filtro anti-canibalización: las keywords ya usadas como H1 de otras
  fichas de la misma categoría NO pueden volver como secundarias.

═══ TAREA 1 — H1 ═══
- Resultado: {reglas.REGLAS_H1}
- La 'keyword principal' del input va EXACTA en el H1, con la MISMA redacción, tal cual.
- Si el H1 actual ya cumple, no lo cambies innecesariamente (edición quirúrgica también acá).

═══ TAREA 2 — DESCRIPCIÓN LARGA ═══
- PARTÍ DEL TEXTO ACTUAL tal cual viene en el input 'Descripción larga actual':
  tu trabajo es EDITARLO QUIRÚRGICAMENTE (insertar o ajustar frases donde la
  keyword encaje natural). NUNCA la reescribas desde cero ni generes una nueva:
  la versión editada conserva la estructura, la redacción y el tono del original.
- {reglas.REGLAS_TONO}
- {reglas.REGLAS_DIVERSIFICAR}
- {reglas.REGLAS_DESC_LARGA}
- {reglas.REGLAS_SECUNDARIAS}
- {reglas.REGLAS_KEYWORD_JUNTA}
- ANTI-CANIBALIZACIÓN YA APLICADA: las 'Keywords candidatas' del input YA pasaron
  el filtro determinista (se comparó contra las H1 reales de las fichas hermanas y
  las categorías reales de la tienda). Por eso NO las descartes: tu trabajo es
  ELEGIR 2 o 3 entre ellas para usar (priorizando las de mayor volumen siempre que
  encajen natural). Si generás una variante nueva, debe estar anclada en los
  atributos de la ficha y reportarse igual en 'secondary_keywords' con su porqué.
- 'secondary_keywords' es OBLIGATORIO: devolvé 2 o 3, cada una con su 'why' específico.
- Es OBLIGATORIO conservar al menos el 80% de las oraciones originales INTACTAS:
  sumá frases nuevas alrededor, nunca reemplaces una oración existente.
- SI te llegan MENOS DE 3 candidatas: generá las que faltan como variantes ANCLADAS
  en los atributos o contexto de la ficha (material, estructura, estilo, uso) y
  registralas en 'secondary_keywords' con su porqué. Las variantes no pueden
  repetir la palabra ya usada por otra keyword elegida ('sofa' usado una vez = no
  más 'sofa' en otras secundarias).
- {reglas.REGLAS_NO_GO}
- Preservá el tono de lujo y TODO el HTML y formato existentes en la descripción larga.
- No repitas conceptos que ya estén en el texto original.
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


def _faltantes(result: dict) -> list[str]:
    """Claves obligatorias que el JSON del editor no trajo (o trajo vacías)."""
    faltan = []
    if not (result.get("h1") or "").strip():
        faltan.append("h1")
    if not (result.get("description") or "").strip():
        faltan.append("description")
    if not (result.get("keyword_principal") or "").strip():
        faltan.append("keyword_principal")
    if len(result.get("secondary_keywords") or []) < 2:
        faltan.append("secondary_keywords (2 o 3)")
    return faltan


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
             keyword_principal: str = "",
             feedback: list[str] | None = None) -> dict:
        """Devuelve el output estructurado de la ficha o lanza LLMError."""
        if not keywords:
            raise LLMError("Sin keywords válidas para editar")

        key_rows = "\n".join(
            f"- {k['keyword']} (volumen {k.get('volume', '?')})" for k in keywords)
        principal = keyword_principal or (keywords[0].get("keyword", "") if keywords else "")

        bloque_feedback = ""
        if feedback:
            bloque_feedback = (
                "\n\nTU VERSIÓN ANTERIOR FUE RECHAZADA POR ESTOS MOTIVOS "
                "(corregilos TODOS, sin excepción):\n"
                + "\n".join(f"- {i}" for i in feedback))

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

Keywords candidatas (ordenadas por oportunidad: la primera es la principal; usa el volumen para desempatar):
{key_rows}

Keywords ya usadas como H1 en OTRAS fichas de esta categoría (anti-canibalización;
no pueden repetirse como secundarias; si descartás alguna candidata, registrala en
'discarded' con su destino):
{chr(10).join(f'- {k}' for k in keywords_ya_usadas) or '(sin datos de otras fichas)'}

Responde SOLO con JSON:
{json_schema()}{bloque_feedback}"""
        # presupuesto holgado: los modelos razonadores gastan tokens antes de
        # emitir el JSON y la descripción larga es extensa (se truncó el 2-nov)
        result = self.llm.complete_json(SYSTEM_PROMPT, user,
                                        model=self.cfg.llm_editor_model,
                                        max_tokens=12000)
        faltan = _faltantes(result)
        if faltan:
            # el modelo devolvió un JSON a medias (pasó en el piloto real del
            # 2-nov: sin secundarias y con la principal vacía). Se le pide de
            # nuevo diciéndole QUÉ falta, en vez de aceptarlo y que rebote abajo.
            recordatorio = (f"\n\nTu respuesta anterior estuvo incompleta. Falta: "
                            f"{', '.join(faltan)}. Devolvé el JSON COMPLETO con todas "
                            f"las claves del esquema (h1, description, "
                            f"secondary_keywords con 2 o 3 elementos, discarded, "
                            f"keyword_principal, used_keywords, selection_reason).")
            result2 = self.llm.complete_json(SYSTEM_PROMPT, user + recordatorio,
                                             model=self.cfg.llm_editor_model,
                                             max_tokens=12000)
            if len(_faltantes(result2)) < len(faltan):
                result = result2
        return {
            "h1": result.get("h1", ""),
            "description": result.get("description", ""),
            "keyword_principal": result.get("keyword_principal") or principal,
            "secondary_keywords": result.get("secondary_keywords", []),
            "discarded": result.get("discarded", []),
            "used_keywords": result.get("used_keywords", []),
            "selection_reason": result.get("selection_reason", ""),
        }