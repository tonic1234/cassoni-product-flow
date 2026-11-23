# -*- coding: utf-8 -*-
"""Simula EN SECO fichas nuevas sin acceso a WooCommerce ni a Search Console (23-nov-2026).

- La ficha se lee de la página publicada con DataForSEO On-Page (content_parsing,
  US$ 0,00015 por página): nombre y marca («X by Marca»), descripción, medidas, opciones
  y la categoría (del menú de la tienda, por coincidencia con el tipo).
- Search Console se reemplaza por lo que DataForSEO Labs estima que la página rankea
  (posición <= 30 y volumen). No son impresiones reales: la landing lo dice.
- Volúmenes de las genéricas: un pedido de Google Ads para todas las fichas.
- H1, keywords, redacción y validación: las mismas funciones del agente
  (tools/control_alex_sin_tienda.preparar + Validator.redactar_hasta_minimo).
Nada se escribe en la tienda: este script no tiene cliente de WooCommerce.

    CASSONI_DFS_LOGIN=… CASSONI_DFS_PASSWORD=… CASSONI_LLM_…=… \\
      ./venv/bin/python tools/simular_fichas_nuevas.py \\
        --entrada evidencia/2026-11-23-simulacion-10-nuevas-entrada.json \\
        --out evidencia/2026-11-23-simulacion-10-nuevas.json
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cassoni.config import Config                       # noqa: E402
from cassoni.criterio_seo import Referencia, genericas  # noqa: E402
from cassoni.dataforseo import DataForSEOFetcher        # noqa: E402
from cassoni.h1 import tipo_ee_uu                       # noqa: E402
from cassoni.investigacion import materiales_del_texto  # noqa: E402
from cassoni.llm import LLMClient, LLMError             # noqa: E402
from cassoni.redactor import Redactor                   # noqa: E402
from cassoni.reglas_seo import MIN_KEYWORDS             # noqa: E402
from cassoni.validator import Validator                 # noqa: E402

from control_alex_sin_tienda import preparar            # noqa: E402

PARSE_URL = "https://api.dataforseo.com/v3/on_page/content_parsing/live"
_DIMS = re.compile(r'\d+\s*["”]\s*(?:\d+/\d+)?\s*["”]?\s*[WDHØ]', re.I)   # con pulgadas


def leer_pagina(fetcher: DataForSEOFetcher, url: str) -> dict:
    res = fetcher._tarea([{"url": url, "enable_javascript": False}], PARSE_URL, 0.00015, "página")
    items = (res or {}).get("items") or []
    return (items[0] or {}).get("page_content") or {} if items else {}


def ficha_desde_pagina(url: str, pc: dict) -> dict:
    """{nombre, marca, descripcion (HTML), atributos, categorias, url_categoria}."""
    nombre = marca = ""
    medidas: list[str] = []
    opciones: list[str] = []
    for t in pc.get("secondary_topic") or []:
        titulo = (t.get("h_title") or "").strip()
        sec = t.get("secondary_content") or []
        if " by " in titulo and any("/brand/" in (c.get("url") or "") for c in sec):
            nombre, _, marca = titulo.rpartition(" by ")
            for c in sec:
                tx = " ".join((c.get("text") or "").split())
                if not tx or tx == titulo or tx.lower().startswith("size ") or len(tx.split()) > 6:
                    continue
                if _DIMS.search(tx):
                    medidas.append(tx)
                elif tx not in opciones:
                    opciones.append(tx)
            break
    parrafos = []
    for t in pc.get("main_topic") or []:
        if (t.get("h_title") or "").strip().lower() == "description":
            parrafos = [" ".join((c.get("text") or "").split()) for c in t.get("primary_content") or []
                        if (c.get("text") or "").strip()]
            break
    descripcion = "".join(f"<p>{html.escape(p)}</p>\n" for p in parrafos)
    atributos = []
    if medidas:
        atributos.append("Size: " + ", ".join(dict.fromkeys(medidas)))
    if opciones:
        atributos.append("Options: " + ", ".join(opciones[:12]))
    cats = [(c.get("text") or "", c.get("url") or "") for c in
            ((pc.get("header") or {}).get("secondary_content") or [])
            if "/product-category/" in (c.get("url") or "")]
    return {"url": url, "nombre": nombre.strip(), "marca": marca.strip(), "descripcion": descripcion,
            "atributos": atributos, "menu": cats}


def categoria_para(nombre: str, tipo: str, menu: list[tuple[str, str]]) -> tuple[list[str], str]:
    """La categoría del menú que mejor coincide con el tipo y el nombre."""
    w = set(re.findall(r"[a-z]+", f"{nombre} {tipo}".lower()))
    w |= {x[:-1] for x in w if x.endswith("s")}
    mejor, puntos = ("", ""), 0
    for texto, url in menu:
        tw = set(re.findall(r"[a-z]+", texto.lower()))
        tw |= {x[:-1] for x in tw if x.endswith("s")}
        p = len(w & tw)
        if p > puntos:
            mejor, puntos = (texto, url), p
    ruta = [s for s in mejor[1].split("/product-category/")[-1].split("/") if s] if mejor[1] else []
    return ruta, mejor[1]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entrada", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    cfg = Config.load("staging", dry_run=True)
    dfs = DataForSEOFetcher(cfg)
    llm = LLMClient(cfg)
    referencia = Referencia.cargar(cfg.referencia_seo)
    redactor, validator = Redactor(cfg, llm, referencia=referencia), Validator(cfg, llm)
    entrada = json.loads(Path(a.entrada).read_text(encoding="utf-8"))

    # 1) fichas desde la página publicada
    refs, descs = [], {}
    for url in entrada["elegidas"]:
        f = ficha_desde_pagina(url, leer_pagina(dfs, url))
        if not f["nombre"] or not f["descripcion"]:
            print(f"salteada (no se pudo leer la ficha): {url}", flush=True)
            continue
        ruta0, _ = categoria_para(f["nombre"], "", f["menu"])
        tipo = tipo_ee_uu(f["nombre"], ruta0, tuple(f["atributos"]))
        ruta, url_cat = categoria_para(f["nombre"], tipo, f["menu"])
        texto = " ".join([f["nombre"], *f["atributos"], re.sub("<[^>]+>", " ", f["descripcion"])])
        gsc = [{"keyword": b["keyword"], "origen": "gsc", "posicion": b["posicion"],
                "volumen": b["volumen"],
                # estimación: sin Search Console, las búsquedas en la primera página cuentan
                # como vistas; más abajo, como pocas impresiones
                "impresiones": (b["volumen"] or 0) if (b["posicion"] or 99) <= 10 else 3}
               for b in entrada["busquedas"][url]]
        refs.append({"url": url, "nombre": f["nombre"], "marca": f["marca"], "tipo": tipo,
                     "materiales": materiales_del_texto(texto), "candidatas": gsc,
                     "url_categoria_seo": url_cat, "atributos": f["atributos"],
                     "_genericas": genericas(f["nombre"], f["marca"], tipo, f["atributos"],
                                             f["descripcion"])})
        descs[url] = f["descripcion"]
        print(f"leída   {f['nombre']} by {f['marca']} · {tipo} · {url_cat.split('product-category/')[-1]}",
              flush=True)

    # 2) volumen de las genéricas: un solo pedido para todas
    todas = sorted({g for r in refs for g in r["_genericas"]})
    vol = dict(zip(todas, dfs.search_volume(todas))) if todas else {}
    for r in refs:
        r["candidatas"] += [{"keyword": g, "origen": "generica",
                             "volumen": (vol.get(g) or {}).get("volume") or 0}
                            for g in r.pop("_genericas")]

    # 3) H1, keywords, redacción y validación: las funciones del agente
    fichas = []
    for r in refs:
        t0 = time.time()
        ficha, objetivos, dec = preparar(r, descs[r["url"]], cfg.h1_umbral_nombre)
        if len(objetivos) < MIN_KEYWORDS:
            sug = []
            from cassoni.h1 import modelo_de
            from cassoni.reglas_seo import _norm, cabeza_de
            modelo = _norm(modelo_de(r["nombre"], r["marca"]))
            marca = (_norm(r["marca"]).split() or [""])[0]
            for semilla in dict.fromkeys([f"{modelo} {cabeza_de(r['tipo']) or _norm(r['tipo'])}",
                                          f"{marca} {modelo}"]):
                sug += dfs.sugerencias(semilla.strip())
            ficha, objetivos, dec = preparar(r, descs[r["url"]], cfg.h1_umbral_nombre,
                                             rankeadas=sug, origen="sugerencia")
        ficha["atributos"] = r["atributos"]
        from cassoni.redactor import medidas_ee_uu
        ficha["medidas"] = medidas_ee_uu(r["atributos"])
        try:
            val = validator.redactar_hasta_minimo(ficha=ficha, keywords=objetivos,
                                                  reservas=dec["reservas"], redactor=redactor,
                                                  minimo=MIN_KEYWORDS)
        except LLMError as exc:
            fichas.append({"url": r["url"], "status": "failed", "reason": str(exc),
                           "h1_original": r["nombre"], "keywords": [], "keywords_detalle": []})
            continue
        ed = val["edited"]
        obj = val["objetivos"]
        fichas.append({
            "url": r["url"], "status": "processed" if val["aprobado"] else "rejected",
            "reason": "simulación en seco: ficha leída de la página publicada",
            "h1_original": r["nombre"], "h1": ed.get("h1") or "", "h1_regla": dec["regla"],
            "descripcion": ed.get("description") or "", "descripcion_original": descs[r["url"]],
            "keywords": [o["keyword"] for o in obj], "keywords_detalle": obj,
            "omitidas": ed.get("omitidas") or [], "reservas_usadas": val.get("reservas_usadas") or [],
            "validacion": val["validacion"], "intentos": val["intentos"],
            "segundos": round(time.time() - t0, 1)})
        print(f"{fichas[-1]['status']:9} {fichas[-1]['h1']}  kw={fichas[-1]['keywords']}", flush=True)

    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    costos = llm.consumo()
    costos["dfs_usd"] = round(dfs.costo_usd, 4)
    out = {"meta": {"modo": "simulación sin tienda", "llm": cfg.llm_editor_model, "commit": commit,
                    "dry_run": True, "simulada": True, "semilla": entrada["semilla"],
                    "universo": entrada["universo"],
                    "nota": "Ficha leída de la página publicada con DataForSEO; Search Console "
                            "reemplazado por las búsquedas que DataForSEO estima para la página.",
                    "costos": costos}, "fichas": fichas}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("guardado en", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
