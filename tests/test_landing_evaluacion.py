# -*- coding: utf-8 -*-
"""La página de evaluación se arma desde el JSON de la corrida, sin red.

Lo que se fija acá es lo que ya se rompió una vez: las pestañas, que cada ficha
llegue a la página con su antes/después, y que no queden placeholders sin
reemplazar (`{Marca}` quedó a la vista en la primera versión).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _lote(tmp_path: Path, n: int = 3) -> Path:
    fichas = []
    for i in range(n):
        fichas.append({
            "url": f"https://cassoni.com/product/ficha-{i}/",
            "status": "processed", "reason": "",
            "h1_original": f"Modelo {i} Lamp",
            "h1": f"Modelo {i} Leather Sconce by Marca",
            "descripcion": "<p>Texto nuevo con la keyword <b>leather sconce</b>.</p><h2>Medidas</h2><p>11\" W.</p>",
            "descripcion_original": "<p>Texto viejo.</p>",
            "keywords": ["leather sconce"],
            "keywords_detalle": [{"keyword": "leather sconce", "origen": "gsc", "volume": 120,
                                  "posicion": 8.4}],
            "seleccion": "elegidas: leather sconce (gsc, vol 120) | descartadas: lamp (ya lo dice el H1)",
            "validacion": {"aprobado": True, "issues": []},
            "intentos": 1, "segundos": 20,
        })
    datos = {"meta": {"modo": "reescritura", "llm": "deepseek-flash", "commit": "abc1234",
                      "dry_run": True,
                      "costos": {"usd": 0.02, "dfs_usd": 0.15, "llamadas": 6,
                                 "tokens_in": 1000, "tokens_out": 900}},
             "fichas": fichas}
    p = tmp_path / "lote.json"
    p.write_text(json.dumps(datos), encoding="utf-8")
    return p


def _generar(tmp_path: Path, lote: Path) -> str:
    out = tmp_path / "index.html"
    r = subprocess.run([sys.executable, str(RAIZ / "tools" / "landing_evaluacion.py"),
                        "--json", str(lote), "--out", str(out), "--titulo", "Prueba"],
                       capture_output=True, text=True, cwd=str(RAIZ))
    assert r.returncode == 0, r.stderr
    return out.read_text(encoding="utf-8")


def test_las_cinco_pestanias_existen(tmp_path):
    html = _generar(tmp_path, _lote(tmp_path))
    for tab in ("resumen", "fichas", "rechazadas", "como", "medicion"):
        assert f'data-tab="{tab}"' in html, f"falta la pestaña {tab}"
        assert f'id="{tab}"' in html, f"falta la sección {tab}"


def test_cada_ficha_llega_con_su_antes_y_despues(tmp_path):
    html = _generar(tmp_path, _lote(tmp_path, n=3))
    assert html.count('class="ficha"') == 3
    assert "Modelo 0 Lamp" in html and "<em>Leather Sconce by Marca</em></ins>" in html
    # la keyword se marca en la descripción y en el H1 nuevo
    assert "<mark>leather sconce</mark>" in html
    assert "<em>Leather Sconce by Marca</em>" in html


def test_no_quedan_placeholders_sin_reemplazar(tmp_path):
    html = _generar(tmp_path, _lote(tmp_path))
    sobrantes = re.findall(r"(?<!\{)\{[a-zA-Z_]+\}(?!\})", html)
    assert not sobrantes, f"placeholders sin reemplazar: {sorted(set(sobrantes))}"
    assert "None" not in html


def test_el_validador_y_los_costos_se_ven(tmp_path):
    html = _generar(tmp_path, _lote(tmp_path))
    assert "US$ 0.17" in html                    # 0,02 LLM + 0,15 DataForSEO
    assert "sin observaciones" in html
    assert "dry-run" in html                     # nunca se muestra como escritura
