# -*- coding: utf-8 -*-
"""Fichas que salieron sin datos de Google porque se agotó el tope de DataForSEO."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from rehacer_sin_presupuesto import main, sin_presupuesto  # noqa: E402


def test_marca_nueva():
    assert sin_presupuesto({"dfs_sin_presupuesto": True, "keywords": ["x"]})


def test_lote_viejo_por_el_motivo():
    assert sin_presupuesto({"keywords": [], "seleccion":
                            "descartadas: rock table (sin datos de Google para comprobarla "
                            "(intención en Google))"})


def test_sin_keywords_por_otro_motivo_no_se_rehace():
    assert not sin_presupuesto({"keywords": [], "seleccion": "descartadas: x (pocas impresiones)"})
    assert not sin_presupuesto({"keywords": ["a"], "seleccion": "sin datos de Google"})


def test_solo_listar(tmp_path, capsys):
    lote = {"meta": {}, "fichas": [
        {"url": "u1", "keywords": ["a"], "seleccion": ""},
        {"url": "u2", "keywords": [], "dfs_sin_presupuesto": True}]}
    p = tmp_path / "l.json"
    p.write_text(json.dumps(lote))
    assert main(["--lote", str(p), "--solo-listar"]) == 0
    assert "1 de 2" in capsys.readouterr().out


def test_el_pipeline_expone_el_tope():
    from cassoni.orchestrator import Pipeline

    class F:
        sin_presupuesto = True

    class V:
        fetcher = F()
    p = object.__new__(Pipeline)
    p.volumenes = V()
    assert p.dfs_sin_presupuesto is True
