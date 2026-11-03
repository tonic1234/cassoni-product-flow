# -*- coding: utf-8 -*-
"""Agente Validador — control de calidad del output del editor.

Dos capas, en este orden:
1) REGLAS MECÁNICAS en código (cassoni/checklist.py): longitudes, H2, que cada
   keyword objetivo quedó EXACTA, conservación del original y HTML seguro.
   Deterministas: no dependen del prompt ni del modelo.
2) LLM para lo creativo: tono de lujo, naturalidad, coherencia, datos inventados.
Si cualquiera de las dos capas falla, rebota al editor (hasta max_passes).
"""
from __future__ import annotations

import json

from .config import Config
from .checklist import check_reglas
from .editor import Editor
from .llm import LLMClient, LLMError

# el validador ve el texto COMPLETO: si se recorta, los datos inventados del
# final de la descripción nunca se revisan (auditoría 3-nov)
MAX_CHARS_TEXTO = 12000

VALIDATOR_SYSTEM = """Sos un control de calidad editorial riguroso para una tienda
de muebles de lujo. Evaluás si una edición SEO de la descripción larga es aceptable.
Detectá: pérdida del tono de lujo, keyword forzada/antinatural o incoherente con el
producto, repetición de conceptos ya presentes, HTML roto, o datos inventados
(precios/materiales/medidas que no estén en el original ni en los atributos).
Las reglas mecánicas (longitudes, conteos, keywords exactas, HTML seguro) YA se
verificaron en código antes de llegarte: reportá solo lo cualitativo.
Decidí si la edición APRUEBA o necesita re-trabajo.
"""


class Validator:
    def __init__(self, config: Config, llm: LLMClient):
        self.cfg = config
        self.llm = llm

    def validate(self, *, url: str, h1: str, original_desc: str, edited_desc: str,
                 target_keywords: list[str],
                 attributes: tuple = (), brand: str = "",
                 categories: tuple = ()) -> dict:
        # Los ATRIBUTOS OFICIALES de la ficha son la fuente de verdad de los datos:
        # sin ellos, cualquier medida real de WooCommerce parece "inventada" (pasó
        # en el piloto del 2-nov). El validador juzga con lo mismo que el editor.
        attrs = "\n".join(f"- {a}" for a in attributes) or "(sin atributos)"
        user = f"""Producto: {url}
H1: {h1}
Marca: {brand or '(sin dato)'}
Categoría(s): {', '.join(categories) or '(sin dato)'}

Atributos oficiales de la ficha (datos REALES de WooCommerce; cualquier dato que
figure acá NO es inventado y NO puede reportarse como tal):
{attrs}

---- DESCRIPCIÓN ORIGINAL ----
{original_desc[:MAX_CHARS_TEXTO]}

---- DESCRIPCIÓN EDITADA ----
{edited_desc[:MAX_CHARS_TEXTO]}

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
        if not isinstance(out, dict):
            raise LLMError("El validador no devolvió un objeto JSON")
        out["aprobado"] = bool(out.get("aprobado"))
        return out

    def pass_or_rework(self, *, url: str, original_desc: str, edited: dict,
                       keywords: list[dict], editor: Editor,
                       context: dict | None = None, max_passes: int = 2) -> dict:
        """Valida (reglas mecánicas + LLM); si no aprueba, rebota al editor
        (hasta max_passes veces). Devuelve {aprobado, intentos, validacion, edited}."""
        ctx = context or {}
        objetivo = [k["keyword"] for k in keywords if k.get("keyword")]
        last_edited = dict(edited)
        last_val = None
        mecanicas: list[str] = []
        for attempt in range(max_passes):
            mecanicas = check_reglas(last_edited, original_description=original_desc,
                                     keywords=objetivo)
            last_val = self.validate(
                url=url, h1=last_edited.get("h1", ""), original_desc=original_desc,
                edited_desc=last_edited.get("description", ""),
                target_keywords=objetivo,
                attributes=tuple(ctx.get("attributes") or ()),
                brand=ctx.get("brand") or "",
                categories=tuple(ctx.get("categories") or ()))
            issues = list(mecanicas) + list(last_val.get("issues") or [])
            if not mecanicas and last_val.get("aprobado"):
                last_val["issues"] = issues
                return {"aprobado": True, "intentos": attempt + 1,
                        "validacion": last_val, "edited": last_edited}
            if attempt + 1 < max_passes:
                last_edited = editor.edit(
                    url=url, h1=last_edited.get("h1", ""),
                    current_description=last_edited.get("description", ""),
                    keywords=keywords,
                    current_short_description=ctx.get("current_short_description", ""),
                    categories=tuple(ctx.get("categories") or ()),
                    brand=ctx.get("brand") or "",
                    attributes=tuple(ctx.get("attributes") or ()),
                    feedback=issues)
        if last_val is not None:
            last_val["issues"] = list(mecanicas) + list(last_val.get("issues") or [])
            last_val["aprobado"] = False
        return {"aprobado": False, "intentos": max_passes,
                "validacion": last_val or {"aprobado": False, "issues": mecanicas},
                "edited": last_edited}
