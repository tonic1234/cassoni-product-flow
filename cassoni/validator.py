# -*- coding: utf-8 -*-
"""Agente Validador — control de calidad del output del editor.

Dos capas, en este orden:
1) REGLAS MECÁNICAS en código (cassoni/checklist.py): longitudes, conteos de
   palabras/H2, usos de secundarias, keyword exacta. Deterministas: no dependen
   del prompt ni del modelo.
2) LLM para lo creativo: tono de lujo, naturalidad, HTML roto, datos inventados.
Si cualquiera de las dos capas falla, rebota al editor (hasta max_passes).
"""
from __future__ import annotations

import json

from .config import Config
from .checklist import check_reglas
from .editor import Editor
from .llm import LLMClient, LLMError

VALIDATOR_SYSTEM = """Sos un control de calidad editorial riguroso para una tienda
de muebles de lujo. Evaluás si una edición SEO es aceptable.
Detectá: pérdida del tono de lujo, keyword forzada/antinatural, repetición de
conceptos ya presentes, H1 que dejó de ser descriptivo, HTML roto, o datos
inventados (precios/materiales/medidas).
Las reglas mecánicas (longitudes, conteos, anti-canibalización) YA se verificaron
en código antes de llegarte: reportá solo lo cualitativo.
Decidí si la edición APRUEBA o necesita re-trabajo.
"""


class Validator:
    def __init__(self, config: Config, llm: LLMClient):
        self.cfg = config
        self.llm = llm

    def validate(self, *, url: str, original_h1: str, original_desc: str,
                 edited_h1: str, edited_desc: str,
                 target_keywords: list[str],
                 attributes: tuple = (), brand: str = "",
                 categories: tuple = ()) -> dict:
        # Los ATRIBUTOS OFICIALES de la ficha son la fuente de verdad de los datos:
        # sin ellos, cualquier medida real de WooCommerce parece "inventada" (pasó
        # en el piloto del 2-nov: marcó 62"3/8 y 122"W como falsas y eran del campo
        # Size). El validador juzga con la misma información que tuvo el editor.
        attrs = "\n".join(f"- {a}" for a in attributes) or "(sin atributos)"
        user = f"""Producto: {url}
Marca: {brand or '(sin dato)'}
Categoría(s): {', '.join(categories) or '(sin dato)'}

Atributos oficiales de la ficha (datos REALES de WooCommerce; cualquier dato que
figure acá NO es inventado y NO puede reportarse como tal):
{attrs}

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
                       edited: dict, target_keywords: list[str],
                       editor: Editor, backup_keywords: list[dict],
                       context: dict | None = None,
                       max_passes: int = 2) -> dict:
        """Valida (reglas mecánicas + LLM); si no aprueba, rebota al editor
        (hasta max_passes veces). Devuelve {aprobado, intentos, validacion,
        edited:{h1,description}}."""
        self._context = context or {}
        # la ficha completa del editor viaja entera: check_reglas necesita
        # keyword_principal y secondary_keywords, no solo los textos
        last_edited = dict(edited)
        last_val = None
        for attempt in range(max_passes):
            mecanicas = check_reglas(last_edited,
                                     original_description=original_desc)
            last_val = self.validate(
                url=url, original_h1=original_h1, original_desc=original_desc,
                edited_h1=last_edited["h1"], edited_desc=last_edited["description"],
                target_keywords=target_keywords,
                attributes=tuple(self._context.get("attributes") or ()),
                brand=self._context.get("brand") or "",
                categories=tuple(self._context.get("categories") or ()))
            issues = list(mecanicas) + list(last_val.get("issues") or [])
            if not mecanicas and last_val.get("aprobado"):
                last_val["issues"] = issues
                return {"aprobado": True, "intentos": attempt + 1,
                        "validacion": last_val, "edited": last_edited}
            if attempt + 1 < max_passes:
                last_edited = self._rework(editor, url, last_edited,
                                           backup_keywords, issues)
        if last_val is not None:
            last_val["issues"] = list(mecanicas) + list(last_val.get("issues") or [])
        return {"aprobado": False, "intentos": max_passes,
                "validacion": last_val or {"aprobado": False, "issues": mecanicas},
                "edited": last_edited}

    def _rework(self, editor, url, current, backup_keywords, issues) -> dict:
        ctx = dict(self._context)
        ctx.pop("current_h1", None)
        ctx.pop("current_description", None)
        principal = ctx.pop("keyword_principal", "")
        feedback = editor.edit(
            url=url, current_h1=current["h1"], current_description=current["description"],
            keywords=backup_keywords,
            current_short_description=ctx.pop("current_short_description", ""),
            categories=ctx.pop("categories", ()),
            brand=ctx.pop("brand", ""),
            attributes=ctx.pop("attributes", ()),
            keywords_ya_usadas=ctx.pop("keywords_ya_usadas", ()),
            keyword_principal=principal,
            feedback=list(issues or []))
        # la ficha COMPLETA viaja al siguiente pase: si se devuelven sólo h1 y
        # description, la 2da pasada rebota por "falta la keyword principal" y
        # "hay 0 secundarias" (bug real del piloto, 2-nov)
        return {
            "h1": feedback["h1"],
            "description": feedback["description"],
            "keyword_principal": feedback.get("keyword_principal") or principal,
            "secondary_keywords": feedback.get("secondary_keywords") or [],
            "discarded": feedback.get("discarded") or [],
            "used_keywords": feedback.get("used_keywords") or [],
            "selection_reason": feedback.get("selection_reason") or "",
        }