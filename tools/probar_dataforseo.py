# -*- coding: utf-8 -*-
"""Prueba mínima de DataForSEO antes de una corrida: una consulta de cada tipo
con UNA ficha, el costo real de cada una y una muestra de lo que devuelve.

Sirve para confirmar, con centavos, que la cuenta opera y que el formato de las
respuestas es el que el código espera (keyword_ideas y ranked_keywords se
escribieron sin poder llamarlos: la cuenta estaba sin saldo).

Uso:
  python tools/probar_dataforseo.py --env prod --url https://cassoni.com/product/<slug>/
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cassoni.competidores import elegir_competidores   # noqa: E402
from cassoni.config import Config                      # noqa: E402
from cassoni.dataforseo import DataForSEOFetcher       # noqa: E402
from cassoni.extract import extract_slug               # noqa: E402
from cassoni.h1 import h1_plantilla                    # noqa: E402
from cassoni.investigacion import semillas             # noqa: E402
from cassoni.orchestrator import _brand_y_atributos    # noqa: E402
from cassoni.woo import WooCommerce                    # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--env", default="prod")
    p.add_argument("--url", required=True)
    a = p.parse_args(argv)
    cfg = Config.load(env=a.env, dry_run=True)
    f = DataForSEOFetcher(cfg)

    cuenta = f.saldo()
    print(f"Cuenta: {cuenta}")
    if not cuenta or (cuenta.get("saldo_usd") or 0) <= 0:
        print("Sin saldo o sin acceso: no se hace ningún pedido.")
        return 1

    producto = WooCommerce(cfg).get_product_by_slug(extract_slug(a.url)[0])
    marca, atributos = _brand_y_atributos(producto)
    categorias = [c["name"] for c in producto.get("categories") or []]
    h1, _ = h1_plantilla(producto.get("name", ""), marca)
    consulta = h1.replace(" by ", " ")

    def costo(antes):
        return f"US$ {f.costo_usd - antes:.4f}"

    antes = f.costo_usd
    serp = f.serp_organico(consulta)
    print(f"\n1) Búsqueda orgánica «{consulta}»: {len(serp)} resultados · {costo(antes)}")
    for r in serp[:5]:
        print(f"   #{r['rank']} {r['domain']}")
    comp = elegir_competidores(serp, cfg.prod_hosts, n=1)

    if comp:
        antes = f.costo_usd
        rk = f.ranked_keywords(comp[0]["url"], patron=comp[0].get("patron", ""))
        print(f"\n2) Keywords que rankea {comp[0]['url']}: {len(rk)} · {costo(antes)}")
        for r in rk[:8]:
            print(f"   {r['keyword']} · vol {r['volume']} · dif {r['difficulty']} · "
                  f"{r['intent']} · pos {r['posicion_competidor']}")
    else:
        print("\n2) No hay competidores por encima nuestro: no se pide ranked_keywords.")

    sem = semillas(producto.get("name", ""), marca, categorias, atributos)
    antes = f.costo_usd
    ideas = f.ideas_de_keywords(sem)
    print(f"\n3) Ideas para {sem}: {len(ideas)} · {costo(antes)}")
    for r in ideas[:8]:
        print(f"   {r['keyword']} · vol {r['volume']} · dif {r['difficulty']} · {r['intent']}")

    print(f"\nTotal gastado: US$ {f.costo_usd:.4f}"
          + (f" · problema: {f.sin_saldo}" if f.sin_saldo else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
