# -*- coding: utf-8 -*-
"""Cron supervisor anti-bot.

Ejecuta el pipeline en horario de oficina (9-18 local, lun-vie), con pausas
aleatorias de 30s-5min entre productos (no uniformes, para no formar patrón),
y un ritmo de ~50 productos/día. Reanuda al día siguiente lo que quedó
pendiente. Pensado para correr bajo systemd/cron como proceso de larga duración.
"""
from __future__ import annotations

import datetime as dt
import logging
import random
import time
from pathlib import Path
from typing import Iterable

from .config import Config
from .orchestrator import Pipeline, Result

log = logging.getLogger("cassoni.scheduler")


class Scheduler:
    def __init__(self, config: Config, pipeline: Pipeline,
                 urls_file: str, state_file: str = "./cassoni_sched.json",
                 dry_run: bool = True):
        self.cfg = config
        self.pipeline = pipeline
        self.urls_file = Path(urls_file)
        self.state_file = Path(state_file)
        self._state = self._load_state()

    # ---- utilidades de estado ----
    def _load_state(self) -> dict:
        import json
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except Exception:
                return {}
        return {}

    def _save_state(self):
        import json
        self.state_file.write_text(json.dumps(self._state, ensure_ascii=False, indent=2))

    def _read_urls(self) -> list[str]:
        if not self.urls_file.exists():
            return []
        return [l.strip() for l in self.urls_file.read_text().splitlines()
                if l.strip() and not l.startswith("#")]

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

    def run_until(self, max_products: int | None = None,
                  max_minutes: float | None = None, urls: Iterable[str] | None = None):
        """Procesa URLs (de archivo o inyectadas) respetando ventana horaria y
        pausas. `max_products`/`max_minutes` limitan la corrida (para --batch)."""
        url_queue = list(urls) if urls is not None else self._read_urls()
        done = self._state.get("done", [])
        pending = [u for u in url_queue if u not in done]
        log.info("scheduler: %d total, %d pendientes", len(url_queue), len(pending))
        results: list[Result] = []
        start = dt.datetime.now()
        produced = 0
        for url in pending:
            # límites de corrida
            if max_products is not None and produced >= max_products:
                break
            if max_minutes is not None and (dt.datetime.now() - start).total_seconds() > max_minutes * 60:
                break
            # ventana horaria: si no es horario hábil, parar (reanuda el día siguiente)
            if not self.in_work_hours(dt.datetime.now()):
                log.info("fuera de ventana (9-18 lun-vie): detengo corrida")
                break
            time.sleep(self._delay())
            try:
                res = self.pipeline.process(url)
            except Exception as exc:  # nunca tumba el ciclo
                res = Result(url=url, status="failed", reason=f"excepción: {exc}")
            results.append(res)
            produced += 1
            if res.status == "processed" or res.status == "skipped":
                if url not in self._state.setdefault("done", []):
                    self._state["done"].append(url)
            self._save_state()
            log.info("[%d/%d] %s -> %s (%s)", produced, len(pending), url,
                     res.status, res.reason or "")
        self._state["last_run"] = dt.datetime.now().isoformat()
        self._save_state()
        return results