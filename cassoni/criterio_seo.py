# -*- coding: utf-8 -*-
"""Criterio del SEO, aprendido de su documento del 6-nov-2026 ("Cómo hacerlo por
ficha"): qué keywords elige para cada descripción y cómo la escribe.

Lo que muestra el documento (10 fichas, 22 keywords):
- variantes del nombre por las que la ficha YA aparece en Google ('cruise couch',
  824 impresiones; 'tiffany mirror', 492; 'shibari chairs', 100), sin piso de volumen;
- marca + tipo ('rugiano coffee table', 'visionnaire chair');
- una genérica corta de material o tipo ('marble table', 'glass table', 'wall sconce').

En vez de reglas a mano, el agente le muestra al LLM las elecciones reales del SEO
como ejemplos. Para medir si se parece al SEO en las MISMAS fichas sin hacer
trampa, cada ficha se procesa viendo las otras nueve, nunca la propia
(`excluir_url`): es la misma situación que una ficha nueva del catálogo.
"""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import Iterable, Optional

from .checklist import strip_html
from .investigacion import materiales_del_texto, valores_de_atributos
from .keywords import PALABRAS_SENSIBLES, parece_typo

log = logging.getLogger(__name__)

MAX_GSC = 25
MAX_GENERICAS = 15
MAX_EJEMPLOS = 9
# palabras que convierten una búsqueda en otra cosa que comprar esta ficha
_FUERA = re.compile(r"\b(price|prices|cost|costs|cheap|used|for sale|near me|diy|how|what|"
                    r"why|who|where|when|is|are|review|reviews|vs|company|job|jobs|"
                    r"site|cassoni|meaning|definition|wiki)\b", re.I)
# muebles en otros idiomas que llegan por GSC ('specchio tiffany', 'cama hermes')
_OTRO_IDIOMA = {"specchio", "specchi", "espejo", "espejos", "cama", "camas", "mesa", "mesas",
                "silla", "sillas", "sillon", "sofa cama", "sedia", "sedie", "divano", "divani",
                "poltrona", "poltrone", "tavolo", "tavoli", "letto", "letti", "lampada",
                "lampara", "lampadario", "mueble", "muebles", "mobili", "mobile", "kerusi",
                "stuhl", "tisch", "spiegel", "fauteuil", "miroir", "cadeira",
                "mesita", "tapete", "alfombra", "divan", "stol", "sessel", "lampe"}
# tipo de EE. UU. → otras formas con que se busca el mismo producto
_SINONIMOS = {"wall sconce": ["wall light"], "pendant light": ["pendant lamp"],
              "ceiling lamp": ["ceiling light"], "sofa": ["couch"],
              "outdoor sofa": ["outdoor couch"], "nightstand": ["bedside table"]}


def _plano(s: str) -> str:
    return unicodedata.normalize("NFKD", (s or "").lower()).encode("ascii", "ignore").decode()


def clave(kw: str) -> str:
    """'Cleopatra's Chair' ~ 'cleopatra chair'; 'shibari chairs' ~ 'shibari chair'."""
    t = _plano(kw).replace("&", " and ").replace("'s ", " ").replace("’s ", " ")
    w = re.findall(r"[a-z0-9]+", t)
    return " ".join(x[:-1] if len(x) > 3 and x.endswith("s") and not x.endswith("ss") else x
                    for x in w if x != "s")


# --- candidatas ---------------------------------------------------------------
def candidatas_gsc(filas: Iterable[dict], nombre: str, marca: str) -> list[dict]:
    """Búsquedas por las que la ficha ya aparece (posición ≤ 30, ≥ 2 impresiones),
    sin tipeos, contenido sensible, otros idiomas ni intención que no sea comprar."""
    out, vistas = [], set()
    for f in sorted(filas, key=lambda f: -(f.get("impressions") or 0)):
        kw = (f.get("keyword") or "").strip()
        k = kw.lower()
        if (not kw or k in vistas or (f.get("impressions") or 0) < 2
                or (f.get("position") or 99) > 30 or not kw.isascii()
                or set(_plano(kw).split()) & (PALABRAS_SENSIBLES | _OTRO_IDIOMA)
                or "_" in kw or _FUERA.search(kw)
                or f.get("spell") or parece_typo(kw, f"{nombre} {marca}")):
            continue
        vistas.add(k)
        out.append({"keyword": kw, "origen": "gsc", "impresiones": f.get("impressions"),
                    "posicion": round(f.get("position") or 0, 1), "volumen": f.get("volume")})
    return out[:MAX_GSC]


def genericas(nombre: str, marca: str, tipo: str, atributos: Iterable[str],
              descripcion: str) -> list[str]:
    """Genéricas armadas SOLO con datos de la ficha: material × tipo ('marble table',
    'marble coffee table'), dos materiales ('wood and leather chair'), tipo en
    material ('dining table in glass'), marca × tipo ('rugiano sofas'), el tipo y
    sus sinónimos de EE. UU. ('wall sconce', 'wall light'), 'italian X'."""
    tipo = _plano(tipo)
    if not tipo:
        return []
    nucleo = tipo[len("outdoor "):] if tipo.startswith("outdoor ") else tipo
    cabeza = nucleo.split()[-1]
    texto = " ".join([nombre, *atributos, strip_html(descripcion)])
    mats = materiales_del_texto(texto)[:4]
    estilo = [v for v in valores_de_atributos(atributos) if v not in mats][:2]
    out: list[str] = [tipo, *_SINONIMOS.get(tipo, []), *_SINONIMOS.get(nucleo, [])]
    for m in mats + estilo:
        out += [f"{m} {cabeza}", f"{m} {nucleo}"]
    for i, m1 in enumerate(mats):
        for m2 in mats[i + 1:]:
            out += [f"{m1} and {m2} {cabeza}", f"{m2} and {m1} {cabeza}"]
        if nucleo != cabeza:
            out.append(f"{nucleo} in {m1}")
    if marca:
        m = _plano(marca)
        out += [f"{m} {cabeza}", f"{m} {cabeza}s", f"{m} {nucleo}"]
    if re.search(r"\b(italy|italian)\b", _plano(texto)):
        out.append(f"italian {cabeza}")
    vistas, limpio = set(), []
    for s in out:
        s = " ".join(s.split())
        if s and s not in vistas:
            vistas.add(s)
            limpio.append(s)
    return limpio


def con_volumen(genericas_: list[str], vol: dict) -> list[dict]:
    out = []
    for g in genericas_:
        v = (vol.get(g.lower()) or {}).get("volume")
        if v:
            out.append({"keyword": g, "origen": "generica", "volumen": v})
    return sorted(out, key=lambda c: -c["volumen"])[:MAX_GENERICAS]


# --- referencia del SEO -------------------------------------------------------
class Referencia:
    """Las fichas que hizo el SEO, con las candidatas que el agente les arma."""

    def __init__(self, fichas: list[dict]):
        self.fichas = [f for f in fichas if f.get("url")]

    @classmethod
    def cargar(cls, ruta: str) -> Optional["Referencia"]:
        if not ruta:
            return None
        p = Path(ruta)
        if not p.exists():
            log.warning("No está la referencia del SEO (%s): sigo sin ejemplos", ruta)
            return None
        return cls(json.loads(p.read_text(encoding="utf-8")))

    def ejemplos(self, excluir_url: str = "", n: int = MAX_EJEMPLOS) -> list[dict]:
        propia = (excluir_url or "").rstrip("/")
        return [f for f in self.fichas if f["url"].rstrip("/") != propia][:n]


def _fila(c: dict) -> str:
    if c["origen"] == "gsc":
        return (f"- {c['keyword']} · ya aparece: {c.get('impresiones')} impresiones, "
                f"posición {c.get('posicion')}, volumen {c.get('volumen') or 's/d'}")
    return f"- {c['keyword']} · genérica, volumen {c.get('volumen')}"


def _bloque_ficha(f: dict) -> str:
    return (f"Ficha: {f['nombre']} · marca {f.get('marca') or '-'} · tipo {f.get('tipo') or '-'}\n"
            f"Materiales y datos: {', '.join(f.get('materiales') or []) or '-'}\n"
            f"CANDIDATAS:\n" + "\n".join(_fila(c) for c in f.get("candidatas") or []))


SISTEMA_SELECCION = """Sos el SEO de cassoni.com (muebles de lujo italianos, venta en
EE. UU.). Para cada ficha elegís de 1 a 3 keywords para meter en la descripción
larga. Elegís SOLO de la lista de CANDIDATAS, copiando la keyword tal cual.
(Los nombres de abajo son inventados; tus criterios reales están en los EJEMPLOS.)

Cómo elegís:
- Primero una variante del nombre por la que la ficha YA aparece en Google y que
  agregue algo al nombre: otra palabra para el tipo, el plural, un complemento
  ('marlo couch' o 'marlo chairs' para Marlo Sofa). Pesan las impresiones, no el
  volumen.
- NUNCA el nombre del producto tal cual ni su forma corta ('marlo sofa', 'marlo',
  'vela lamp' para Vela Wall Lamp): eso ya lo cubre el H1.
- Marca + tipo si aparece entre las candidatas ('ostra sideboards'), aunque tenga
  poco volumen.
- Como mucho dos genéricas, en su forma más CORTA y solo del material principal o
  del tipo que la ficha realmente tiene ('walnut table' antes que 'walnut console
  table'; 'pendant light'). Nada de genéricas de otro material secundario.
- Menos es más: si solo una candidata cumple, elegí una. No completes hasta 3.
- Nunca: otro producto, otra marca, otro idioma, precio, información, navegación
  ajena ('marlo couch company'), ni un material o rasgo que la ficha no tenga.
- No repitas dos variantes de la misma búsqueda ('marlo couch' y 'marlo couches').
"""


class SelectorSEO:
    def __init__(self, llm, model: str, referencia: Optional[Referencia]):
        self.llm, self.model, self.ref = llm, model, referencia

    def elegir(self, ficha: dict, excluir_url: str = "") -> dict:
        """`ficha`: nombre, marca, tipo, materiales, candidatas. Devuelve
        {elegidas: [candidata + por_que], descartadas: [...]}."""
        cands = ficha.get("candidatas") or []
        if not cands:
            return {"elegidas": [], "descartadas": []}
        ejemplos = self.ref.ejemplos(excluir_url) if self.ref else []
        bloque = "\n\n".join(
            f"EJEMPLO {i}\n{_bloque_ficha(e)}\nTU ELECCIÓN: "
            + json.dumps(e.get("keywords_seo") or [], ensure_ascii=False)
            for i, e in enumerate(ejemplos, 1))
        user = (f"{bloque}\n\nAHORA ESTA FICHA\n{_bloque_ficha(ficha)}\n\n"
                'Responde SOLO con JSON: {"keywords": [{"keyword": "<de la lista>", '
                '"por_que": "<una frase>"}]}')
        res = self.llm.complete_json(SISTEMA_SELECCION, user, model=self.model,
                                     temperature=0.2, max_tokens=16000)
        exactas = {c["keyword"].lower(): c for c in cands}
        por_clave = {}
        for c in cands:
            por_clave.setdefault(clave(c["keyword"]), c)
        elegidas, vistas = [], set()
        for k in (res or {}).get("keywords") or []:
            kw = (k.get("keyword") or "").strip().lower() if isinstance(k, dict) else ""
            c = exactas.get(kw) or por_clave.get(clave(kw))
            if c and clave(kw) not in vistas and len(elegidas) < 3:
                vistas.add(clave(kw))
                elegidas.append({**c, "keyword": c["keyword"], "por_que": k.get("por_que", ""),
                                 "volume": c.get("volumen"), "impressions": c.get("impresiones"),
                                 "origen": c["origen"]})
        elegidas_k = {e["keyword"].lower() for e in elegidas}
        return {"elegidas": elegidas,
                "descartadas": [{"keyword": c["keyword"], "motivo": "no la eligió el criterio SEO"}
                                for c in cands if c["keyword"].lower() not in elegidas_k]}


def ejemplos_de_redaccion(referencia: Optional[Referencia], excluir_url: str = "",
                          n: int = MAX_EJEMPLOS) -> str:
    """Descripciones del SEO como ejemplo de estilo (nunca la de la propia ficha)."""
    if not referencia:
        return ""
    partes = []
    for e in referencia.ejemplos(excluir_url, n):
        partes.append(f"H1: {e['h1_seo']}\nKeywords: {', '.join(e.get('keywords_seo') or [])}\n"
                      f"Descripción:\n{e['descripcion_seo']}")
    return "\n\n---\n\n".join(partes)
