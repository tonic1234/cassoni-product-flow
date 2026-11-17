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
        assert cfg.db_url == f"sqlite:///{tmp_path.as_posix()}/data/cassoni.db"

    def test_ruta_absoluta_se_respeta(self, tmp_path):
        from cassoni.config import Config
        (tmp_path / "abs.json").write_text("{}")
        (tmp_path / ".env.staging").write_text(
            f"CASSONI_GSC_SERVICE_ACCOUNT_FILE={tmp_path}/abs.json\n")
        cfg = Config.load(env="staging", env_file=tmp_path / ".env.staging")
        assert cfg.gsc_service_account_file == f"{tmp_path}/abs.json"


class TestStagingNoApuntaAProduccion:
    """Auditoría 3-nov: el preflight del 2-nov corrió con env=staging y
    base=https://cassoni.com. Un --write ahí escribía en la tienda real."""

    def _cfg(self, env, base):
        c = Config(env=env)
        c.wc_base, c.wc_key, c.wc_secret = base, "k", "s"
        c.gsc_service_account_file = "x"
        c.dfs_login = c.dfs_password = "x"
        c.llm_base_url, c.llm_api_key, c.llm_editor_model = "u", "k", "m"
        return c

    def test_staging_con_base_de_produccion_es_invalido(self):
        faltan = self._cfg("staging", "https://cassoni.com").validate()
        assert any("PRODUCCIÓN" in f for f in faltan)

    def test_staging_con_www_tambien(self):
        assert self._cfg("staging", "https://www.cassoni.com/").validate()

    def test_prod_con_base_de_produccion_es_valido(self):
        assert self._cfg("prod", "https://cassoni.com").validate() == []

    def test_staging_real_es_valido(self):
        assert self._cfg("staging", "https://22f34d534b.nxcli.io").validate() == []

    def test_hosts_de_produccion_configurables(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CASSONI_PROD_HOSTS", "tienda.example")
        monkeypatch.setenv("CASSONI_WC_BASE", "https://tienda.example")
        c = Config.load(env="staging", env_file=tmp_path / "nada.env")
        assert c.prod_hosts == ("tienda.example",)
        assert any("PRODUCCIÓN" in f for f in c.validate())


def test_comentario_al_final_de_la_linea(tmp_path):
    """Un '# ...' al final dejaba el tope de gasto sin efecto en silencio."""
    f = tmp_path / ".env.prod"
    f.write_text('CASSONI_DFS_PRESUPUESTO_USD=0.30   # tope\nCASSONI_DFS_COMPETIDORES=si_faltan # x\n'
                 'CASSONI_LLM_API_KEY="abc #no-es-comentario"\n')
    c = Config.load(env="prod", env_file=f)
    assert c.dfs_presupuesto_usd == 0.30
    assert c.dfs_competidores == "si_faltan"
    assert c.llm_api_key == "abc #no-es-comentario"


def test_el_ejemplo_de_env_se_lee_completo(tmp_path):
    from pathlib import Path
    ej = Path(__file__).resolve().parent.parent / ".env.staging.example"
    c = Config.load(env="staging", env_file=ej)
    assert c.dfs_location_code == 2840 and c.dfs_min_volume == 50
    assert c.dfs_competidores == "siempre" and c.dfs_presupuesto_usd == 0.50
