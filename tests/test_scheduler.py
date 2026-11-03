# -*- coding: utf-8 -*-
"""Tests del scheduler: ventana horaria, resumen de pausas."""
import datetime as dt

import pytest

from cassoni.scheduler import Scheduler


def test_in_work_hours():
    assert Scheduler.in_work_hours(dt.datetime(2026, 8, 31, 10, 0)) is True   # lunes
    assert Scheduler.in_work_hours(dt.datetime(2026, 8, 31, 8, 59)) is False
    assert Scheduler.in_work_hours(dt.datetime(2026, 8, 31, 17, 0)) is True
    assert Scheduler.in_work_hours(dt.datetime(2026, 8, 31, 18, 0)) is False
    assert Scheduler.in_work_hours(dt.datetime(2026, 9, 5, 10, 0)) is False   # sábado
    assert Scheduler.in_work_hours(dt.datetime(2026, 8, 30, 10, 0)) is False   # domingo


def test_delay_in_bounds(cfg):
    # cfg.pause_min_s=30 pause_max_s=300 por defecto
    import random
    random.seed(7)
    delays = [Scheduler(cfg, None, urls_file="x")._delay() for _ in range(200)]
    assert all(30 <= d <= 300 for d in delays)
    # distribución no uniforme (triangular) -> la media no es el punto medio exacto
    mean = sum(delays) / len(delays)
    assert 30 < mean < 300


def test_state_load_save(tmp_path, cfg):
    s = Scheduler(cfg, None, urls_file="x", state_file=str(tmp_path / "st.json"))
    s._state["done"] = ["https://a"]
    s._save_state()
    assert "done" in Scheduler(cfg, None, urls_file="x",
                               state_file=str(tmp_path / "st.json"))._state


def test_read_urls(tmp_path, cfg):
    f = tmp_path / "urls.txt"
    f.write_text("# comentario\nhttps://a/p1/\n\nhttps://a/p2/\n")
    s = Scheduler(cfg, None, urls_file=str(f))
    assert s._read_urls() == ["https://a/p1/", "https://a/p2/"]

# --- goteo diario (3-nov-2026) ------------------------------------------------
from cassoni.orchestrator import Result


class _PipeFake:
    def __init__(self, status="processed"):
        self.status = status
        self.procesadas = []
        self.precargadas = []

    def precargar(self, urls):
        self.precargadas.append(list(urls))

    def process(self, url):
        self.procesadas.append(url)
        st = self.status(url) if callable(self.status) else self.status
        return Result(url=url, status=st, reason="")


def _sched(tmp_path, pipe, target=10):
    from cassoni.config import Config
    from cassoni.scheduler import Scheduler
    c = Config(env="staging")
    c.daily_target = target
    s = Scheduler(c, pipe, urls_file=str(tmp_path / "lista.txt"),
                  state_file=str(tmp_path / "st.json"))
    s._delay = lambda: 0
    return s


def _urls(n):
    return [f"https://x.com/product/p{i}/" for i in range(n)]


def test_respeta_el_cupo_diario(tmp_path):
    pipe = _PipeFake()
    s = _sched(tmp_path, pipe, target=10)
    s.run_until(urls=_urls(25), respetar_horario=False)
    assert len(pipe.procesadas) == 10
    s.run_until(urls=_urls(25), respetar_horario=False)        # mismo día: cupo agotado
    assert len(pipe.procesadas) == 10
    assert s.hechas_hoy() == 10


def test_la_lista_crece_y_sigue_donde_quedo(tmp_path):
    pipe = _PipeFake()
    s = _sched(tmp_path, pipe, target=3)
    s.run_until(urls=_urls(3), respetar_horario=False)
    s._state["por_dia"] = {}                                  # "otro día"
    s.run_until(urls=_urls(6), respetar_horario=False)
    assert pipe.procesadas == _urls(6)


def test_las_rechazadas_se_abandonan_tras_dos_intentos(tmp_path):
    """Antes se reintentaban para siempre y cada intento gastaba LLM."""
    pipe = _PipeFake(status="rejected")
    s = _sched(tmp_path, pipe, target=10)
    s.run_until(urls=_urls(1), respetar_horario=False)
    s.run_until(urls=_urls(1), respetar_horario=False)
    s.run_until(urls=_urls(1), respetar_horario=False)
    assert len(pipe.procesadas) == 2
    assert s._state["abandonadas"] == _urls(1)


def test_las_salteadas_no_consumen_cupo(tmp_path):
    pipe = _PipeFake(status=lambda u: "skipped" if u.endswith(("p0/", "p1/")) else "processed")
    s = _sched(tmp_path, pipe, target=2)
    s.run_until(urls=_urls(5), respetar_horario=False)
    assert pipe.procesadas == _urls(4)


def test_precarga_el_lote_del_dia(tmp_path):
    pipe = _PipeFake()
    _sched(tmp_path, pipe, target=3).run_until(urls=_urls(5), respetar_horario=False)
    assert pipe.precargadas == [_urls(3)]
