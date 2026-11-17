# -*- coding: utf-8 -*-
"""Panel de observabilidad del agente SEO (estilo Dendra). Página estática que el
worker regenera después de cada corrida; el VPS solo sirve la carpeta.

Lee: la base del agente (fichas, costos, mediciones), el estado del worker (cupo,
hechas, abandonadas), la cola (lista del SEO + propuestas), los reportes diarios y
los logs. Con --salud, además prueba las conexiones (GSC, WooCommerce, LLM,
DataForSEO y su saldo) sin gastar LLM.

    python tools/panel.py --out publico            # publico/index.html + publico/diario/
    python tools/panel.py --out publico --salud
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from sqlalchemy import create_engine, text   # noqa: E402

from cassoni.config import Config             # noqa: E402

PLANTILLA = Path(__file__).with_name("panel_plantilla.html")


def _f(x) -> float:
    try:
        return float(x or 0)
    except (TypeError, ValueError):
        return 0.0


def _json(x, defecto):
    try:
        return json.loads(x) if x else defecto
    except (TypeError, ValueError):
        return defecto


def _fecha(x) -> str:
    return str(x or "")[:19].replace("T", " ")


def datos_fichas(db_url: str) -> tuple[list[dict], list[dict]]:
    eng = create_engine(db_url)
    with eng.connect() as c:
        filas = c.execute(text(
            "select url, status, reason, original_h1, edited_h1, selected_keywords, "
            "llm_cost, dfs_cost, dry_run, applied, validation_attempts, updated_at, edited_at "
            "from cassoni_processed_products order by updated_at desc")).mappings().all()
        try:
            revs = c.execute(text(
                "select url, keyword, days, position, impressions, clicks, delta_position, "
                "delta_impressions, delta_clicks, verdict, created_at from cassoni_reviews "
                "order by created_at desc")).mappings().all()
        except Exception:
            revs = []
    fichas = []
    for r in filas:
        kws = [k.get("keyword") for k in _json(r["selected_keywords"], []) if isinstance(k, dict)]
        fichas.append({"url": r["url"], "estado": r["status"], "motivo": r["reason"] or "",
                       "h1_antes": r["original_h1"] or "", "h1": r["edited_h1"] or "",
                       "keywords": [k for k in kws if k], "llm_usd": _f(r["llm_cost"]),
                       "dfs_usd": _f(r["dfs_cost"]), "seco": bool(r["dry_run"]),
                       "escrita": bool(r["applied"]), "intentos": r["validation_attempts"] or 0,
                       "fecha": _fecha(r["updated_at"]), "escrita_el": _fecha(r["edited_at"])})
    medicion = [{k: (_fecha(v) if k == "created_at" else v) for k, v in dict(r).items()}
                for r in revs]
    return fichas, medicion


def datos_worker(raiz: Path) -> dict:
    estados = {}
    for modo, nombre in (("escritura", "cassoni_sched.json"), ("seco", "cassoni_sched_seco.json")):
        p = raiz / nombre
        if p.exists():
            estados[modo] = _json(p.read_text(encoding="utf-8"), {})
    activo = "escritura" if "escritura" in estados else ("seco" if estados else "")
    st = estados.get(activo, {})
    cola = []
    for nombre in ("lista.txt", "lista-propuestas.txt"):
        p = raiz / nombre
        if p.exists():
            cola += [(l.strip(), "SEO" if nombre == "lista.txt" else "propuesta")
                     for l in p.read_text(encoding="utf-8").splitlines()
                     if l.strip() and not l.startswith("#")]
    cerradas = set(st.get("done", [])) | set(st.get("abandonadas", []))
    vistas, pendientes = set(), []
    for u, origen in cola:
        if u not in cerradas and u not in vistas:
            vistas.add(u)
            pendientes.append({"url": u, "origen": origen})
    return {"modo": activo, "ultima": st.get("last_run", ""), "por_dia": st.get("por_dia", {}),
            "hechas": len(st.get("done", [])),
            "abandonadas": [{"url": u, "intentos": st.get("intentos", {}).get(u, 0)}
                            for u in st.get("abandonadas", [])],
            "pendientes": pendientes}


def datos_reportes(raiz: Path, destino: Path) -> list[dict]:
    carpeta = raiz / "evidencia" / "diario"
    out = []
    if not carpeta.exists():
        return out
    (destino / "diario").mkdir(parents=True, exist_ok=True)
    for j in sorted(carpeta.glob("????-??-??.json"), reverse=True)[:60]:
        d = _json(j.read_text(encoding="utf-8"), {})
        meta, fichas = d.get("meta", {}), d.get("fichas", [])
        html = j.with_suffix(".html")
        if html.exists():
            shutil.copyfile(html, destino / "diario" / html.name)
        c = meta.get("costos", {})
        out.append({"fecha": meta.get("fecha", j.stem), "fichas": len(fichas),
                    "aprobadas": sum(f.get("status") == "processed" for f in fichas),
                    "llm_usd": _f(c.get("usd")), "dfs_usd": _f(c.get("dfs_usd")),
                    "seco": bool(meta.get("dry_run", True)),
                    "pagina": f"diario/{html.name}" if html.exists() else ""})
    return out


def datos_logs(raiz: Path, n: int = 25) -> list[dict]:
    out = []
    for p in sorted((raiz / "logs").glob("agente-*.log"), reverse=True)[:7]:
        for l in p.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"(\S+ \S+) (WARNING|ERROR) (\S+): (.*)", l)
            if m and "httpx" not in m.group(3):
                out.append({"fecha": m.group(1)[:16], "nivel": m.group(2), "texto": m.group(4)[:300]})
    return sorted(out, key=lambda x: x["fecha"], reverse=True)[:n]


def salud(cfg: Config) -> dict:
    from cassoni.cli import preflight
    try:
        r = preflight(cfg)
    except Exception as exc:
        return {"error": str(exc)}
    return {"gsc": bool((r.get("gsc") or {}).get("ok")), "woo": bool((r.get("woo") or {}).get("ok")),
            "llm": bool((r.get("llm") or {}).get("ok")),
            "dataforseo": bool((r.get("dataforseo") or {}).get("ok")),
            "saldo_dfs": (r.get("dataforseo") or {}).get("saldo_usd"),
            "modelo": (r.get("llm") or {}).get("modelo")}


def resumen(fichas: list[dict], reportes: list[dict]) -> dict:
    hoy = dt.date.today()
    semana = (hoy - dt.timedelta(days=7)).isoformat()
    proc = [f for f in fichas if f["estado"] in ("processed", "rejected", "failed")]
    dfs = sum(r["dfs_usd"] for r in reportes) or sum(f["dfs_usd"] for f in fichas)
    llm = sum(f["llm_usd"] for f in fichas)
    por_dia: dict[str, Counter] = defaultdict(Counter)
    costo_dia: dict[str, float] = defaultdict(float)
    for f in fichas:
        d = f["fecha"][:10]
        if d:
            por_dia[d][f["estado"]] += 1
            costo_dia[d] += f["llm_usd"]
    for r in reportes:
        costo_dia[r["fecha"]] += r["dfs_usd"]
    dias = [(hoy - dt.timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
    return {
        "procesadas": len(proc),
        "semana": sum(1 for f in proc if f["fecha"][:10] >= semana),
        "aprobadas": sum(f["estado"] == "processed" for f in fichas),
        "rechazadas": sum(f["estado"] == "rejected" for f in fichas),
        "fallidas": sum(f["estado"] == "failed" for f in fichas),
        "escritas": sum(f["escrita"] for f in fichas),
        "keywords": sum(len(f["keywords"]) for f in fichas if f["estado"] == "processed"),
        "con_keywords": sum(bool(f["keywords"]) for f in fichas if f["estado"] == "processed"),
        "costo_llm": round(llm, 4), "costo_dfs": round(dfs, 4),
        "serie": [{"dia": d, "aprobadas": por_dia[d]["processed"], "rechazadas": por_dia[d]["rejected"],
                   "fallidas": por_dia[d]["failed"], "costo": round(costo_dia[d], 4)} for d in dias],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="publico")
    ap.add_argument("--env", default="prod")
    ap.add_argument("--salud", action="store_true", help="probar conexiones (sin gastar LLM)")
    a = ap.parse_args(argv)
    destino = (RAIZ / a.out) if not Path(a.out).is_absolute() else Path(a.out)
    destino.mkdir(parents=True, exist_ok=True)
    cfg = Config.load(a.env, dry_run=True)
    fichas, medicion = datos_fichas(cfg.db_url)
    reportes = datos_reportes(RAIZ, destino)
    datos = {"generado": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
             "worker": datos_worker(RAIZ), "fichas": fichas[:60], "medicion": medicion[:80],
             "reportes": reportes, "logs": datos_logs(RAIZ),
             "resumen": resumen(fichas, reportes),
             "config": {"cupo": cfg.daily_target, "modo_keywords": cfg.modo_keywords,
                        "modelo": cfg.llm_editor_model},
             "salud": salud(cfg) if a.salud else None}
    seguro = (json.dumps(datos, ensure_ascii=False, separators=(",", ":"), default=str)
              .replace("</", "<\\/").replace("<!--", "<\\!--"))
    html = PLANTILLA.read_text(encoding="utf-8").replace("__DATOS__", seguro)
    (destino / "index.html").write_text(html, encoding="utf-8")
    print(f"panel en {destino / 'index.html'} ({len(html) // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
