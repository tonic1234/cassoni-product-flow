# -*- coding: utf-8 -*-
"""Agente Validador — control de calidad del output del editor.

Revisa coherencia, tono de lujo preservado, keywords incorporadas, ausencia
de repetición, y que el texto siga siendo descriptivo. Si detecta problemas,
rebota al editor para una segunda pasada.
"""
from __future__ import annotations

import json

from .config import Config
from .editor import Editor
from .llm import LLMClient, LLMError

VALIDATOR_SYSTEM = """Sos un control de calidad editorial riguroso para una tienda
de muebles de lujo. Evaluás si una edición SEO es aceptable.
Detectá: pérdida del tono de lujo, keyword forzada/antinatural, repetición de
conceptos ya presentes, H1 que dejó de ser descriptivo, HTML roto, o datos
inventados (precios/materiales/medidas).
Decidí si la edición APRUEBA o necesita re-trabajo.
"""


class Validator:
    def __init__(self, config: Config, llm: LLMClient):
        self.cfg = config
        self.llm = llm

    def validate(self, *, url: str, original_h1: str, original_desc: str,
                 edited_h1: str, edited_desc: str,
                 target_keywords: list[str]) -> dict:
        user = f"""Producto: {url}

---- ORIGINAL ----
H1: {original_h1}
Descripción: {original_desc[:1500]}

---- EDITADO ----
H1: {edited_h1}
Descripción: {edited_desc[:2500]}

Keywords que debían incorporarse: {', '.join(target_keywords)}

Responde SOLO con JSON:
{json.dumps({
    "aprobado": True,
    "issues": ["<detalle del problema si existe>"],
    "keywords_presentes": ["<kw que efectivamente están>"],
    "tono_lujo": True,
    "razon": "<breve justificación>",
}, ensure_ascii=False)}"""
        out = self.llm.complete_json(VALIDATOR_SYSTEM, user,
                                     model=self.cfg.llm_validator_model)
        out["aprobado"] = bool(out.get("aprobado"))
        return out

    def pass_or_rework(self, *, url: str, original_h1: str, original_desc: str,
                       edited_h1: str, edited_desc: str, target_keywords: list[str],
                       editor: Editor, backup_keywords: list[dict],
                       max_passes: int = 2) -> dict:
        """Valida; si no aprueba, rebota al editor (hasta max_passes veces).
        Devuelve {aprobado, intentos, resultado_validacion, edited:{h1,desc}}."""
        last_edited = {"h1": edited_h1, "description": edited_desc}
        last_val = None
        for attempt in range(max_passes):
            last_val = self.validate(
                url=url, original_h1=original_h1, original_desc=original_desc,
                edited_h1=last_edited["h1"], edited_desc=last_edited["description"],
                target_keywords=target_keywords)
            if last_val.get("aprobado"):
                return {"aprobado": True, "intentos": attempt + 1,
                        "validacion": last_val, "edited": last_edited}
            if attempt + 1 < max_passes:
                last_edited = self._rework(editor, url, last_edited, backup_keywords,
                                           last_val)
        return {"aprobado": False, "intentos": max_passes,
                "validacion": last_val, "edited": last_edited}

    def _rework(self, editor, url, current, backup_keywords, last_val) -> dict:
        issues = "; ".join(last_val.get("issues") or [])
        feedback = editor.edit(
            url=url, current_h1=current["h1"], current_description=current["description"],
            keywords=backup_keywords)
        # nota: el editor no conoce los issues; para re-trabajo lo más simple
        # es re-correr con los keywords originales. Guardamos el intento.
        return {"h1": feedback["h1"], "description": feedback["description"]}