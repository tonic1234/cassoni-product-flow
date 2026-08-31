# -*- coding: utf-8 -*-
"""Entrypoint CLI del pipeline Cassoni.

Uso:
  python -m cassoni.cli --env staging --dry-run --urls urls.txt
  python -m cassoni.cli --env staging --urls urls.txt --batch 5
  python -m cassoni.cli --env staging --urls urls.txt --scheduler
  python -m cassoni.cli --env prod   --urls urls.txt --dry-run   # pre-flight de produccion
"""
from __future__ import annotations

import argparse
import logging
import sys

from .config import Config
from .orchestrator import Pipeline

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main(argv=None):
    p = argparse.ArgumentParser(prog="cassoni", description="Pipeline SEO Cassoni")
    p.add_argument("--env", choices=["staging", "prod"], default="staging")
    p.add_argument("--urls", required=True, help="archivo con URLs (1 por línea)")
    p.add_argument("--dry-run", action="store_true", help="no toca WooCommerce (default)")
    p.add_argument("--write", action="store_true", help="habilita escritura en WooCommerce")
    p.add_argument("--batch", type=int, default=0, help="procesar N productos y salir")
    p.add_argument("--scheduler", action="store_true", help="modo cron supervisor")
    p.add_argument("--db", help="db_url (default del config)")
    args = p.parse_args(argv)

    dry = not args.write          # si no se pasa --write => dry_run
    cfg = Config.load(env=args.env, dry_run=dry)
    if args.db:
        cfg.db_url = args.db
    missing = cfg.validate()
    if missing:
        print(f"FALTAN credenciales para env '{args.env}': {missing}", file=sys.stderr)
        print("El pipeline NO puede correr en vivo sin ellas.", file=sys.stderr)
        sys.exit(2)

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
        flag = "⚠" if r.status == "failed" else ("-" if r.status == "skipped" else "✓")
        print(f"  {flag} {r.status:9s} {r.url}")
        if r.edited_h1:
            print(f"       H1 → {r.edited_h1[:90]}")
        if r.reason:
            print(f"       ({r.reason})")


if __name__ == "__main__":
    raise SystemExit(main())