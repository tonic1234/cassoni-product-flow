# -*- coding: utf-8 -*-
"""La preparación del control sin tienda usa las mismas reglas que el orquestador."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from control_alex_sin_tienda import CONTROL, preparar  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent


def _ref(nombre):
    refs = json.loads((RAIZ / "evidencia/referencia-seo.json").read_text(encoding="utf-8"))
    orig = {f["url"]: f.get("descripcion_original") or "" for f in
            json.loads((RAIZ / CONTROL).read_text(encoding="utf-8"))["fichas"]}
    r = next(f for f in refs if f["nombre"].startswith(nombre))
    return r, orig[r["url"]]


def test_rock_como_alex():
    ref, desc = _ref("Rock")
    ficha, objetivos, _ = preparar(ref, desc, 1000)
    assert ficha["h1_fijo"] == "Rock Marble Coffee Table by Rugiano"
    assert {o["keyword"] for o in objetivos} == {"rugiano coffee table", "marble table", "wood table"}


def test_bakkarat_ofrece_las_genericas_de_alex():
    ref, desc = _ref("Bakkarat")
    ficha, _, _ = preparar(ref, desc, 1000)
    kws = [k for k, _, _ in ficha["genericas_opcionales"]]
    assert "dining table in glass" in kws and "glass table" in kws


def test_cleopatra_h1_fijo_como_alex():
    ref, desc = _ref("Cleopatra")
    ficha, _, r = preparar(ref, desc, 1000)
    assert ficha["h1_fijo"] == "Cleopatra Wood and Leather Dining Chair by OAK"
