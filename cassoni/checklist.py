# -*- coding: utf-8 -*-
"""Checklist duro del agente SEO — reglas verificables EN CÓDIGO (sin LLM).

La spec (docs/REGLA-SEO-FICHAS.md + cassoni/reglas.py) tiene dos naturalezas:
- reglas creativas (redacción, tono) → LLM (editor/validador);
- reglas MECÁNICAS (longitudes, conteos, repeticiones, anti-canibalización) → acá,
  deterministas y testeables, para que el gate no dependa de la suerte del prompt.

check_reglas(editado, original, keywords) -> list[str]  (issues; vacío = pasa)
html_inseguro(original, editado) -> list[str]
filtrar_canibalizacion(candidatas, principals_ya_usadas, categorias, blogs_guia) -> dict
"""
from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser
from typing import Iterable

from . import reglas

# --- utilidades de texto ---
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(html: str) -> str:
    """Saca tags HTML/entidades; deja el texto plano."""
    text = _TAG_RE.sub(" ", html or "")
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
    return _WS_RE.sub(" ", text).strip()


def word_count(html: str) -> int:
    """Cantidad de palabras del texto (sin HTML)."""
    return len(strip_html(html).split())


def h2_count(html: str) -> int:
    """Cantidad de H2 en el HTML (case-insensitive)."""
    return len(re.findall(r"<h2\b[^>]*>", html or "", flags=re.I))


def norm(s: str) -> str:
    """Normalización para comparar keywords: minúsculas + espacios colapsados."""
    return _WS_RE.sub(" ", (s or "").strip().lower())


def kw_exacta_en(texto: str, kw: str) -> bool:
    """True si `kw` está en `texto` EXACTA (palabra completa, case/espacios
    normalizados). 'sofá' NO matchea dentro de 'sofás'."""
    t, k = norm(texto), norm(kw)
    if not k:
        return False
    return re.search(r"(?<!\w)" + re.escape(k) + r"(?!\w)", t) is not None


def usos_de(kw: str, texto: str) -> int:
    """Cuántas veces aparece `kw` exacta (palabra completa) en `texto`."""
    t, k = norm(texto), norm(kw)
    if not k:
        return 0
    return len(re.findall(r"(?<!\w)" + re.escape(k) + r"(?!\w)", t))


# --- reglas mecánicas ---
_SENT_RX = re.compile(r"(?<=[.!?])\s+")   # separador de oraciones
# el HTML real viene del scraping con puntos pegados ('living area.Made in Italy'):
# sin esto la frase se lee como UNA oración y el editor que la escribe bien queda
# penalizado (falso negativo medido en el piloto del 2-nov)
_PUNT_PEGADA_RX = re.compile(r"([.!?])(?=[A-Za-zÁÉÍÓÚÑÜáéíóúñü])")
_BLOQUE_RX = re.compile(r"</(?:p|h1|h2|h3|li|div|section|blockquote|tr)>", re.I)
# palabras funcionales que no cuentan para la regla anti-repetición
_FUNCIONALES = {
    "de", "la", "el", "los", "las", "con", "para", "por", "que", "un", "una",
    "unos", "unas", "y", "en", "del", "al", "su", "sus", "se", "no", "más",
    "mas", "the", "and", "for", "with", "its", "this", "that", "are", "can",
    "into", "from", "has", "have", "was", "were", "also", "como", "sobre",
    "cada", "entre", "desde", "hasta", "them", "their", "they", "there",
}


def oraciones(html: str) -> list[str]:
    """Oraciones del texto (sin HTML), normalizadas y no vacías. No cruza
    fronteras de bloque: un texto de H2 no se pega a la oración del párrafo."""
    out = []
    for bloque in _BLOQUE_RX.split(html or ""):
        texto = _PUNT_PEGADA_RX.sub(r"\1 ", strip_html(bloque))
        for s in _SENT_RX.split(texto):
            n = norm(s)
            if len(n) > 2:
                out.append(n)
    return out


def conservacion(original: str, editado: str) -> float:
    """Fracción de oraciones del ORIGINAL que siguen intactas en la edición.
    1.0 = nada se tocó; 0.0 = reescritura total. Es la medición de la regla
    'editar sobre el texto actual, nunca reescribir' (requisito Antonio 18-sep)."""
    orig = oraciones(original)
    if not orig:
        return 1.0
    edit_norm = set(oraciones(editado))
    conservadas = [o for o in orig if o in edit_norm]
    return len(conservadas) / len(orig)


def _clave_palabras(kw: str) -> set[str]:
    """Huella de una keyword: palabras significativas, sin acentos y sin plural
    final ('sofa', 'sofas' y 'sofá' colisionan entre sí)."""
    out: set[str] = set()
    for w in strip_html(kw).lower().split():
        w = unicodedata.normalize("NFKD", w).encode("ascii", "ignore").decode()
        w = w.strip(".,;:()[]¡!¿?\"'")
        if len(w) < 4 or w in _FUNCIONALES:
            continue
        if len(w) > 4 and w.endswith("s"):
            w = w[:-1]
        out.add(w)
    return out


def seleccionar_diversas(candidatas: list[dict], max_sec: int = 3,
                         ignorar: Iterable[str] = ()) -> dict:
    """Elige hasta `max_sec` keywords que NO compartan palabras entre sí
    (regla de Antonio 18-sep: de todas las que dicen 'sofa' solo se usa UNA),
    priorizando volumen. Devuelve {elegidas, omitidas, faltantes}.

    `faltantes` > 0 = hay que SALIR A BUSCAR más candidatas con palabras
    distintas para completar las secundarias (expansor).
    `ignorar`: palabras que no cuentan para el choque (las del H1: 'brass club
    sofa' y 'leather club sofa' se distinguen por 'brass' y 'leather')."""
    fuera = set()
    for w in ignorar:
        fuera |= _clave_palabras(w)
    ordenadas = sorted(candidatas,
                       key=lambda c: (c.get("opportunity_score") or 0,
                                      c.get("volume") or 0), reverse=True)
    elegidas: list[dict] = []
    omitidas: list[dict] = []
    usadas: set[str] = set()
    for c in ordenadas:
        kw = c.get("keyword", "")
        claves = _clave_palabras(kw) - fuera
        choque = claves & usadas
        if choque:
            otra = next((e["keyword"] for e in elegidas
                         if claves & (_clave_palabras(e["keyword"]) - fuera)), "")
            omitidas.append({
                "keyword": kw, "choca_con": otra,
                "motivo": (f"comparte la palabra '{sorted(choque)[0]}' con '{otra}' "
                           f"(solo se usa una por palabra)")})
            continue
        if len(elegidas) < max_sec:
            elegidas.append(c)
            usadas |= claves
        else:
            omitidas.append({"keyword": kw, "choca_con": "",
                             "motivo": f"ya hay {max_sec} secundarias elegidas"})
    return {"elegidas": elegidas, "omitidas": omitidas,
            "faltantes": max(0, max_sec - len(elegidas))}


def _frecuencia(palabra: str, html: str) -> int:
    return sum(1 for w in strip_html(html).lower().split()
               if w.strip(".,;:()[]¡!¿?\"'") == palabra)


def palabra_dominante(html: str, max_apariciones: int | None = None) -> str:
    """Devuelve la palabra no funcional más repetida del texto, o '' si ninguna
    pasa el límite. Regla anti 'sofa sofa sofa' (Antonio 18-sep)."""
    limite = max_apariciones if max_apariciones is not None else reglas.REPETICION_MAX_PALABRA
    frec: dict[str, int] = {}
    for w in strip_html(html).lower().split():
        w = w.strip(".,;:()[]¡!¿?\"'")
        if len(w) < 4 or w in _FUNCIONALES:
            continue
        frec[w] = frec.get(w, 0) + 1
    if not frec:
        return ""
    top, n = max(frec.items(), key=lambda kv: kv[1])
    return top if n > limite else ""


# medidas: 62"3/8, 28"H, 96 x 43, 74 5/8 inches, 120 cm…
_MEDIDA_RX = re.compile(
    r'\d+\s*(?:["”″]|\b(?:in|inch|inches|cm|mm|m|ft|feet|kg|lbs?)\b)'
    r'|\d+\s*[x×]\s*\d+|\b(?:measures?|dimensions?)\b', re.I)


# --- HTML seguro ---
_TAGS_PROHIBIDOS = {"script", "iframe", "object", "embed", "style", "form", "input",
                    "button", "link", "meta", "base", "frame", "frameset", "svg", "math"}


class _Tags(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags: dict[str, int] = {}
        self.eventos: list[str] = []
        self.urls_peligrosas: list[str] = []
        self.links: set[str] = set()
        self.imagenes: set[str] = set()

    def handle_starttag(self, tag, attrs):
        self.tags[tag] = self.tags.get(tag, 0) + 1
        for nombre, valor in attrs:
            nombre, valor = (nombre or "").lower(), (valor or "").strip()
            if nombre.startswith("on"):
                self.eventos.append(f"{tag} {nombre}")
            if nombre in ("href", "src", "action", "formaction", "srcset"):
                if re.match(r"^\s*(javascript|data|vbscript):", valor, re.I):
                    self.urls_peligrosas.append(valor[:60])
                if nombre == "href":
                    self.links.add(valor)
                elif nombre == "src":
                    self.imagenes.add(valor)


def _tags(html: str) -> _Tags:
    p = _Tags()
    try:
        p.feed(html or "")
    except Exception:
        pass
    return p


def html_inseguro(original: str, editado: str) -> list[str]:
    """Lo que la edición agregó al HTML y no puede llegar a la tienda. El texto del
    LLM se escribe con claves REST de admin: WordPress NO lo filtra."""
    o, e = _tags(original), _tags(editado)
    issues = []
    for tag in sorted(_TAGS_PROHIBIDOS):
        if e.tags.get(tag, 0) > o.tags.get(tag, 0):
            issues.append(f"El HTML agrega una etiqueta prohibida <{tag}>")
    if e.eventos:
        issues.append(f"El HTML tiene atributos de evento ({', '.join(e.eventos[:3])})")
    if e.urls_peligrosas:
        issues.append("El HTML tiene URLs javascript:/data:")
    nuevos = sorted(e.links - o.links)
    if nuevos:
        issues.append(f"La edición agrega enlaces que no estaban: {', '.join(nuevos[:3])}")
    if e.imagenes - o.imagenes:
        issues.append("La edición agrega imágenes que no estaban")
    return issues


# --- modo reescritura (devolución SEO 6-nov-2026) ---
_NUMERO_RX = re.compile(r"\d+(?:[.,]\d+)?(?:/\d+)?")
_TAGS_REESCRITURA = {"p", "h2", "ul", "li", "strong", "em", "a", "br"}
REESCRITURA_MIN_PALABRAS = 55     # el SEO escribe de 62 a 103 (documento 6-nov)
REESCRITURA_MAX_PALABRAS = 140


def numeros(texto: str) -> set[str]:
    """'33 1/2" … 2700K … 1,265' → {'33', '1/2', '2700', '1265'}."""
    out = set()
    for n in _NUMERO_RX.findall(strip_html(texto or "")):
        n = n.replace(",", "") if re.fullmatch(r"\d{1,3},\d{3}", n) else n
        out.add(n)
    return out


def numeros_sin_respaldo(descripcion: str, fuentes: str) -> list[str]:
    """Números de la descripción que no están en la ficha (descripción original,
    atributos, medidas). Una medida o un dato técnico inventado es lo más grave
    que puede escribir el redactor: se controla en código, no con el LLM."""
    permitidos = numeros(fuentes)
    return sorted(n for n in numeros(descripcion) if n not in permitidos)


def check_reescritura(editado: dict, *, keywords: Iterable[str] = (), fuentes: str = "",
                      url_categoria: str = "") -> list[str]:
    """Issues de una descripción REESCRITA con la plantilla del SEO (vacía = cumple).
    No se mide la conservación del original: la plantilla lo reemplaza."""
    issues: list[str] = []
    desc = editado.get("description") or ""
    plano = strip_html(desc)
    wc = word_count(desc)
    if wc < REESCRITURA_MIN_PALABRAS:
        issues.append(f"La descripción es corta: {wc} palabras (mínimo "
                      f"{REESCRITURA_MIN_PALABRAS})")
    if wc > REESCRITURA_MAX_PALABRAS:
        issues.append(f"La descripción es larga: {wc} palabras (máximo "
                      f"{REESCRITURA_MAX_PALABRAS})")
    h2c = h2_count(desc)
    if not 1 <= h2c <= reglas.MAX_H2:
        issues.append(f"La descripción tiene que tener 1 o 2 secciones con título <h2> "
                      f"(tiene {h2c})")
    t = _tags(desc)
    extras = sorted(set(t.tags) - _TAGS_REESCRITURA)
    if extras:
        issues.append(f"Etiquetas HTML no permitidas: {', '.join(extras)}")
    if t.eventos or t.urls_peligrosas:
        issues.append("El HTML tiene atributos de evento o URLs javascript:/data:")
    ajenos = sorted(link for link in t.links if link != url_categoria)
    if ajenos:
        issues.append(f"Solo se permite el enlace a la categoría ({url_categoria or 'ninguna'})"
                      f"; sobra: {', '.join(ajenos[:2])}")
    if t.tags.get("a", 0) > 1:
        issues.append("Hay más de un enlace: va uno solo, a la categoría")
    inventados = numeros_sin_respaldo(desc, fuentes)
    if inventados:
        issues.append(f"Números que la ficha no tiene (dato inventado): "
                      f"{', '.join(inventados[:6])}")
    vacia = _FRASE_VACIA_RX.search(plano)
    if vacia:
        issues.append(f"Frase genérica que no describe este producto («{vacia.group(0)}»)")
    for kw in keywords:
        kw = (kw or "").strip()
        if not kw:
            continue
        usos = usos_de(kw, plano)
        if usos == 0:
            issues.append(f"La keyword '{kw}' no quedó EXACTA en la descripción")
        elif usos > reglas.SEC_MAX_USOS:
            issues.append(f"La keyword '{kw}' aparece {usos} veces (máximo "
                          f"{reglas.SEC_MAX_USOS})")
    return issues


# frases de interiorismo genérico: no dicen nada de ESTE producto (prueba real
# 3-nov: "brings a tailored, architectural presence to the room")
_FRASE_VACIA_RX = re.compile(
    r"\b(presence|focal point|statement piece|elevat\w*|to the room|any (?:room|interior|"
    r"space|home|setting)|conceived (?:for|as)|adds? a touch|brings? a\b|perfect "
    r"(?:for|addition)|must-have|tailored|composed)\b", re.I)
_PALABRAS_ENLACE = {
    "with", "its", "this", "these", "those", "which", "while", "where", "when", "each",
    "both", "more", "most", "than", "then", "very", "such", "other", "piece", "made",
    "italy", "italian", "whose", "within", "among", "across", "their", "there"}
MAX_PALABRAS_NUEVAS = 4      # calibrado con la prueba real: 2-4 = bien, 6-9 = relleno


def _contenido(texto: str) -> set[str]:
    return {w for w in re.findall(r"[a-z][a-z'-]+", strip_html(texto).lower())
            if len(w) >= 4 and w not in _FUNCIONALES and w not in _PALABRAS_ENLACE}


def palabras_nuevas(oracion: str, base: str, keywords: Iterable[str] = ()) -> list[str]:
    """Palabras con contenido de `oracion` que no están en la ficha (`base`) ni en
    las keywords: si son muchas, la oración está inventando o rellenando."""
    conocidas = _contenido(base)
    conocidas |= {w.rstrip("s") for w in conocidas}
    for k in keywords:
        conocidas |= _contenido(k)
    return sorted(w for w in _contenido(oracion)
                  if w not in conocidas and w.rstrip("s") not in conocidas)


def check_reglas(editado: dict, original_description: str = "",
                 keywords: Iterable[str] = (), datos_ficha: str = "") -> list[str]:
    """Issues de la edición (vacía = cumple TODO). Alcance: SOLO la descripción
    larga (el H1 lo arma cassoni/h1.py por plantilla).
    `editado`: {description, ...}. `keywords`: las keywords objetivo, que tienen
    que quedar EXACTAS en la descripción (la pizarra: "detectar que esté o no
    esté esa kw")."""
    issues: list[str] = []
    desc = editado.get("description") or ""
    plain_desc = strip_html(desc)

    # largo: el mínimo de 150 ya no bloquea (prueba real 3-nov: con originales de
    # 10-73 palabras obligaba a rellenar). El máximo se mide contra el original:
    # si ya era largo, solo se controla lo que agrega la edición.
    wc = word_count(desc)
    kws = [k for k in (k.strip() for k in keywords) if k]
    tope = max(reglas.LARGA_MAX_WORDS,
               word_count(original_description) + reglas.PALABRAS_POR_KEYWORD * max(1, len(kws)))
    if wc > tope:
        issues.append(f"La descripción larga supera las {tope} palabras (tiene {wc})")

    # lo AGREGADO: una oración por keyword, cada una con su keyword, sin medidas
    if original_description and kws:
        previas = set(oraciones(original_description))
        agregadas = [o for o in oraciones(desc) if o not in previas]
        if len(agregadas) > len(kws):
            issues.append(f"Se agregaron {len(agregadas)} oraciones para {len(kws)} "
                          f"keyword(s): solo una oración nueva por keyword, sin relleno")
        sueltas = [o for o in agregadas if not any(kw_exacta_en(o, k) for k in kws)]
        if sueltas:
            issues.append(f"Hay {len(sueltas)} oración(es) agregada(s) sin ninguna keyword "
                          f"(relleno): «{sueltas[0][:80]}»")
        base = f"{original_description} {datos_ficha}"
        for o in agregadas:
            vacia = _FRASE_VACIA_RX.search(o)
            if vacia:
                issues.append(f"Frase genérica que no describe este producto "
                              f"(«{vacia.group(0)}»): «{o[:80]}»")
            nuevas = palabras_nuevas(o, base, kws)
            if len(nuevas) > MAX_PALABRAS_NUEVAS:
                issues.append(f"La oración agregada usa {len(nuevas)} palabras que no están "
                              f"en la ficha ({', '.join(nuevas[:6])}): tiene que apoyarse en "
                              f"lo que la ficha ya dice")
        if not any(_MEDIDA_RX.search(k) for k in kws):
            con_medidas = [o for o in agregadas if _MEDIDA_RX.search(o)]
            if con_medidas:
                issues.append("La edición agrega medidas, que ya están en los atributos de "
                              f"la ficha: «{con_medidas[0][:80]}»")

    if original_description:
        ratio = conservacion(original_description, desc)
        if ratio < reglas.CONSERVACION_MIN:
            issues.append(
                f"La descripción larga fue reescrita desde cero: conserva solo "
                f"{ratio:.0%} de las oraciones del original "
                f"(mínimo {reglas.CONSERVACION_MIN:.0%})")

    # se mide lo que AGREGA la edición: si el original ya repetía una palabra
    # (Shibari: 'knot' más de 8 veces), conservarlo no puede ser motivo de rechazo
    dominante = palabra_dominante(desc)
    if dominante and _frecuencia(dominante, desc) <= _frecuencia(dominante, original_description):
        dominante = ""
    if dominante:
        issues.append(
            f"La palabra '{dominante}' se repite demasiado en la descripción larga "
            f"(más de {reglas.REPETICION_MAX_PALABRA} veces, 'sofa sofa sofa' está "
            f"prohibido)")

    h2c = h2_count(desc)
    if h2c > reglas.MAX_H2:
        issues.append(f"La descripción larga tiene más de {reglas.MAX_H2} H2 "
                      f"(tiene {h2c})")

    for kw in keywords:
        kw = (kw or "").strip()
        if not kw:
            continue
        usos = usos_de(kw, plain_desc)
        if usos == 0:
            issues.append(f"La keyword '{kw}' no quedó EXACTA en la descripción")
        elif usos > reglas.SEC_MAX_USOS:
            issues.append(f"La keyword '{kw}' aparece más de {reglas.SEC_MAX_USOS} "
                          f"veces (aparece {usos})")

    issues.extend(html_inseguro(original_description, desc))
    return issues


# --- filtro anti-canibalización (determinista) ---
_BLOG_INTENT = ("como elegir", "cómo elegir", "guía de", "guia de", "top ",
                "mejores", "qué es", "que es", "mejor ")


def _es_consulta_de_categoria(norm_cand: str, cats: set[str]) -> bool:
    """True si la candidata compite con la página de categoría: es la categoría
    exacta o la categoría + pocas palabras genéricas (sin señales de producto)."""
    for c in cats:
        nc = norm(c)
        if norm_cand == nc:
            return True
        if norm_cand.startswith(nc + " "):
            extra = len(norm_cand[len(nc) + 1:].split())
            if extra <= 2:  # "sofas de lujo" sí; "sofas de la coleccion aria" no
                return True
    return False


def filtrar_canibalizacion(
        candidatas: Iterable[str],
        principals_ya_usadas: Iterable[str] = (),
        categorias_como_pagina: Iterable[str] = (),
        blogs_guia: Iterable[str] = ()) -> dict:
    """Aplica el filtro anti-canibalización del documento.

    Devuelve:
      {"aceptadas": [{"keyword": k}, ...],
       "descartadas": [{"keyword": k, "motivo": str, "pertenece_a": str}, ...]}
    """
    principals = {norm(p) for p in principals_ya_usadas}
    cats = set()
    for c in categorias_como_pagina:
        # "Sofas & Sectionals" es la página de "sofas" Y la de "sectionals"
        # (prueba real 3-nov: eligió 'sectionals', 74.000/mes, para un club sofa)
        cats.add(norm(c))
        cats.update(norm(x) for x in re.split(r"\s*(?:&|,|/|\band\b|\by\b)\s*", c) if norm(x))
    blogs = {norm(b) for b in blogs_guia}

    aceptadas, descartadas = [], []
    for cand in candidatas:
        nc = norm(cand)
        if not nc:
            continue
        if nc in principals:
            descartadas.append({
                "keyword": cand,
                "motivo": "ya es la keyword principal de otra ficha",
                "pertenece_a": "otra ficha (keyword principal ya utilizada)",
            })
        elif _es_consulta_de_categoria(nc, cats):
            descartadas.append({
                "keyword": cand,
                "motivo": "compite con la página de categoría",
                "pertenece_a": "página de categoría",
            })
        elif nc in blogs or any(p in nc for p in _BLOG_INTENT):
            descartadas.append({
                "keyword": cand,
                "motivo": "responde mejor a un blog o guía de compra que a una ficha",
                "pertenece_a": "blog o guía de compra",
            })
        else:
            aceptadas.append({"keyword": cand})

    return {"aceptadas": aceptadas, "descartadas": descartadas}