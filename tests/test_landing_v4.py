# -*- coding: utf-8 -*-
"""La landing v4 se arma con los datos de hoy, nombra a Alex y dice que todo es en seco."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from landing_v4 import armar  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent


def test_arma_y_cumple_lo_que_promete(monkeypatch):
    monkeypatch.chdir(RAIZ)
    html = armar("evidencia/2026-11-23-control-alex-sin-tienda-v3-vs-seo.json",
                 "evidencia/2026-11-17-tanda-reglas3.json", "", "23-nov", "nota")
    assert html.startswith("<!doctype html>") and "</html>" in html
    assert html.count("Alex") >= 8
    assert "Todo en seco" in html and "nada se escribió en la tienda" in html
    assert '"historial":[{"fecha":"13-nov"' in html
    assert "</script><" not in html.split('id="datos">')[1].split("</script>")[0]
