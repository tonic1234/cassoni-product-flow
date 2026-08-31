# -*- coding: utf-8 -*-
import tempfile
from pathlib import Path

import pytest

from cassoni.config import Config


def make_config(tmp_path: Path, *, env="staging", dry_run=True, db_url=None) -> Config:
    c = Config(env=env, dry_run=dry_run)
    c.db_url = db_url or f"sqlite:///{tmp_path}/test.db"
    c.wc_base = "https://staging.cassoni.test"
    c.wc_key = "ck_test"
    c.wc_secret = "cs_test"
    c.gsc_service_account_file = str(tmp_path / "gsc.json")
    c.dfs_login = "login"
    c.dfs_password = "pass"
    c.llm_base_url = "https://llm.test/v1"
    c.llm_api_key = "key"
    c.llm_editor_model = "editor"
    c.llm_validator_model = "validator"
    return c


@pytest.fixture
def cfg(tmp_path):
    return make_config(tmp_path)


@pytest.fixture
def cfg_write(tmp_path):
    return make_config(tmp_path, dry_run=False)