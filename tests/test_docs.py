# -*- coding: utf-8 -*-
"""La documentación es ejecutable: si cita un comando, el comando existe.

Un README que promete `--seleccionar` cuando el CLI no lo acepta es peor que no
tener README: el auditor corre el comando, falla y desconfía de todo lo demás.
"""
import re
from pathlib import Path

from cassoni.cli import parse_args

RAIZ = Path(__file__).resolve().parent.parent
DOCS = [RAIZ / "README.md", RAIZ / "PLAN.md"] + sorted((RAIZ / "docs").glob("*.md"))

# `python -m cassoni.cli ... --flag` en cualquier parte de la doc
_CMD = re.compile(r"python\s+-m\s+cassoni\.cli([^\n`]*)")
_FLAG = re.compile(r"(--[a-z][a-z-]*)")


def _flags_citados() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for d in DOCS:
        if not d.exists():
            continue
        for m in _CMD.finditer(d.read_text(encoding="utf-8")):
            out.setdefault(d.name, set()).update(_FLAG.findall(m.group(1)))
    return out


def test_todos_los_flags_citados_existen():
    validos = set(vars(parse_args(["--preflight"])))
    citados = _flags_citados()
    faltantes = {}
    for doc, flags in citados.items():
        # parse_args usa dest con guiones bajos
        desconocidos = {f for f in flags
                        if f.lstrip("-").replace("-", "_") not in validos}
        if desconocidos:
            faltantes[doc] = sorted(desconocidos)
    assert not faltantes, f"la doc cita flags que el CLI no tiene: {faltantes}"


def test_la_doc_principal_existe():
    for nombre in ("README.md", "PLAN.md", "docs/AUDITORIA.md",
                   "docs/ARQUITECTURA.md", "docs/OPERACION.md", "docs/DECISIONES.md"):
        assert (RAIZ / nombre).exists(), f"falta {nombre}"


def test_la_evidencia_citada_existe():
    """Cada archivo de evidencia que la doc nombra tiene que estar en el repo."""
    texto = (RAIZ / "docs" / "AUDITORIA.md").read_text(encoding="utf-8")
    citados = re.findall(r"evidencia/([A-Za-z0-9._/-]+)", texto)
    faltan = [c for c in citados if not (RAIZ / "evidencia" / c).exists()]
    assert not faltan, f"la auditoría cita evidencia que no está: {faltan}"


def test_la_doc_no_tiene_credenciales():
    patrones = re.compile(r"(ck_[a-f0-9]{20,}|cs_[a-f0-9]{20,}|BEGIN [A-Z ]*PRIVATE KEY)")
    for d in DOCS:
        if d.exists():
            assert not patrones.search(d.read_text(encoding="utf-8")), f"secreto en {d}"
