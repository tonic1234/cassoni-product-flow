# -*- coding: utf-8 -*-
"""Entrypoint CLI del pipeline Cassoni.

Tres formas de usarlo:

  # 1) ¿está todo conectado? (no gasta LLM ni DataForSEO)
  python -m cassoni.cli --env prod --preflight

  # 2) el agente ELIGE el trabajo solo, desde GSC
  python -m cassoni.cli --env prod --seleccionar 20 --out evidencia/lote.json

  # 3) procesar un lote (dry-run por defecto; --write para editar de verdad)
  python -m cassoni.cli --env prod --urls lote.txt --batch 20
  python -m cassoni.cli --env prod --urls lote.txt --write --scheduler

  # 4) medir el efecto a 14/28 días
  python -m cassoni.cli --env prod --revisar --days 14
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from .config import Config
from .orchestrator import Pipeline
from .selector import filtrar_paginas, lote_a_json, priorizar

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")


# ---------------------------------------------------------------- constructores
# separados para poder inyectarlos en los tests sin tocar la red
def _make_gsc(cfg):
    from .gsc import GSCClient
    return GSCClient(cfg)


def _make_woo(cfg):
    from .woo import WooCommerce
    return WooCommerce(cfg)


def _make_llm(cfg):
    from .llm import LLMClient
    return LLMClient(cfg)


# ---------------------------------------------------------------- acciones
def seleccionar(gsc, *, n: int, days: int = 90, candidatas: int | None = None,
                pausa: float = 0.0) -> list[dict]:
    """Elige las N fichas con más oportunidad real. Consulta sólo las necesarias."""
    paginas = gsc.pages(days=days)
    cands = filtrar_paginas(paginas)
    tope = candidatas or max(n * 3, n)
    consultadas: dict[str, list[dict]] = {}
    for p in cands[:tope]:
        consultadas[p["url"]] = gsc.queries_for_page(p["url"], days=days)
        if pausa:
            time.sleep(pausa)
    return priorizar(cands[:tope], consultadas, top_n=n)


def preflight(cfg: Config) -> dict:
    """Chequeo de terreno SIN gastar LLM ni DataForSEO."""
    out: dict = {"env": cfg.env, "dry_run": cfg.dry_run, "faltantes": cfg.validate()}

    try:
        gsc = _make_gsc(cfg)
        sitios = gsc.list_sites()
        out["gsc"] = {"ok": cfg.gsc_site in sitios, "sitios": sitios}
    except Exception as exc:
        out["gsc"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    try:
        woo = _make_woo(cfg)
        items = woo._get("products", {"per_page": 1, "status": "publish"})
        out["woo"] = {"ok": bool(items), "muestra": len(items), "base": cfg.wc_base}
    except Exception as exc:
        out["woo"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    try:
        llm = _make_llm(cfg)
        status = llm.ping()
        out["llm"] = {"ok": status == 200, "http": status,
                      "modelo": cfg.llm_editor_model, "base": cfg.llm_base_url}
    except Exception as exc:
        out["llm"] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    out["dataforseo"] = {"ok": bool(cfg.dfs_login and cfg.dfs_password),
                         "nota": "credenciales presentes (no se gasta acá)"}
    out["ok"] = all(out[k].get("ok") for k in ("gsc", "woo", "llm")) and not out["faltantes"]
    return out


def revisar(cfg: Config, *, days: int, urls: list[str] | None = None) -> list[dict]:
    from .db import DB
    from .revisar import revisar_lote
    return revisar_lote(DB(cfg), _make_gsc(cfg), urls, days=days)


# ---------------------------------------------------------------- CLI
def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="cassoni", description="Pipeline SEO Cassoni")
    p.add_argument("--env", choices=["staging", "prod"], default="staging")
    p.add_argument("--urls", help="archivo con URLs (1 por línea)")
    p.add_argument("--dry-run", action="store_true", help="no toca WooCommerce (default)")
    p.add_argument("--write", action="store_true", help="habilita escritura en WooCommerce")
    p.add_argument("--batch", type=int, default=0, help="procesar N productos y salir")
    p.add_argument("--scheduler", action="store_true", help="modo cron supervisor")
    p.add_argument("--db", help="db_url (default del config)")
    # nuevas
    p.add_argument("--seleccionar", type=int, metavar="N",
                   help="elegir las N fichas con más oportunidad desde GSC")
    p.add_argument("--days", type=int, default=90, help="ventana de GSC en días")
    p.add_argument("--out", default="", help="archivo JSON del lote (default: evidencia/)")
    p.add_argument("--pausa", type=float, default=0.0,
                   help="segundos entre consultas a GSC (cortesía)")
    p.add_argument("--candidatas", type=int, default=0,
                   help="cuántas fichas candidatas consultar (default 3xN)")
    p.add_argument("--revisar", action="store_true",
                   help="medir el efecto sobre las fichas ya editadas")
    p.add_argument("--preflight", action="store_true", help="chequear conexiones y salir")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    dry = not args.write          # si no se pasa --write => dry_run
    cfg = Config.load(env=args.env, dry_run=dry)
    if args.db:
        cfg.db_url = args.db
    missing = cfg.validate()
    if missing:
        print(f"FALTAN credenciales para env '{args.env}': {missing}", file=sys.stderr)
        print("El pipeline NO puede correr en vivo sin ellas.", file=sys.stderr)
        return 2

    if args.preflight:
        res = preflight(cfg)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0 if res["ok"] else 1

    if args.seleccionar:
        gsc = _make_gsc(cfg)
        lote = seleccionar(gsc, n=args.seleccionar, days=args.days,
                           candidatas=args.candidatas or None, pausa=args.pausa)
        meta = {"dias": args.days, "tope": args.seleccionar,
                "generado": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "env": cfg.env, "filtro": {"min_impressions": 50,
                                           "max_pos_sin_clics": 30}}
        out = Path(args.out) if args.out else Path(
            f"evidencia/lote-{time.strftime('%Y-%m-%d')}-{args.seleccionar}.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(lote_a_json(lote, meta=meta), encoding="utf-8")
        print(f"\nLote de {len(lote)} fichas → {out}")
        for i, c in enumerate(lote, 1):
            print(f"  {i:>2}. [{c['opportunity_score']:>3}] {c['keyword'][:48]:<48} "
                  f"pos {c['kw_position']:>5.1f} impr {c['kw_impressions']:>6}  {c['url']}")
        return 0

    if args.revisar:
        urls = None
        if args.urls:
            urls = [l.strip() for l in open(args.urls) if l.strip()
                    and not l.startswith("#")]
        res = revisar(cfg, days=args.days, urls=urls)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0

    if not args.urls:
        print("Falta --urls (o usá --seleccionar N / --revisar / --preflight).",
              file=sys.stderr)
        return 2

    print(f"CASSonI pipeline | env={cfg.env} | dry_run={cfg.dry_run}")
    print(f"  wc_base={cfg.wc_base}")
    pipe = Pipeline(cfg)

    if args.scheduler:
        from .scheduler import Scheduler
        sched = Scheduler(cfg, pipe, urls_file=args.urls)
        res = sched.run_until(max_products=args.batch or None,
                              max_minutes=60 * 12)
        _print_results(res)
        print("\nResumen DB:", sched.pipeline.db.summary())
        return 0

    urls = [l.strip() for l in open(args.urls) if l.strip() and not l.startswith("#")]
    limit = args.batch or len(urls)
    results = [pipe.process(u) for u in urls[:limit]]
    _print_results(results)
    print("\nResumen DB:", pipe.db.summary())
    return 0


def _print_results(results):
    from collections import Counter
    counts = Counter(r.status for r in results)
    print(f"\nResultados: {dict(counts)}")
    for r in results:
        flag = ("⚠" if r.status == "failed"
                else ("✗" if r.status == "rejected"
                      else ("-" if r.status == "skipped" else "✓")))
        print(f"  {flag} {r.status:9s} {r.url}")
        if r.edited_h1:
            print(f"       H1 → {r.edited_h1[:90]}")
        if r.reason:
            print(f"       ({r.reason})")


if __name__ == "__main__":
    raise SystemExit(main())
