# -*- coding: utf-8 -*-
"""Corre EN SECO las 10 fichas de referencia de Alex con el LLM real, sin WooCommerce,
Search Console ni DataForSEO: usa los datos guardados en el repo.

- candidatas (Search Console + volúmenes) y materiales: evidencia/referencia-seo.json
- descripción original: el lote de control del 17-nov
- H1 y keywords: las mismas funciones que el orquestador (_seleccion_reglas)
- redacción y validación: Redactor y Validator reales, viendo las fichas del SEO
  menos la propia (leave-one-out)

Faltan los atributos de WooCommerce (medidas, materiales cargados como atributo) y la
descripción corta: es una aproximación. La medición completa es tools/correr_lote.py.
Nada se escribe en la tienda: este script no tiene cliente de WooCommerce.

    CASSONI_LLM_BASE_URL=https://opencode.ai/inference/go/openai/v1 \\
    CASSONI_LLM_API_KEY=proxy-injected CASSONI_LLM_EDITOR_MODEL=deepseek-v4.1-flash \\
    CASSONI_LLM_VALIDATOR_MODEL=deepseek-v4.1-flash \\
      ./venv/bin/python tools/control_alex_sin_tienda.py --out evidencia/X.json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cassoni.config import Config                      # noqa: E402
from cassoni.criterio_seo import Referencia            # noqa: E402
from cassoni.h1 import h1_respaldo, modelo_de          # noqa: E402
from cassoni.llm import LLMClient, LLMError            # noqa: E402
from cassoni.redactor import Redactor, strip_html      # noqa: E402
from cassoni.reglas_seo import (elegir_keywords, genericas_opcionales,  # noqa: E402
                                genericas_usadas, h1_por_datos, keywords_de_opciones,
                                marca_ajena_en, nombre_de_busqueda, opciones_de_material,
                                opciones_para_h1, rasgo_combinado, rasgos_con_volumen,
                                sufijo_del_nombre, genericas_para_h1)
from cassoni.validator import Validator                # noqa: E402

CONTROL = "evidencia/2026-11-17-control-reglas3.json"


def preparar(ref: dict, desc_orig: str, umbral: int) -> tuple[dict, list[dict], dict]:
    """(ficha para el redactor, keywords objetivo, decisión del H1)."""
    vol = {c["keyword"].lower(): {"volume": c.get("volumen") or 0} for c in ref["candidatas"]}
    tipo, nombre, marca = ref["tipo"], ref["nombre"], ref["marca"]
    nucleo = tipo[len("outdoor "):] if tipo.startswith("outdoor ") else tipo
    plano = strip_html(desc_orig)
    mats = ref["materiales"]
    ops = opciones_para_h1(plano, mats)
    ajena = marca_ajena_en(nombre, marca)
    rasgos = rasgos_con_volumen(mats, nucleo, vol)
    r = h1_por_datos(nombre, marca, tipo, (vol.get(nombre_de_busqueda(nombre)) or {}).get("volume"),
                     rasgos, umbral=umbral, opciones=ops, marca_ajena=ajena,
                     combinado=rasgo_combinado(plano, mats, nucleo, vol))
    kw_ops = keywords_de_opciones(ops, nucleo, vol) if len(ops) >= 2 else []
    sel = elegir_keywords(ref["candidatas"], nombre=nombre, marca=marca, tipo=tipo, h1=r["h1"],
                          rasgo=r["rasgo"], texto_ficha=" ".join([nombre, marca, plano]),
                          opciones=kw_ops, marca_ajena=ajena)
    ficha = {"url": ref["url"], "nombre": nombre, "marca": marca, "modelo": modelo_de(nombre, marca),
             "tipo": tipo, "categorias": [], "url_categoria": ref.get("url_categoria_seo") or "",
             "atributos": [], "medidas": [], "descripcion": desc_orig, "corta": "",
             "mismo_nombre": [], "h1_respaldo": h1_respaldo(nombre, marca, tipo),
             "h1_fijo": r["h1"] if r["fijo"] else "", "h1_regla": r["regla"],
             "h1_rasgos": sorted(((m, v) for m, v in rasgos if v), key=lambda x: -x[1]),
             "genericas_opcionales": [] if kw_ops else genericas_opcionales(mats, nucleo, vol),
             "opciones": opciones_de_material(plano, mats),
             "sufijo": sufijo_del_nombre(nombre, marca, tipo), "keywords_obligatorias": True}
    return ficha, sel["elegidas"], r


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--ref", default="evidencia/referencia-seo.json")
    a = ap.parse_args(argv)
    cfg = Config.load("staging", dry_run=True)
    llm = LLMClient(cfg)
    referencia = Referencia.cargar(a.ref)
    redactor, validator = Redactor(cfg, llm, referencia=referencia), Validator(cfg, llm)
    refs = json.loads(Path(a.ref).read_text(encoding="utf-8"))
    originales = {f["url"]: f.get("descripcion_original") or ""
                  for f in json.loads(Path(CONTROL).read_text(encoding="utf-8"))["fichas"]}
    fichas = []
    for ref in refs:
        t0 = time.time()
        ficha, objetivos, r = preparar(ref, originales.get(ref["url"], ""), cfg.h1_umbral_nombre)
        try:
            val = validator.redactar_y_validar(ficha=ficha, keywords=objetivos, redactor=redactor)
        except LLMError as exc:
            fichas.append({"url": ref["url"], "status": "failed", "reason": str(exc),
                           "h1_original": ref["nombre"], "keywords": []})
            print(f"failed    {ref['nombre']}: {exc}", flush=True)
            continue
        ed = val["edited"]
        h1 = ed.get("h1") or ""
        omitidas = {(o.get("keyword") or "").lower() for o in ed.get("omitidas") or []}
        objetivos = [o for o in objetivos if o["keyword"].lower() not in omitidas]
        if val["aprobado"] and ficha["genericas_opcionales"]:
            ya = {o["keyword"].lower() for o in objetivos}
            validas = {k for k, _, _ in genericas_para_h1(h1, ficha["genericas_opcionales"])}
            for kw, v, ok in genericas_usadas(strip_html(ed.get("description") or ""), h1,
                                              ficha["genericas_opcionales"]):
                if ok and kw in validas and kw not in ya:
                    ya.add(kw)
                    objetivos.append({"keyword": kw, "origen": "generica", "volumen": v})
        fichas.append({
            "url": ref["url"], "status": "processed" if val["aprobado"] else "rejected",
            "reason": "dry_run sin tienda", "h1_original": ref["nombre"], "h1": h1,
            "h1_regla": r["regla"], "descripcion": ed.get("description") or "",
            "descripcion_original": ficha["descripcion"],
            "keywords": [o["keyword"] for o in objetivos], "keywords_detalle": objetivos,
            "omitidas": ed.get("omitidas") or [], "validacion": val["validacion"],
            "intentos": val["intentos"], "segundos": round(time.time() - t0, 1)})
        print(f"{fichas[-1]['status']:9} {h1}  kw={fichas[-1]['keywords']}", flush=True)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    out = {"meta": {"modo": "reescritura sin tienda", "llm": cfg.llm_editor_model,
                    "validador": cfg.llm_validator_model, "commit": commit, "dry_run": True,
                    "faltan": "atributos y descripción corta de WooCommerce",
                    "costos": llm.consumo()}, "fichas": fichas}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("guardado en", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
