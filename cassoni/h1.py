# -*- coding: utf-8 -*-
"""H1 por plantilla: `{Nombre} by {Marca}` (decisión del equipo SEO, 3-nov-2026).

El H1 deja de pasar por el LLM: es una función determinista para que TODAS las
fichas tengan la misma estructura visual. Se escribe en el campo `name` de
WooCommerce. Idempotente: aplicarla dos veces da el mismo resultado.

Casos borde:
- el nombre ya termina en "by {Marca}"   → queda igual (no "by X by X");
- el nombre empieza con la marca          → se saca del principio y va al final;
- la ficha no tiene marca                 → el nombre queda como está + aviso;
- entidades HTML (&amp;, &#8217;)         → se decodifican antes de armar.
"""
from __future__ import annotations

import html
import re

_WS = re.compile(r"\s+")


def _limpio(s: str) -> str:
    return _WS.sub(" ", html.unescape(s or "")).strip()


def h1_plantilla(nombre: str, marca: str) -> tuple[str, str]:
    """Devuelve (h1, aviso). `aviso` vacío = se aplicó la plantilla sin dudas."""
    nombre, marca = _limpio(nombre), _limpio(marca)
    if not nombre:
        return "", "la ficha no tiene nombre"
    if not marca:
        return nombre, "sin marca: el H1 queda como el nombre actual"
    sufijo = re.compile(r"\s+by\s+" + re.escape(marca) + r"$", re.I)
    if sufijo.search(nombre):
        base = sufijo.sub("", nombre).strip()
        return f"{base} by {marca}", ""
    prefijo = re.compile(r"^" + re.escape(marca) + r"\b[\s\-–—:|]*", re.I)
    base = prefijo.sub("", nombre).strip() or nombre
    return f"{base} by {marca}", ""
