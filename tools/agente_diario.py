# -*- coding: utf-8 -*-
"""El agente autónomo: una corrida diaria sin intervención.

1. Toma las pendientes de la lista del SEO (`lista.txt`). Si la lista se quedó sin
   pendientes, propone fichas desde Search Console (las de más oportunidad que nunca
   se procesaron) y las agrega a `lista-propuestas.txt` (la lista del SEO no se toca).
2. Procesa hasta el cupo diario (10) en horario hábil, con pausas al azar, con las
   reglas del SEO (H1 por volumen, keywords de Search Console + marca y tipo) y
   DeepSeek para redactar.
3. Deja el reporte del día: `evidencia/diario/AAAA-MM-DD.json` y la página de
   revisión `evidencia/diario/AAAA-MM-DD.html`.
4. Los lunes mide el efecto de lo escrito (14 y 28 días).

Por defecto corre EN SECO. Escribe en la tienda solo con `--write`, que se habilita
cuando el SEO apruebe el primer lote.

    python tools/agente_diario.py                 # en seco
    python tools/agente_diario.py --write         # escribe lo aprobado
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

from cassoni.config import Config            # noqa: E402
from cassoni.orchestrator import Pipeline    # noqa: E402
from cassoni.scheduler import Scheduler      # noqa: E402


def _fila(pipe: Pipeline, r) -> dict:
    fila = pipe.db.get_state(r.url)
    return {"url": r.url, "status": r.status, "reason": r.reason,
            "h1_original": getattr(fila, "original_h1", None),
            "h1": r.edited_h1, "descripcion": r.edited_description,
            "descripcion_original": getattr(fila, "original_description", None),
            "keywords": [k["keyword"] for k in r.selected], "keywords_detalle": r.selected,
            "seleccion": getattr(fila, "selection_reason", None),
            "validacion": json.loads(fila.validation_result) if getattr(
                fila, "validation_result", None) else None,
            "intentos": getattr(fila, "validation_attempts", None),
            "aplicado": r.aplicado}


def _proponer(cfg: Config, sched: Scheduler, n: int, destino: Path, log) -> list[str]:
    """Fichas de más oportunidad en Search Console que nunca se procesaron."""
    from cassoni.cli import _make_gsc, seleccionar
    vistas = set(sched._state.get("done", [])) | set(sched._state.get("abandonadas", []))
    if destino.exists():
        vistas |= {l.strip() for l in destino.read_text(encoding="utf-8").splitlines()}
    lote = seleccionar(_make_gsc(cfg), n=n * 3)
    nuevas = [c["url"] for c in lote if c["url"] not in vistas][:n]
    if nuevas:
        with destino.open("a", encoding="utf-8") as f:
            f.write(f"# propuestas por el agente {dt.date.today().isoformat()}\n")
            f.writelines(u + "\n" for u in nuevas)
        log.info("lista del SEO sin pendientes: propongo %d fichas desde Search Console",
                 len(nuevas))
    return nuevas


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="escribe en WooCommerce lo aprobado")
    ap.add_argument("--lista", default="lista.txt")
    ap.add_argument("--propuestas", default="lista-propuestas.txt")
    ap.add_argument("--sin-horario", action="store_true", help="ignora la ventana 9-18")
    ap.add_argument("--presupuesto-dfs", default="1.50", help="tope DataForSEO por corrida (USD)")
    ap.add_argument("--estado", default="", help="archivo de estado (default según el modo)")
    ap.add_argument("--carpeta", default="evidencia/diario", help="dónde dejar los reportes")
    ap.add_argument("--panel", default="publico", help="carpeta del panel ('' = no generarlo)")
    a = ap.parse_args(argv)

    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("CASSONI_DFS_PRESUPUESTO_USD", a.presupuesto_dfs)
    hoy = dt.date.today().isoformat()
    carpeta = RAIZ / a.carpeta
    carpeta.mkdir(parents=True, exist_ok=True)
    (RAIZ / "logs").mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(RAIZ / "logs" / f"agente-{hoy}.log",
                                                      encoding="utf-8"),
                                  logging.StreamHandler()])
    log = logging.getLogger("cassoni.agente")

    cfg = Config.load("prod", dry_run=not a.write)
    faltan = cfg.validate()
    if faltan:
        log.error("configuración incompleta: %s", faltan)
        return 2
    pipe = Pipeline(cfg)
    lista, propuestas = RAIZ / a.lista, RAIZ / a.propuestas
    # en seco y escribiendo llevan estados distintos: una ficha probada en seco no
    # puede quedar "hecha" para la corrida que escribe
    estado = a.estado or str(RAIZ / ("cassoni_sched.json" if a.write else "cassoni_sched_seco.json"))
    sched = Scheduler(cfg, pipe, urls_file=str(lista), state_file=estado)
    urls = sched._read_urls()
    if propuestas.exists():
        urls += [l.strip() for l in propuestas.read_text(encoding="utf-8").splitlines()
                 if l.strip() and not l.startswith("#")]
    cupo = max(0, cfg.daily_target - sched.hechas_hoy())
    if cupo and not sched.pendientes(urls):
        try:
            urls += _proponer(cfg, sched, cupo, propuestas, log)
        except Exception as exc:
            log.warning("no pude proponer fichas desde Search Console (%s)", exc)

    resultados = sched.run_until(urls=urls, respetar_horario=not a.sin_horario)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                            cwd=RAIZ).stdout.strip()
    salida = carpeta / f"{hoy}.json"
    previas = json.loads(salida.read_text(encoding="utf-8"))["fichas"] if salida.exists() else []
    datos = {"meta": {"fecha": hoy, "modo": cfg.modo_keywords, "llm": cfg.llm_editor_model,
                      "commit": commit, "dry_run": cfg.dry_run, "costos": pipe._costos()},
             "fichas": previas + [_fila(pipe, r) for r in resultados]}
    salida.write_text(json.dumps(datos, ensure_ascii=False, indent=1, default=str),
                      encoding="utf-8")
    if datos["fichas"]:
        subprocess.run([sys.executable, str(RAIZ / "tools" / "pagina_revision_seo.py"),
                        "--lote", f"{hoy}={salida}", "--fecha", hoy,
                        "--out", str(carpeta / f"{hoy}.html")], cwd=RAIZ, check=False)
    if a.panel:
        # el panel de observabilidad se regenera después de cada corrida
        subprocess.run([sys.executable, str(RAIZ / "tools" / "panel.py"), "--out", a.panel,
                        "--salud"], cwd=RAIZ, check=False)
    ok = sum(r.status == "processed" for r in resultados)
    log.info("corrida terminada: %d procesadas, %d aprobadas · reporte en %s",
             len(resultados), ok, salida)

    if dt.date.today().weekday() == 0 and not sched._state.get("medido_" + hoy):
        from cassoni.cli import revisar
        for dias in (14, 28):
            try:
                med = revisar(cfg, days=dias)
                (carpeta / f"{hoy}-medicion-{dias}d.json").write_text(
                    json.dumps(med, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
            except Exception as exc:
                log.warning("medición a %d días no disponible (%s)", dias, exc)
        sched._state["medido_" + hoy] = True
        sched._save_state()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
