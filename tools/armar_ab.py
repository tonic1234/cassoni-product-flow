# -*- coding: utf-8 -*-
"""Arma la hoja de EVALUACIÓN CIEGA: por ficha, dos versiones (A y B) del H1, las
keywords y la descripción, una del agente y otra del SEO, en un orden al azar con
semilla fija. La clave (qué letra es de quién) va a un archivo aparte que el
evaluador no ve hasta terminar.

Criterios de la rúbrica: los de la columna "Qué falla" de la devolución del SEO
(6-nov-2026), aplicados igual a las dos versiones.

    ./venv/bin/python tools/armar_ab.py --agente evidencia/X-ciega.json \
        --seo seo.csv --semilla 20261111 --out eval.csv --clave clave.json
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import random
import re
from pathlib import Path

CRITERIOS = [
    "1. El H1 dice qué es (tipo, en inglés de EE. UU.)",
    "2. El H1 lleva un rasgo real y distintivo (material, forma, técnica)",
    "3. El H1 no tiene códigos ni se confunde con otra ficha",
    "4. Ninguna keyword es de categoría, de otro tema o de otro producto",
    "5. Ninguna keyword está forzada ni repite lo que ya dice el texto",
    "6. Nada inventado (todo dato está en la ficha)",
    "7. La descripción ayuda a decidir la compra (estructura, consejo, medidas, enlace)",
]


def _texto(desc_html: str) -> str:
    t = re.sub(r"</(p|h2|li)>", "\n", desc_html or "")
    t = re.sub(r"<li>", "• ", t)
    return html.unescape(re.sub(r"\n{2,}", "\n", re.sub(r"<[^>]+>", "", t))).strip()


def _seo(path: Path) -> dict[str, dict]:
    filas = list(csv.reader(path.open(encoding="utf-8")))
    cab = next(i for i, f in enumerate(filas) if f and f[0].strip() == "#")
    out = {}
    for f in filas[cab + 1:]:
        if len(f) >= 9 and f[1].startswith("http"):
            out[f[1].rstrip("/")] = {"h1": f[5].strip(), "keywords": f[6].strip(),
                                     "descripcion": f[8].strip()}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agente", required=True)
    ap.add_argument("--seo", required=True)
    ap.add_argument("--semilla", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--clave", required=True)
    a = ap.parse_args()
    agente = {f["url"].rstrip("/"): f for f in
              json.loads(Path(a.agente).read_text())["fichas"]}
    seo = _seo(Path(a.seo))
    faltan = sorted(set(agente) - set(seo))
    if faltan:
        raise SystemExit(f"El SEO no entregó estas fichas: {faltan}")
    rnd = random.Random(a.semilla)
    clave, filas = {}, []
    cab = ["#", "Ficha", "Versión", "H1", "Keywords", "Descripción"] + CRITERIOS + \
        ["Nota (Crítico / Mal / Aceptable / Bien)", "¿Cuál preferís? (A / B / igual)",
         "Comentario"]
    for i, url in enumerate(sorted(agente), 1):
        ag = agente[url]
        va = {"h1": ag["h1"] or "", "keywords": "\n".join(ag["keywords"]),
              "descripcion": _texto(ag["descripcion"] or "")}
        versiones = [("agente", va), ("seo", seo[url])]
        rnd.shuffle(versiones)
        clave[url] = {"A": versiones[0][0], "B": versiones[1][0]}
        for letra, (_, v) in zip("AB", versiones):
            filas.append([i, url, letra, v["h1"], v["keywords"], v["descripcion"]] +
                         [""] * (len(CRITERIOS) + 3))
    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["Evaluación ciega · agente vs SEO · marcá Sí/No por criterio, "
                    "una nota por versión y cuál preferís (en la fila A)"])
        w.writerow([])
        w.writerow(cab)
        w.writerows(filas)
    Path(a.clave).write_text(json.dumps({"semilla": a.semilla, "clave": clave},
                                        ensure_ascii=False, indent=1))
    print(f"{len(agente)} fichas → {a.out}; clave en {a.clave} (no mostrar al evaluador)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
