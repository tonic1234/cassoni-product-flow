# -*- coding: utf-8 -*-
"""¿Qué tan parecido a lo del SEO es lo que hace el agente en las MISMAS fichas?

Compara una corrida en seco (tools/correr_lote.py) contra la referencia del SEO
(tools/armar_referencia_seo.py), ficha por ficha:
- H1: igual, palabras en común;
- keywords: cuántas del SEO eligió el agente (cobertura) y cuántas de las del
  agente están en la lista del SEO (acierto); plural y posesivo cuentan igual;
- descripción: palabras, secciones, listas y si la primera keyword va en la apertura.

    python tools/evaluar_vs_seo.py --lote evidencia/X.json --ref evidencia/referencia-seo.json \\
        [--out evidencia/X-vs-seo.json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cassoni.checklist import h2_count, strip_html, word_count   # noqa: E402
from cassoni.criterio_seo import clave                             # noqa: E402


def _tokens(h1: str) -> set[str]:
    base = re.split(r"\s+by\s+", (h1 or "").lower())[0]
    return set(re.findall(r"[a-z0-9]+", base.replace("-", " ")))


def _seo_secciones(txt: str) -> int:
    return sum(1 for l in (txt or "").splitlines()
               if l.strip() and l.strip() == l.strip().upper() and re.search(r"[A-Z]", l))


def _seo_palabras(txt: str) -> int:
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\"/.-]*", txt or ""))


def comparar(agente: dict, seo: dict) -> dict:
    kws_a = [k for k in agente.get("keywords") or []]
    ka, ks = {clave(k): k for k in kws_a}, {clave(k): k for k in seo["keywords_seo"]}
    comunes = sorted(set(ka) & set(ks))
    ta, ts = _tokens(agente.get("h1")), _tokens(seo["h1_seo"])
    desc = agente.get("descripcion") or ""
    apertura = strip_html(desc.split("</p>")[0]).lower() if desc else ""
    return {
        "url": agente["url"], "nombre": agente.get("h1_original"),
        "h1_agente": agente.get("h1"), "h1_seo": seo["h1_seo"],
        "h1_igual": (agente.get("h1") or "").strip().lower() == seo["h1_seo"].strip().lower(),
        "h1_parecido": round(len(ta & ts) / max(len(ta | ts), 1), 2),
        "kw_agente": kws_a, "kw_seo": seo["keywords_seo"],
        "kw_en_comun": [ks[c] for c in comunes],
        "cobertura": round(len(comunes) / max(len(ks), 1), 2),
        "acierto": round(len(comunes) / len(ka), 2) if ka else None,
        "palabras_agente": word_count(desc), "palabras_seo": _seo_palabras(seo["descripcion_seo"]),
        "secciones_agente": h2_count(desc), "secciones_seo": _seo_secciones(seo["descripcion_seo"]),
        "lista_agente": "<li>" in desc, "lista_seo": "•" in seo["descripcion_seo"],
        "kw_en_apertura": bool(kws_a) and kws_a[0].lower() in apertura,
        "aprobada": agente.get("status") == "processed",
        "descripcion_agente": desc, "descripcion_seo": seo["descripcion_seo"],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lote", required=True)
    ap.add_argument("--ref", default="evidencia/referencia-seo.json")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    ref = {r["url"].rstrip("/"): r for r in json.loads(Path(a.ref).read_text(encoding="utf-8"))}
    lote = json.loads(Path(a.lote).read_text(encoding="utf-8"))
    filas = [comparar(f, ref[f["url"].rstrip("/")]) for f in lote["fichas"]
             if f["url"].rstrip("/") in ref and f.get("h1")]
    for r in filas:
        print(f"\n## {r['nombre']}  {'(rechazada)' if not r['aprobada'] else ''}")
        print(f"   H1 agente: {r['h1_agente']}")
        igual = "= IGUAL" if r["h1_igual"] else f"parecido {r['h1_parecido']:.0%}"
        print(f"   H1 SEO   : {r['h1_seo']}   {igual}")
        print(f"   kw agente: {r['kw_agente']}")
        print(f"   kw SEO   : {r['kw_seo']}   → en común {r['kw_en_comun']}")
        print(f"   palabras {r['palabras_agente']} vs {r['palabras_seo']} · secciones "
              f"{r['secciones_agente']} vs {r['secciones_seo']} · lista {r['lista_agente']} vs "
              f"{r['lista_seo']}")
    n = len(filas)
    kw_seo = sum(len(r["kw_seo"]) for r in filas)
    kw_ag = sum(len(r["kw_agente"]) for r in filas)
    com = sum(len(r["kw_en_comun"]) for r in filas)
    resumen = {
        "fichas": n,
        "h1_iguales": sum(r["h1_igual"] for r in filas),
        "h1_parecido_promedio": round(sum(r["h1_parecido"] for r in filas) / max(n, 1), 2),
        "keywords_seo": kw_seo, "keywords_agente": kw_ag, "keywords_en_comun": com,
        "cobertura": round(com / max(kw_seo, 1), 2),
        "acierto": round(com / max(kw_ag, 1), 2),
        "palabras_agente_prom": round(sum(r["palabras_agente"] for r in filas) / max(n, 1)),
        "palabras_seo_prom": round(sum(r["palabras_seo"] for r in filas) / max(n, 1)),
        "aprobadas": sum(r["aprobada"] for r in filas),
    }
    print("\nRESUMEN", json.dumps(resumen, ensure_ascii=False))
    if a.out:
        Path(a.out).write_text(json.dumps({"resumen": resumen, "meta": lote.get("meta"),
                                           "fichas": filas}, ensure_ascii=False, indent=1),
                               encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
