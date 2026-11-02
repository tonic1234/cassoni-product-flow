# -*- coding: utf-8 -*-
from pathlib import Path

import pytest

from cassoni.config import Config, _load_env_file


def test_load_env_file(tmp_path):
    f = tmp_path / ".env.staging"
    f.write_text("CASSONI_WC_BASE=\"https://x.com\"\nCASSONI_WC_KEY=abc\n# comment\n\nB=2\n")
    d = _load_env_file(f)
    assert d["CASSONI_WC_BASE"] == "https://x.com"
    assert d["CASSONI_WC_KEY"] == "abc"
    assert d["B"] == "2"
    assert "comment" not in "\n".join(d.keys())


def test_config_env_file_and_defaults(tmp_path, monkeypatch):
    (tmp_path / ".env.staging").write_text(
        "CASSONI_WC_BASE=https://x.com\nCASSONI_WC_KEY=k\nCASSONI_WC_SECRET=s\n")
    monkeypatch.chdir(tmp_path)
    c = Config.load(env="staging")
    assert c.wc_base == "https://x.com"
    assert c.dry_run is True
    assert c.write_enabled is False


def test_config_write_flag(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    c = Config.load(env="staging", dry_run=False)
    assert c.write_enabled is True


def test_config_invalid_env():
    with pytest.raises(ValueError):
        Config.load(env="produccion")


def test_validate_reports_missing(tmp_path):
    c = Config()
    missing = c.validate()
    assert "CASSONI_WC_BASE" in missing
    assert "CASSONI_GSC_SERVICE_ACCOUNT_FILE" in missing

class TestRutasRelativasAlEnvFile:
    """La config se lee de un .env, pero las rutas relativas se resolvían contra el
    cwd: correr el CLI desde otra carpeta rompía GSC y partía la base SQLite."""

    def test_service_account_relativa_al_env(self, tmp_path):
        from cassoni.config import Config
        (tmp_path / "creds").mkdir()
        (tmp_path / "creds" / "gsc.json").write_text("{}")
        (tmp_path / ".env.staging").write_text(
            "CASSONI_GSC_SERVICE_ACCOUNT_FILE=creds/gsc.json\n"
            "CASSONI_DB_URL=sqlite:///./data/cassoni.db\n")
        cfg = Config.load(env="staging", env_file=tmp_path / ".env.staging")
        assert cfg.gsc_service_account_file == str(tmp_path / "creds" / "gsc.json")

    def test_db_sqlite_relativa_al_env(self, tmp_path):
        from cassoni.config import Config
        (tmp_path / ".env.staging").write_text(
            "CASSONI_DB_URL=sqlite:///./data/cassoni.db\n")
        cfg = Config.load(env="staging", env_file=tmp_path / ".env.staging")
        assert cfg.db_url == f"sqlite:///{tmp_path}/data/cassoni.db"

    def test_ruta_absoluta_se_respeta(self, tmp_path):
        from cassoni.config import Config
        (tmp_path / "abs.json").write_text("{}")
        (tmp_path / ".env.staging").write_text(
            f"CASSONI_GSC_SERVICE_ACCOUNT_FILE={tmp_path}/abs.json\n")
        cfg = Config.load(env="staging", env_file=tmp_path / ".env.staging")
        assert cfg.gsc_service_account_file == f"{tmp_path}/abs.json"
