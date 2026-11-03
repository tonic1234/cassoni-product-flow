# -*- coding: utf-8 -*-
"""Goteo diario de la lista de SEO (pizarra: "5-10 URLs/día, horarios random,
no penalización").

- La lista (`--urls lista.txt`) la completa el equipo SEO día a día: el
  scheduler toma las pendientes, en el orden del archivo.
- Hasta `daily_target` fichas por día (10 por defecto), en horario hábil
  (9-18, lun-vie), con pausas aleatorias de 30 s a 5 min entre fichas.
- Una ficha escrita, salteada o aprobada en seco queda "hecha". Una rechazada
  o fallida se reintenta otro día, hasta MAX_INTENTOS; después queda
  "abandonada" para que SEO la mire (antes se reintentaba para siempre y cada
  intento gastaba LLM).
- El estado vive en `cassoni_sched.json`: correrlo con cron varias veces por
  día es seguro.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import random
import time
from pathlib import Path
from typing import Iterable

from .config import Config
from .orchestrator import Pipeline, Result

log = logging.getLogger("cassoni.scheduler")

MAX_INTENTOS = 2


class Scheduler:
    def __init__(self, config: Config, pipeline: Pipeline,
                 urls_file: str, state_file: str = "./cassoni_sched.json"):
        self.cfg = config
        self.pipeline = pipeline
        self.urls_file = Path(urls_file)
        self.state_file = Path(state_file)
        self._state = self._load_state()

    # ---- utilidades de estado ----
    def _load_state(self) -> dict:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except Exception:
                return {}
        return {}

    def _save_state(self):
        self.state_file.write_text(json.dumps(self._state, ensure_ascii=False, indent=2))

    def _read_urls(self) -> list[str]:
        if not self.urls_file.exists():
            return []
        return [l.strip() for l in self.urls_file.read_text().splitlines()
                if l.strip() and not l.startswith("#")]

    def hechas_hoy(self, hoy: dt.date | None = None) -> int:
        hoy = (hoy or dt.date.today()).isoformat()
        return int(self._state.get("por_dia", {}).get(hoy, 0))

    def pendientes(self, urls: Iterable[str]) -> list[str]:
        cerradas = set(self._state.get("done", [])) | set(self._state.get("abandonadas", []))
        return [u for u in dict.fromkeys(urls) if u not in cerradas]

    # ---- horario ----
    @staticmethod
    def in_work_hours(now: dt.datetime) -> bool:
        return now.weekday() < 5 and Scheduler._in_window(now)

    @staticmethod
    def _in_window(now: dt.datetime) -> bool:
        return 9 <= now.hour < 18

    def _delay(self) -> float:
        # distribución no uniforme: skew hacia pausas cortas con cola larga ocasional
        return random.triangular(self.cfg.pause_min_s, self.cfg.pause_max_s,
                                 (self.cfg.pause_min_s + self.cfg.pause_max_s) / 2)

    def _anotar(self, url: str, res: Result) -> None:
        hoy = dt.date.today().isoformat()
        por_dia = self._state.setdefault("por_dia", {})
        if res.status in ("processed", "rejected", "failed"):
            por_dia[hoy] = por_dia.get(hoy, 0) + 1
        if res.status in ("processed", "skipped"):
            if url not in self._state.setdefault("done", []):
                self._state["done"].append(url)
            return
        intentos = self._state.setdefault("intentos", {})
        intentos[url] = intentos.get(url, 0) + 1
        if intentos[url] >= MAX_INTENTOS:
            ab = self._state.setdefault("abandonadas", [])
            if url not in ab:
                ab.append(url)
                log.warning("%s abandonada tras %s intentos (%s)", url, intentos[url],
                            res.reason)

    def run_until(self, max_products: int | None = None,
                  max_minutes: float | None = None, urls: Iterable[str] | None = None,
                  respetar_horario: bool = True):
        """Procesa las pendientes respetando el cupo diario, la ventana horaria y
        las pausas. `max_products`/`max_minutes` limitan además la corrida."""
        url_queue = list(urls) if urls is not None else self._read_urls()
        pending = self.pendientes(url_queue)
        cupo = max(0, self.cfg.daily_target - self.hechas_hoy())
        if max_products is not None:
            cupo = min(cupo, max_products)
        log.info("scheduler: %d en la lista, %d pendientes, cupo de hoy %d",
                 len(url_queue), len(pending), cupo)
        results: list[Result] = []
        if not cupo or not pending:
            return results
        try:
            self.pipeline.precargar(pending[:cupo])
        except Exception as exc:
            log.warning("precarga degradada (%s)", exc)
        start = dt.datetime.now()
        hechas = 0
        for url in pending:
            if hechas >= cupo:
                break
            if max_minutes is not None and (dt.datetime.now() - start).total_seconds() > max_minutes * 60:
                break
            if respetar_horario and not self.in_work_hours(dt.datetime.now()):
                log.info("fuera de ventana (9-18 lun-vie): detengo corrida")
                break
            if results:
                time.sleep(self._delay())
            try:
                res = self.pipeline.process(url)
            except Exception as exc:  # nunca tumba el ciclo
                res = Result(url=url, status="failed", reason=f"excepción: {exc}")
            results.append(res)
            self._anotar(url, res)
            if res.status != "skipped":
                hechas += 1
            self._save_state()
            log.info("[%d/%d] %s -> %s (%s)", hechas, cupo, url, res.status,
                     res.reason or "")
        self._state["last_run"] = dt.datetime.now().isoformat()
        self._save_state()
        return results
