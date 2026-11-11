# -*- coding: utf-8 -*-
"""Redactor — reescribe H1 y descripción larga con la plantilla del equipo SEO
(devolución del 6-nov-2026, pestaña "Cómo hacerlo por ficha").

Diferencia con cassoni/editor.py (edición quirúrgica): acá la descripción se
REESCRIBE desde los datos de la ficha. Lo que no cambia es la regla de oro:
nada inventado. Todo dato sale de la descripción original, la corta y los
atributos de WooCommerce, y los números se controlan en código
(checklist.check_reescritura).

Plantilla: la ESTRUCTURA que usa el SEO en su devolución (apertura, secciones
con título, consejo de compra, medidas en pulgadas, enlace a la categoría). La
hoja del SEO es una REFERENCIA de calidad, no un texto a imitar: ningún H1,
título de sección ni frase de esa hoja aparece en este prompt. Los ejemplos de
abajo son inventados y de tipos de producto que no están en la hoja, para que
el agente no "sepa" las respuestas de las fichas de ajuste.
"""
from __future__ import annotations

import html
import re
from typing import Iterable

from .checklist import check_reescritura, strip_html
from .config import Config
from .h1 import verificar_h1
from .llm import LLMClient, LLMError

_FRAC = re.compile(r'(\d+)\s*["”″]\s*(\d+/\d+)')     # 33"1/2 → 33 1/2"
_PULG = re.compile(r'(\d+(?: \d+/\d+)?)["”″]')
_EJE = {"W": "wide", "D": "deep", "H": "high", "SH": "seat height", "AH": "arm height"}


def medidas_ee_uu(atributos: Iterable[str]) -> list[str]:
    """Medidas del atributo Size en el formato de EE. UU. que usa el SEO:
    '102"5/8W x 33"1/2D x 28"H' → '102 5/8" W x 33 1/2" D x 28" H'."""
    out = []
    for a in atributos:
        nombre, _, valor = a.partition(":")
        if nombre.strip().lower() not in ("size", "dimensions", "overall dimensions"):
            continue
        v = html.unescape(valor)
        v = _FRAC.sub(lambda m: f'{m.group(1)} {m.group(2)}"', v)
        v = re.sub(r'(["”″])\s*([A-Z]{1,2})\b', r"\1 \2", v)
        v = re.sub(r'(\d+/\d+)"\s*"', r'\1"', v)
        out.extend(p.strip() for p in re.split(r",\s*(?=[Ø~\d])", v) if p.strip())
    return out


SYSTEM_PROMPT = """Sos el redactor SEO de cassoni.com, tienda de muebles de lujo
italianos que vende en EE. UU. Reescribís el H1 y la descripción larga de una ficha
con la plantilla del equipo SEO. Escribís en inglés de EE. UU.

REGLA DE ORO: NADA INVENTADO. Cada dato (material, acabado, medida, diseñador,
origen, uso, cantidad de opciones) tiene que estar en la descripción original, la
descripción corta o los atributos. Si la ficha no lo dice, no existe. No completes
con lo que sabés de la marca o del modelo. Los números van EXACTOS como en la ficha.

H1 — fórmula: {Modelo} + {rasgo} + {Tipo} + by {Marca}
- {Modelo} y {Tipo} vienen dados: usalos tal cual.
- {rasgo}: 1 a 3 palabras de la ficha que más distinguen al producto para quien
  busca en Google: material, forma o tamaño, técnica de fabricación, construcción
  o tecnología. Si es un material, el de la parte que se ve y se elige (la tapa,
  el tapizado, la pantalla, el cuerpo), no el de una pieza menor. Ejemplos inventados: "Aria Walnut Sideboard", "Nube Oval Pendant
  Light", "Delta Hand-Knotted Wool Rug".
- Si lo que distingue es una pieza del producto (patas, base, pantalla, estructura),
  puede ir con "with" después del tipo: "Mira Lounge Chair with Oak Legs".
- Nunca un rasgo vago ("Shaped", "Stylish", "Elegant", "Refined", "Exclusive",
  "Designer") ni el estilo de catálogo ("Glamour", "Contemporary").
- Sin códigos de catálogo, sin la marca repetida, máximo 9 palabras antes de "by".
- Si hay otra ficha con el mismo nombre, el rasgo tiene que distinguirla.

DESCRIPCIÓN — HTML con solo <p>, <h2>, <ul>, <li>, <strong>, <a>:
1. Apertura (<p>, 1 a 3 oraciones, hasta 45 palabras): qué es (rasgo + tipo), quién
   lo diseñó si la ficha lo dice, de qué marca, el material principal. "Made in
   Italy." solo si la ficha dice Italy o Italian.
2. Una o dos secciones, cada una con un <h2> corto en MAYÚSCULAS (2 a 5 palabras)
   que nombre lo que esa sección resuelve para ESTE producto (inventado, para un
   aparador: "DOORS AND DRAWERS"; para una alfombra: "PILE AND CARE"). Nunca
   genérico ("FEATURES", "OVERVIEW", "DETAILS"). Debajo, un <p> corto o una lista
   <ul><li> cuando hay opciones (acabados, tapizados, tamaños, datos técnicos).
3. Al menos una frase útil para decidir la compra, armada con datos de la ficha:
   dónde entra, qué incluye y qué no, cómo elegir entre tamaños o versiones. Podés
   hablarle al lector en segunda persona.
4. Medidas: solo de la lista MEDIDAS, en pulgadas y con el formato dado. Una o dos
   que ayuden a decidir, no la tabla entera.
5. Un solo enlace: <a href="{URL de la categoría}">…</a> sobre una frase que nombre
   el tipo de producto en plural. Ningún otro enlace.
6. Keywords objetivo: cada una EXACTA (mismas palabras, mismo orden) 1 o 2 veces,
   en una oración que explique algo real del producto; la primera, en la apertura.
   Si una keyword NO entra de forma natural (cambia el sentido, obliga a una
   sintaxis rara o a una oración que solo existe para ella), NO la fuerces: dejala
   afuera y ponela en "omitidas" con el motivo. Una keyword forzada es peor que
   ninguna.
7. Entre 80 y 170 palabras en total.

TONO: sobrio, concreto, oraciones cortas. Prohibido: "presence", "focal point",
"statement piece", "elevate", "to the room", "any interior", "brings a", "adds a
touch", "perfect for", "must-have", "tailored", "composed", "timeless elegance".
No repitas la misma idea en dos lugares. No nombres las colecciones internas de
la tienda ("New Glamour Collection", "New Brand! Discover ...", "New Outdoor
Collection"): son menús de cassoni.com, no del producto.
"""


def _json_schema() -> str:
    return ('{"h1": "<H1 con la fórmula>", "description": "<HTML>", '
            '"keywords": [{"keyword": "<exacta>", "donde": "<oración donde quedó>"}], '
            '"omitidas": [{"keyword": "<la que no entró>", "motivo": "<por qué>"}]}')


class Redactor:
    def __init__(self, config: Config, llm: LLMClient):
        self.cfg = config
        self.llm = llm

    def redactar(self, *, ficha: dict, keywords: list[dict],
                 feedback: list[str] | None = None) -> dict:
        """`ficha`: url, nombre, marca, modelo, tipo, categorias, url_categoria,
        atributos, medidas, descripcion, corta, mismo_nombre. Devuelve
        {h1, description, keywords} o lanza LLMError."""
        objetivo = [k["keyword"] for k in keywords if k.get("keyword")]
        hermanas = "\n".join(
            f"- {h['name']} de {h['marca'] or '(sin marca)'}"
            + (f", medidas {h['medida']}" if h.get("medida") else "")
            for h in ficha.get("mismo_nombre") or []) or "(ninguna)"
        bloque_feedback = ""
        if feedback:
            bloque_feedback = ("\n\nTU VERSIÓN ANTERIOR FUE RECHAZADA. Corregí TODO esto:\n"
                               + "\n".join(f"- {i}" for i in feedback))
        user = f"""Ficha: {ficha['url']}
Nombre actual: {ficha['nombre']}
Marca: {ficha['marca'] or '(sin marca)'}
Modelo (para el H1): {ficha['modelo']}
Tipo en inglés de EE. UU. (para el H1): {ficha['tipo'] or '(decidilo de la categoría)'}
Categoría: {' > '.join(ficha.get('categorias') or []) or '(sin dato)'}
URL de la categoría (el único enlace): {ficha.get('url_categoria') or '(no hay: sin enlace)'}
Otras fichas con el mismo nombre:
{hermanas}

ATRIBUTOS:
{chr(10).join(f'- {html.unescape(a)}' for a in ficha.get('atributos') or []) or '(ninguno)'}

MEDIDAS (en pulgadas, usalas con este formato):
{chr(10).join(f'- {m}' for m in ficha.get('medidas') or []) or '(ninguna: no pongas medidas)'}

DESCRIPCIÓN CORTA ACTUAL:
{strip_html(ficha.get('corta') or '') or '(vacía)'}

DESCRIPCIÓN LARGA ACTUAL (fuente de datos; se reescribe):
{strip_html(ficha.get('descripcion') or '')}

KEYWORDS OBJETIVO (exactas, 1 o 2 veces cada una):
{chr(10).join(f'- {k}' for k in objetivo) or '(ninguna: escribí la ficha igual)'}

Responde SOLO con JSON:
{_json_schema()}{bloque_feedback}"""
        res = self.llm.complete_json(SYSTEM_PROMPT, user, model=self.cfg.llm_editor_model,
                                     temperature=0.4, max_tokens=12000)
        if not isinstance(res, dict) or not (res.get("description") or "").strip():
            raise LLMError("El redactor no devolvió una descripción")
        return {"h1": marca_exacta(" ".join(str(res.get("h1") or "").split()),
                                   ficha.get("marca") or ""),
                "description": res.get("description", ""),
                "keywords": [k for k in (res.get("keywords") or []) if isinstance(k, dict)],
                "omitidas": [k for k in (res.get("omitidas") or []) if isinstance(k, dict)
                             and k.get("keyword") in objetivo]}


def fuentes_de(ficha: dict) -> str:
    """Todo lo que la ficha dice: contra esto se controlan números y palabras."""
    return " ".join([ficha.get("nombre") or "", ficha.get("marca") or "",
                     *(ficha.get("categorias") or []),
                     *(html.unescape(a) for a in ficha.get("atributos") or []),
                     *(ficha.get("medidas") or []),
                     strip_html(ficha.get("descripcion") or ""),
                     strip_html(ficha.get("corta") or "")])


def marca_exacta(h1: str, marca: str) -> str:
    """'… by Oak' → '… by OAK': la marca va como la escribe la tienda."""
    if marca and h1.lower().endswith(f" by {marca.lower()}"):
        return h1[: -len(marca)] + marca
    return h1


def controles(ficha: dict, redactado: dict, keywords: list[str]) -> list[str]:
    """Reglas en código: H1 con la fórmula y nada inventado + descripción. Las
    keywords que el redactor declaró omitidas (no entraban natural) no se exigen."""
    omitidas = {(o.get("keyword") or "").lower() for o in redactado.get("omitidas") or []}
    keywords = [k for k in keywords if k.lower() not in omitidas]
    fuentes = fuentes_de(ficha)
    issues = [f"H1: {i}" for i in verificar_h1(
        redactado.get("h1") or "", nombre=ficha["nombre"], marca=ficha["marca"],
        tipo=ficha["tipo"], texto_ficha=fuentes)]
    issues += check_reescritura(redactado, keywords=keywords, fuentes=fuentes,
                                url_categoria=ficha.get("url_categoria") or "")
    return issues
