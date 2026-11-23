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


VALIDATOR_REESCRITURA = """Sos el control de calidad de cassoni.com (muebles de
lujo, EE. UU.). Revisás un H1 y una descripción REESCRITOS por un redactor contra
los datos reales de la ficha. Los números, el HTML, el enlace y las keywords exactas
YA se controlaron en código: vos juzgás lo que el código no ve.

Rechazá (aprobado=false) si encontrás CUALQUIERA de estas cosas, y decí cuál:
1. DATO INVENTADO: una afirmación que no sale de la descripción original, la corta
   ni los atributos (un material, un acabado, un uso, una certificación, "Made in
   Italy" sin que la ficha diga Italy/Italian, una cantidad de opciones mal
   contada). Es lo más grave.
2. CONTRADICCIÓN con la ficha (la descripción afirma algo que un atributo niega).
3. KEYWORD FORZADA: la keyword está pero la oración existe solo para meterla, o la
   usa con otro sentido.
4. H1 que no dice qué es el producto, o que elige un rasgo menor (el color de una
   costura) en vez del que distingue al producto (material, forma, técnica).
5. TONO: frases de catálogo genérico, relleno, la misma idea repetida.

No rechaces por estilo o por gustos si los datos son correctos y se lee bien.
"""


class Validator:
    def __init__(self, config: Config, llm: LLMClient):
        self.cfg = config
        self.llm = llm

    def validate_reescritura(self, *, ficha: dict, redactado: dict,
                             keywords: list[str]) -> dict:
        from .redactor import fuentes_de
        user = f"""Ficha: {ficha['url']}
Marca: {ficha['marca'] or '(sin dato)'}   Tipo: {ficha['tipo']}

---- DATOS REALES DE LA FICHA (lo único que se puede afirmar) ----
{fuentes_de(ficha)[:MAX_CHARS_TEXTO]}

---- H1 PROPUESTO ----
{redactado.get('h1', '')}

---- DESCRIPCIÓN PROPUESTA ----
{redactado.get('description', '')[:MAX_CHARS_TEXTO]}

Keywords objetivo: {', '.join(keywords) or '(ninguna)'}

Responde SOLO con JSON:
{json.dumps({"aprobado": True, "issues": ["<problema concreto, con la frase>"],
             "razon": "<breve>"}, ensure_ascii=False)}"""
        out = self.llm.complete_json(VALIDATOR_REESCRITURA, user,
                                     model=self.cfg.llm_validator_model)
        if not isinstance(out, dict):
            raise LLMError("El validador no devolvió un objeto JSON")
        out["aprobado"] = bool(out.get("aprobado"))
        return out

    def redactar_hasta_minimo(self, *, ficha: dict, keywords: list[dict], reservas: list[dict],
                              redactor, minimo: int) -> dict:
        """redactar_y_validar y, si el redactor omitió keywords por no entrar natural y
        la ficha quedó debajo del mínimo, UNA vuelta más con las siguientes reservas
        (candidatas que pasaron todos los filtros). Devuelve lo mismo más
        `objetivos`: las keywords que efectivamente quedaron (23-nov)."""
        from .reglas_seo import genericas_para_h1, genericas_usadas
        from .checklist import strip_html

        def _quedaron(val, kws):
            ed = val["edited"]
            omit = {(o.get("keyword") or "").lower() for o in ed.get("omitidas") or []}
            quedan = [k for k in kws if k["keyword"].lower() not in omit]
            gen = ficha.get("genericas_opcionales") or []
            if gen and val["aprobado"]:
                h1 = ed.get("h1") or ""
                validas = {k for k, _, _ in genericas_para_h1(h1, gen)}
                ya = {k["keyword"].lower() for k in quedan}
                for kw, v, ok in genericas_usadas(strip_html(ed.get("description") or ""), h1, gen):
                    if ok and kw in validas and kw not in ya:
                        ya.add(kw)
                        quedan.append({"keyword": kw, "origen": "generica", "volumen": v,
                                       "volume": v, "por_que": "el material del H1 con el tipo"})
            return quedan, omit

        val = self.redactar_y_validar(ficha=ficha, keywords=keywords, redactor=redactor)
        quedan, omit = _quedaron(val, keywords)
        val["objetivos"] = quedan
        if not val["aprobado"] or len(quedan) >= minimo or not reservas:
            return val
        ya = {k["keyword"].lower() for k in quedan} | omit
        extra = [r for r in reservas if r["keyword"].lower() not in ya][:minimo - len(quedan)]
        if not extra:
            return val
        base = [k for k in keywords if k["keyword"].lower() not in omit]
        val2 = self.redactar_y_validar(ficha=ficha, keywords=base + extra, redactor=redactor)
        if not val2["aprobado"]:
            return val
        quedan2, _ = _quedaron(val2, base + extra)
        if len(quedan2) <= len(quedan):
            return val
        val2["objetivos"] = quedan2
        val2["intentos"] = val["intentos"] + val2["intentos"]
        val2["reservas_usadas"] = [r["keyword"] for r in extra]
        return val2

    def redactar_y_validar(self, *, ficha: dict, keywords: list[dict], redactor,
                           max_passes: int = 3) -> dict:
        """Redacta, controla (código + LLM) y rebota con los motivos hasta
        `max_passes`. Si el H1 nunca pasa los controles, se usa el de respaldo
        (sin LLM) y se valida la descripción igual. Devuelve
        {aprobado, intentos, validacion, edited, h1_respaldo_usado}."""
        from .redactor import controles
        objetivo = [k["keyword"] for k in keywords if k.get("keyword")]
        feedback: list[str] | None = None
        redactado, val, mecanicas = {}, None, []
        for intento in range(1, max_passes + 1):
            redactado = redactor.redactar(ficha=ficha, keywords=keywords, feedback=feedback)
            mecanicas = controles(ficha, redactado, objetivo)
            if intento == max_passes and all(m.startswith("H1:") for m in mecanicas) \
                    and mecanicas:
                redactado["h1"] = ficha["h1_respaldo"]
                redactado["h1_respaldo_usado"] = True
                mecanicas = controles(ficha, redactado, objetivo)
            if mecanicas:
                feedback = mecanicas
                val = {"aprobado": False, "issues": mecanicas, "razon": "reglas en código"}
                continue
            val = self.validate_reescritura(ficha=ficha, redactado=redactado,
                                            keywords=objetivo)
            if val["aprobado"]:
                return {"aprobado": True, "intentos": intento, "validacion": val,
                        "edited": redactado}
            feedback = list(val.get("issues") or []) or [val.get("razon") or "rechazada"]
        val = val or {"issues": mecanicas}
        val["aprobado"] = False
        return {"aprobado": False, "intentos": max_passes, "validacion": val,
                "edited": redactado}

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
            mecanicas = check_reglas(
                last_edited, original_description=original_desc, keywords=objetivo,
                datos_ficha=" ".join([*(ctx.get("attributes") or ()),
                                      ctx.get("current_short_description") or "",
                                      last_edited.get("h1") or "", ctx.get("brand") or "",
                                      *(ctx.get("categories") or ())]))
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
