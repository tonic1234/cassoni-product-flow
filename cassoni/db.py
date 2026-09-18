# -*- coding: utf-8 -*-
"""Base de datos de TRAZABILIDAD.

Registra por producto: URL, slug, keywords de GSC, volumen DataForSEO, cuáles
se seleccionaron y por qué, dónde se insertaron (H1/desc), texto antes/después,
resultado de validación, y costo real. Backend: SQLite (dev/test) o PostgreSQL
(prod) — el schema es el mismo (SQLAlchemy). Idempotente.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import (Column, DateTime, Integer, String, Text, create_engine,
                        select)
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import Config

log = logging.getLogger("cassoni.db")
Base = declarative_base()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ProcessedProduct(Base):
    __tablename__ = "cassoni_processed_products"
    id = Column(Integer, primary_key=True)
    url = Column(String(500), index=True, nullable=False)
    slug = Column(String(255))
    status = Column(String(20), default="in_queue")  # in_queue|processed|skipped|failed
    # keywords
    gsc_keywords = Column(Text)          # JSON [{keyword,clicks,impressions}]
    df_keywords = Column(Text)           # JSON [{keyword,volume,cpc}]
    selected_keywords = Column(Text)     # JSON [{keyword,volume,ine:H1|desc}]
    selection_reason = Column(Text)
    # texto antes/después
    original_h1 = Column(Text)
    original_description = Column(Text)
    edited_h1 = Column(Text)
    edited_short_description = Column(Text)   # descripción corta (arriba del fold)
    edited_description = Column(Text)
    # validación
    validation_result = Column(Text)     # JSON {aprobado, issues, ...}
    validation_attempts = Column(Integer, default=0)
    # costos
    dfs_cost = Column(String(20))        # "0.285" USD (CRITICO: log por keywords)
    llm_cost = Column(String(20))
    # meta
    host_env = Column(String(10))        # staging|prod
    dry_run = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class DB:
    def __init__(self, config: Config, *, echo: bool = False):
        self.cfg = config
        self.engine = create_engine(config.db_url, echo=echo)
        Base.metadata.create_all(self.engine)
        self._migrate()
        self.Session = sessionmaker(bind=self.engine)

    def _migrate(self):
        """Migración idempotente para bases EXISTENTES: agrega columnas nuevas
        del schema. create_all solo crea tablas; no altera columnas. SQLite no
        soporta 'ADD COLUMN IF NOT EXISTS' -> try/except."""
        try:
            from sqlalchemy import text
            with self.engine.begin() as conn:
                conn.execute(text(
                    "ALTER TABLE cassoni_processed_products "
                    "ADD COLUMN edited_short_description TEXT"))
        except Exception as exc:  # ya existe (o backend sin ALTER) -> ok
            log.debug("Migración de columnas no aplicó (esperado si ya existen): %s", exc)

    def get_state(self, url: str) -> ProcessedProduct | None:
        with self.Session() as s:
            return s.execute(select(ProcessedProduct).where(
                ProcessedProduct.url == url)).scalar_one_or_none()

    def enqueue(self, url: str, slug: str) -> int:
        """Devuelve el product_id (int) del row en cola, creándolo si no existe."""
        with self.Session() as s:
            existing = s.execute(select(ProcessedProduct).where(
                ProcessedProduct.url == url)).scalar_one_or_none()
            if existing:
                return existing.id
            row = ProcessedProduct(url=url, slug=slug, status="in_queue",
                                   host_env=self.cfg.env, dry_run=1 if self.cfg.dry_run else 0)
            s.add(row)
            s.flush()          # asigna row.id sin cerrar la sesión
            pid = row.id
            s.commit()
            return pid

    def record(self, product_id: int, **fields) -> None:
        with self.Session() as s:
            row = s.get(ProcessedProduct, product_id)
            if row is None:
                return
            for k, v in fields.items():
                if v is None:
                    continue
                if isinstance(v, (dict, list)):
                    setattr(row, k, json.dumps(v, ensure_ascii=False))
                elif isinstance(v, bool):
                    setattr(row, k, 1 if v else 0)
                else:
                    setattr(row, k, v)
            s.commit()

    def summary(self) -> dict:
        with self.Session() as s:
            return {
                "total": s.query(ProcessedProduct).count(),
                "processed": s.query(ProcessedProduct).filter_by(status="processed").count(),
                "skipped": s.query(ProcessedProduct).filter_by(status="skipped").count(),
                "failed": s.query(ProcessedProduct).filter_by(status="failed").count(),
                "in_queue": s.query(ProcessedProduct).filter_by(status="in_queue").count(),
            }