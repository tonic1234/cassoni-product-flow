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