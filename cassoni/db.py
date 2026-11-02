# -*- coding: utf-8 -*-
"""Base de datos de TRAZABILIDAD.

Registra por producto: URL, slug, keywords de GSC, volumen DataForSEO, cuáles
se seleccionaron y por qué, dónde se insertaron (H1/desc), texto antes/después,
resultado de validación, costo real y la LÍNEA BASE de la consulta objetivo
(posición/impresiones/clics al momento de editar) para poder medir el efecto.

Backend: SQLite (dev/test) o PostgreSQL (prod) — el schema es el mismo
(SQLAlchemy). La migración es idempotente: `create_all` crea lo que falta y
`_migrar_columnas` agrega las columnas nuevas a tablas que ya existían.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import (Column, DateTime, Float, Integer, String, Text,
                        create_engine, select, text)
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
    edited_description = Column(Text)
    # línea base de la consulta objetivo (2-nov-2026)
    baseline_keyword = Column(String(255))
    baseline_position = Column(Float)
    baseline_impressions = Column(Integer)
    baseline_clicks = Column(Integer)
    baseline_ctr = Column(Float)
    baseline_window = Column(String(60))   # "2026-08-04..2026-11-02"
    baseline_at = Column(DateTime)
    # validación
    validation_result = Column(Text)     # JSON {aprobado, issues, ...}
    validation_attempts = Column(Integer, default=0)
    # costos
    dfs_cost = Column(String(20))        # "0.285" USD (CRITICO: log por keywords)
    llm_cost = Column(String(20))
    llm_tokens_in = Column(Integer)
    llm_tokens_out = Column(Integer)
    # meta
    host_env = Column(String(10))        # staging|prod
    dry_run = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class Review(Base):
    """Una medición del efecto, a N días de la edición."""
    __tablename__ = "cassoni_reviews"
    id = Column(Integer, primary_key=True)
    url = Column(String(500), index=True, nullable=False)
    keyword = Column(String(255))
    days = Column(Integer)
    position = Column(Float)
    impressions = Column(Integer)
    clicks = Column(Integer)
    ctr = Column(Float)
    delta_position = Column(Float)
    delta_impressions = Column(Integer)
    delta_clicks = Column(Integer)
    verdict = Column(String(20))         # subio|igual|bajo|sin_datos
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# columnas agregadas después de la primera versión del schema
_COLUMNAS_NUEVAS = [
    ("baseline_keyword", "VARCHAR(255)"),
    ("baseline_position", "FLOAT"),
    ("baseline_impressions", "INTEGER"),
    ("baseline_clicks", "INTEGER"),
    ("baseline_ctr", "FLOAT"),
    ("baseline_window", "VARCHAR(60)"),
    ("baseline_at", "TIMESTAMP"),
    ("llm_tokens_in", "INTEGER"),
    ("llm_tokens_out", "INTEGER"),
]


class DB:
    def __init__(self, config: Config, *, echo: bool = False):
        self.cfg = config
        self.engine = create_engine(config.db_url, echo=echo)
        Base.metadata.create_all(self.engine)
        self._migrar_columnas()
        self.Session = sessionmaker(bind=self.engine)

    def _migrar_columnas(self) -> None:
        """Agrega columnas nuevas a una base vieja. Idempotente en SQLite y PG."""
        for nombre, tipo in _COLUMNAS_NUEVAS:
            try:
                with self.engine.begin() as conn:
                    conn.execute(text(
                        f"ALTER TABLE cassoni_processed_products "
                        f"ADD COLUMN {nombre} {tipo}"))
            except Exception:
                pass          # ya existe: es el caso normal en cada arranque

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

    def save_review(self, **fields) -> int:
        with self.Session() as s:
            row = Review(**fields)
            s.add(row)
            s.flush()
            rid = row.id
            s.commit()
            return rid

    def reviews_for(self, url: str) -> list[Review]:
        with self.Session() as s:
            return list(s.execute(select(Review).where(Review.url == url)
                                  .order_by(Review.created_at)).scalars())

    def summary(self) -> dict:
        with self.Session() as s:
            return {
                "total": s.query(ProcessedProduct).count(),
                "processed": s.query(ProcessedProduct).filter_by(status="processed").count(),
                "skipped": s.query(ProcessedProduct).filter_by(status="skipped").count(),
                "failed": s.query(ProcessedProduct).filter_by(status="failed").count(),
                "rejected": s.query(ProcessedProduct).filter_by(status="rejected").count(),
                "in_queue": s.query(ProcessedProduct).filter_by(status="in_queue").count(),
                "reviews": s.query(Review).count(),
            }
