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
- {rasgo}: 1 o 2 palabras (3 solo si es una técnica compuesta como "Hand-Knotted Wool") de la ficha que más distinguen al producto para quien
  busca en Google: material, forma o tamaño, técnica de fabricación, construcción
  o tecnología. Si es un material, el de la parte que se ve y se elige (la tapa,
  el tapizado, la pantalla, el cuerpo), no el de una pieza menor. Ejemplos inventados: "Aria Walnut Sideboard", "Nube Oval Pendant
  Light", "Delta Hand-Knotted Wool Rug".
- Si lo que distingue es una pieza del producto (patas, base, pantalla, estructura)
  y no hay un material principal, puede ir con "with" después del tipo: "Mira
  Lounge Chair with Oak Legs". Nunca las dos cosas a la vez (rasgo + "with ...").
- Corto: el H1 dice qué es, no lista todo lo que tiene. Un acabado entre varios
  opcionales ("24K Gold", "Extra Clear") no va: va lo que tienen todas las versiones.
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
7. Entre 60 y 110 palabras en total, como las fichas del equipo SEO: corto y concreto.

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
    def __init__(self, config: Config, llm: LLMClient, referencia=None):
        self.cfg = config
        self.llm = llm
        self.referencia = referencia

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
        from .criterio_seo import ejemplos_de_redaccion
        ejemplos = ejemplos_de_redaccion(self.referencia, ficha.get("url", ""))
        bloque_ejemplos = (
            "FICHAS ESCRITAS POR EL EQUIPO SEO (de OTROS productos). Imitá su estructura, "
            "su largo, su tono y cómo meten las keywords; no copies sus datos: los de "
            "esta ficha salen solo de esta ficha. Los títulos de sección van en <h2>." + chr(10) * 2
            + ejemplos + chr(10) * 2 + "=====" + chr(10) * 2) if ejemplos else ""
        user = bloque_ejemplos + f"""Ficha: {ficha['url']}
Nombre actual: {ficha['nombre']}
Marca: {ficha['marca'] or '(sin marca)'}
{('H1 (DADO POR EL EQUIPO SEO: devolvelo tal cual, no lo cambies): ' + ficha['h1_fijo']) if ficha.get('h1_fijo') else ''}
Modelo (para el H1): {ficha['modelo']}{(chr(10) + 'Después del tipo, tal cual (es parte del nombre, no lo saques): ' + ficha['sufijo']) if ficha.get('sufijo') else ''}
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

{_bloque_rasgos(ficha)}{_bloque_opciones(ficha)}{_bloque_genericas(ficha)}{_bloque_marca_ajena(ficha)}KEYWORDS OBJETIVO (exactas, 1 o 2 veces cada una){' — las eligió el equipo SEO con datos. Tienen que entrar al menos 3 (más si están en la lista y entran natural), cada una en una oración que diga algo real del producto; no armes un listado de keywords. Omití una solo si contradice la ficha o no entra natural, con el motivo en omitidas' if ficha.get('keywords_obligatorias') else ''}:
{chr(10).join(f'- {k}' for k in objetivo) or '(ninguna: escribí la ficha igual)'}

Responde SOLO con JSON:
{_json_schema()}{bloque_feedback}"""
        res = self.llm.complete_json(SYSTEM_PROMPT, user, model=self.cfg.llm_editor_model,
                                     temperature=0.4, max_tokens=12000)
        if not isinstance(res, dict) or not (res.get("description") or "").strip():
            raise LLMError("El redactor no devolvió una descripción")
        h1 = ficha.get("h1_fijo") or marca_exacta(" ".join(str(res.get("h1") or "").split()),
                                                  ficha.get("marca") or "")
        return {"h1": h1,
                "description": res.get("description", ""),
                "keywords": [k for k in (res.get("keywords") or []) if isinstance(k, dict)],
                "omitidas": [k for k in (res.get("omitidas") or []) if isinstance(k, dict)
                             and k.get("keyword") in objetivo]}


def _bloque_rasgos(ficha: dict) -> str:
    """Rasgos candidatos para el H1 con su volumen (reglas del SEO, 17-nov)."""
    rasgos = ficha.get("h1_rasgos") or []
    if ficha.get("h1_fijo") or not rasgos:
        return ""
    lista = ", ".join(f"{m} ({v}/mes como '{m} {ficha.get('tipo', '')}')" for m, v in rasgos)
    return ("RASGO DEL H1 — candidatos con su volumen de búsqueda: " + lista + ".\n"
            "Elegí el que tienen TODAS las versiones del producto (no una opción de "
            "tapizado, acabado o tapa); entre los que cumplen, el más buscado. Si ninguno "
            "cumple, usá otro rasgo real de la ficha (forma, técnica, estructura).\n\n")


def _bloque_opciones(ficha: dict) -> str:
    """La parte principal viene en varias opciones (Rock: tapa de madera o de mármol):
    la descripción cubre TODAS, no solo la del H1 (devolución del 18-nov)."""
    ops = ficha.get("opciones") or []
    if len(ops) < 2:
        return ""
    return ("OPCIONES — la parte principal del producto viene en " + " o ".join(ops) + ". "
            "La descripción cubre TODAS las opciones por igual, no solo la del H1: una "
            "sección (o una lista <ul>) con una línea por opción y lo que la ficha dice de "
            "cada una (ej. del SEO: <h2>UPHOLSTERY</h2> con las telas y los cueros). Cada "
            "opción con su keyword objetivo, si la tiene. Si la opción es el tapizado, el "
            "H1 no elige uno: dice \"Upholstered\".\n\n")


def _bloque_marca_ajena(ficha: dict) -> str:
    """La ficha nombra la marca de otro fabricante («Steinway»): su nombre completo es un
    dato de la marca, no del producto, y respalda las búsquedas que lo usan."""
    from .reglas_seo import NOMBRE_COMPLETO
    m = ficha.get("marca_ajena") or ""
    if not m:
        return ""
    completo = NOMBRE_COMPLETO.get(m, m)
    return (f"MARCA EN EL NOMBRE — el nombre del producto dice «{m.title()}»: es la marca "
            f"{completo.title()} (ese es su nombre completo). Una keyword con "
            f"«{completo}» nombra la misma marca que la ficha; no afirma nada nuevo. "
            f"El fabricante de la ficha sigue siendo {ficha.get('marca') or 'el de la ficha'}.\n\n")


def _bloque_genericas(ficha: dict) -> str:
    gen = ficha.get("genericas_opcionales") or []
    if not gen:
        return ""
    lista = ", ".join(f"'{k}' ({v}/mes)" for k, v, _ in gen)
    return ("GENÉRICAS — sumá HASTA DOS de estas, exactas y una vez cada una, con la "
            "misma regla del equipo SEO: su material es EXACTAMENTE el rasgo que pusiste en "
            "el H1 (H1 'Wood and Leather Dining Chair' → 'wood and leather chair', no "
            "'wood chair'), no repiten el H1 tal cual (H1 'Glass Dining Table' → 'dining "
            "table in glass' y 'glass table', no 'glass dining table'), y preferí la forma "
            "corta. Si el H1 no tiene material, ninguna: " + lista + ".\n\n")


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
    # un H1 dado por las reglas del SEO no lo puede cambiar el redactor: no se le
    # piden correcciones que no puede hacer
    issues = [] if ficha.get("h1_fijo") else [f"H1: {i}" for i in verificar_h1(
        redactado.get("h1") or "", nombre=ficha["nombre"], marca=ficha["marca"],
        tipo=ficha["tipo"], texto_ficha=fuentes)]
    if not ficha.get("h1_fijo"):
        h1_plano = " " + " ".join(re.findall(r"[a-z0-9]+", (redactado.get("h1") or "").lower())) + " "
        for parte, que in ((ficha.get("sufijo") or "", "lo que el nombre dice después del tipo"),):
            w = " ".join(re.findall(r"[a-z0-9]+", parte.lower()))
            if w and f" {w} " not in h1_plano:
                issues.append(f"H1: perdió {que}: '{parte}'")
    issues += check_reescritura(redactado, keywords=keywords, fuentes=fuentes,
                                url_categoria=ficha.get("url_categoria") or "")
    if ficha.get("genericas_opcionales"):
        from .reglas_seo import genericas_para_h1, genericas_usadas
        h1 = redactado.get("h1") or ""
        desc = strip_html(redactado.get("description") or "")
        usadas = genericas_usadas(desc, h1, ficha["genericas_opcionales"])
        for kw, _, ok in usadas:
            if not ok:
                issues.append(f"La genérica '{kw}' no es del material del H1: sacala o usá "
                              "la del material que dice el H1")
        # como Alex: si el H1 tiene material, va su genérica (salvo que no entre natural)
        esperadas = genericas_para_h1(h1, ficha["genericas_opcionales"])
        from .reglas_seo import MAX_KEYWORDS
        if esperadas and len(keywords) < MAX_KEYWORDS and not any(ok for _, _, ok in usadas) \
                and not any(k in omitidas for k, _, _ in esperadas):
            issues.append("Falta la genérica del material del H1: sumá "
                          + " o ".join(f"'{k}'" for k, _, _ in esperadas)
                          + " (exacta, en una oración real; si no entra natural, ponela en omitidas)")
    return issues
