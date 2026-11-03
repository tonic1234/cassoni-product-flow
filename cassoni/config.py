# -*- coding: utf-8 -*-
"""Configuración del pipeline — selectora de entorno (staging | producción)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


def _load_env_file(path: Path) -> dict:
    """Lee un .env simple (K=V, comentarios con #). No sobrescribe lo ya en os.environ."""
    out = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        # soporta CLAVE="valor" con/quotes
        k, v = s.split("=", 1)
        v = v.strip().strip('"').strip("'")
        if k not in os.environ:
            out[k.strip()] = v
    return out


VALID_ENVS = ("staging", "prod")
# hosts de la tienda REAL: un .env de staging que apunte acá escribiría en
# producción creyendo que está en staging (pasó: preflight del 2-nov con
# env=staging y base=https://cassoni.com). Se sobreescribe con CASSONI_PROD_HOSTS.
PROD_HOSTS_DEFAULT = ("cassoni.com", "www.cassoni.com")


@dataclass
class Config:
    env: str = "staging"                       # staging | prod
    dry_run: bool = True                       # True = no toca WooCommerce
    db_url: str = "sqlite:///./cassoni.db"     # SQLite dev / PostgreSQL prod
    # --- WooCommerce ---
    wc_base: str = ""
    wc_key: str = ""
    wc_secret: str = ""
    # --- GSC ---
    gsc_service_account_file: str = ""
    gsc_site: str = "sc-domain:cassoni.com"
    # --- DataForSEO ---
    dfs_login: str = ""
    dfs_password: str = ""
    dfs_max_requests_min: int = 12
    dfs_retries: int = 3
    dfs_bulk_size: int = 1000
    dfs_location_code: int = 2840              # EE.UU. (la tienda es en inglés)
    dfs_language_code: str = "en"
    dfs_min_volume: int = 10                   # debajo: Google Ads no informa
    dfs_cache_dias: int = 30                   # el volumen es mensual
    dfs_presupuesto_usd: float = 0.0          # tope de gasto por corrida (0 = sin tope)
    # --- LLM ---
    llm_base_url: str = ""                     # OpenAI-compatible endpoint
    llm_api_key: str = ""
    llm_editor_model: str = ""
    llm_validator_model: str = ""
    # --- Scheduler ---
    workday_start: int = 9
    workday_end: int = 18
    pause_min_s: int = 30
    pause_max_s: int = 300
    daily_target: int = 10                     # pizarra: 5-10 fichas por día
    prod_hosts: tuple = PROD_HOSTS_DEFAULT

    @staticmethod
    def load(env: str = "staging", dry_run: bool | None = None,
             env_file: str | Path | None = None) -> "Config":
        """Construye la config para un entorno. Lee <env_file> (default .env.<env>)
        y luego os.environ (que manda)."""
        if env not in VALID_ENVS:
            raise ValueError(f"env inválido: {env!r} (use {VALID_ENVS})")
        base = Path(env_file) if env_file else Path(f".env.{env}")
        data = _load_env_file(base)

        def g(key: str, default: str = "") -> str:
            return os.environ.get(key) or data.get(key) or default

        c = Config(env=env)
        c.dry_run = True if dry_run is None else dry_run
        c.db_url = g("CASSONI_DB_URL", c.db_url)
        c.wc_base = g("CASSONI_WC_BASE")
        c.wc_key = g("CASSONI_WC_KEY")
        c.wc_secret = g("CASSONI_WC_SECRET")
        c.gsc_service_account_file = g("CASSONI_GSC_SERVICE_ACCOUNT_FILE")
        c.gsc_site = g("CASSONI_GSC_SITE", c.gsc_site)
        c.dfs_login = g("CASSONI_DFS_LOGIN")
        c.dfs_password = g("CASSONI_DFS_PASSWORD")
        c.llm_base_url = g("CASSONI_LLM_BASE_URL")
        c.llm_api_key = g("CASSONI_LLM_API_KEY")
        c.llm_editor_model = g("CASSONI_LLM_EDITOR_MODEL")
        c.llm_validator_model = g("CASSONI_LLM_VALIDATOR_MODEL")
        # las rutas relativas del .env se resuelven contra la carpeta del .env, no
        # contra el cwd: si no, correr el CLI desde otro lado rompe GSC y parte la DB
        base_dir = base.resolve().parent if base.exists() else Path.cwd()
        if c.gsc_service_account_file and not Path(c.gsc_service_account_file).is_absolute():
            cand = base_dir / c.gsc_service_account_file
            if cand.exists() or base.exists():
                c.gsc_service_account_file = str(cand)
        if c.db_url.startswith("sqlite:///./") or c.db_url.startswith("sqlite:///"):
            resto = c.db_url[len("sqlite:///"):]
            if resto.startswith("./") or (resto and not resto.startswith("/")):
                ruta = (base_dir / resto.lstrip("./")).resolve()
                c.db_url = f"sqlite:///{ruta}"
        for campo, clave in (("dfs_max_requests_min", "CASSONI_DFS_MAX_REQ_MIN"),
                             ("dfs_location_code", "CASSONI_DFS_LOCATION"),
                             ("dfs_min_volume", "CASSONI_DFS_MIN_VOLUMEN"),
                             ("dfs_cache_dias", "CASSONI_DFS_CACHE_DIAS"),
                             ("daily_target", "CASSONI_FICHAS_POR_DIA")):
            try:
                setattr(c, campo, int(g(clave) or getattr(c, campo)))
            except ValueError:
                pass
        c.dfs_language_code = g("CASSONI_DFS_LANGUAGE", c.dfs_language_code)
        try:
            c.dfs_presupuesto_usd = float(g("CASSONI_DFS_PRESUPUESTO_USD") or 0)
        except ValueError:
            pass
        hosts = g("CASSONI_PROD_HOSTS")
        if hosts:
            c.prod_hosts = tuple(h.strip().lower() for h in hosts.split(",") if h.strip())
        return c

    @property
    def wc_host(self) -> str:
        return (urlsplit(self.wc_base).hostname or "").lower()

    def validate(self) -> list[str]:
        """Devuelve la lista de campos faltantes (vacío = todo ok)."""
        missing = []
        if not self.wc_base:
            missing.append("CASSONI_WC_BASE")
        if not self.wc_key or not self.wc_secret:
            missing.append("CASSONI_WC_KEY/SECRET")
        if not self.gsc_service_account_file:
            missing.append("CASSONI_GSC_SERVICE_ACCOUNT_FILE")
        if not self.dfs_login or not self.dfs_password:
            missing.append("CASSONI_DFS_LOGIN/PASSWORD")
        if not self.llm_base_url or not self.llm_api_key or not self.llm_editor_model:
            missing.append("CASSONI_LLM_* (base/key/editor_model)")
        if self.env == "staging" and self.wc_host in self.prod_hosts:
            missing.append(f"CASSONI_WC_BASE: env=staging apunta a PRODUCCIÓN "
                           f"({self.wc_host}); usá --env prod o una base de staging")
        return missing

    @property
    def write_enabled(self) -> bool:
        """El pipeline solo puede escribir en WooCommerce si NO es dry_run."""
        return not self.dry_run

    def __repr__(self) -> str:  # no expone secretos
        return (f"Config(env={self.env!r}, dry_run={self.dry_run}, "
                f"wc_base={self.wc_base or '<set>'}.., db={self.db_url.split('//')[0]}://)")