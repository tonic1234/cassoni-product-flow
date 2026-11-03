# -*- coding: utf-8 -*-
"""Mete el JSON de revisión (tools/exportar_revision.py) en la landing.

La página dibuja la sección "Prueba real" desde <script id="revision-data">.
El JSON se escapa para que ningún texto de una ficha pueda cerrar el <script>.

Uso:
  python tools/landing_con_revision.py --json revision.json \\
      --landing docs/landing/index.html
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

_BLOQUE = re.compile(r'(<script type="application/json" id="revision-data">)(.*?)(</script>)', re.S)


def inyectar(html: str, datos: dict) -> str:
    seguro = (json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
              .replace("</", "<\\/").replace("<!--", "<\\!--"))
    if not _BLOQUE.search(html):
        raise ValueError("la landing no tiene el bloque revision-data")
    return _BLOQUE.sub(lambda m: m.group(1) + seguro + m.group(3), html, count=1)


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--json", required=True)
    p.add_argument("--landing", default="docs/landing/index.html")
    a = p.parse_args(argv)
    ruta = Path(a.landing)
    datos = json.loads(Path(a.json).read_text(encoding="utf-8"))
    ruta.write_text(inyectar(ruta.read_text(encoding="utf-8"), datos), encoding="utf-8")
    print(f"{len(datos.get('fichas', []))} fichas en {ruta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
