# -*- coding: utf-8 -*-
"""Base de datos de TRAZABILIDAD.

Registra por producto: URL, slug, keywords de GSC, volumen DataForSEO, cuáles
se seleccionaron y por qué, dónde se insertaron (H1/desc), texto antes/después,
resultado de validación, costo real y las KEYWORDS OBJETIVO de cada ficha (las
3 que se incorporaron, con su línea base) para poder medir el efecto de cada una.
También guarda la caché de volumen de DataForSEO y sirve de registro
anti-canibalización: qué keyword quedó asignada a qué ficha.

Backend: SQLite (dev/test) o PostgreSQL (prod) — el schema es el mismo
(SQLAlchemy). La migración es idempotente: `create_all` crea lo que falta y
`_migrar_columnas` agrega las columnas nuevas a tablas que ya existían.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from datetime import timedelta

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
    status = Column(String(20), default="in_queue")  # in_queue|processed|rejected|skipped|failed
    reason = Column(Text)                # por qué terminó en ese status
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
    applied = Column(Integer, default=0)  # 1 = se escribió de verdad en WooCommerce
    edited_at = Column(DateTime)          # cuándo se escribió (base de la medición)
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


class KeywordVolume(Base):
    """Caché de volumen de DataForSEO. volume NULL = DFS no lo informa (no es 0)."""
    __tablename__ = "cassoni_keyword_volume"
    keyword = Column(String(255), primary_key=True)
    location = Column(Integer, primary_key=True)
    volume = Column(Integer)
    cpc = Column(Float)
    competition = Column(Float)
    fetched_at = Column(DateTime)


class CompetenciaCache(Base):
    """Caché de lo que rankea la competencia para una consulta (DataForSEO SERP +
    ranked_keywords): es la consulta más cara del pipeline y se repite entre fichas y
    corridas (23-nov)."""
    __tablename__ = "cassoni_competencia_cache"
    consulta = Column(String(255), primary_key=True)
    location = Column(Integer, primary_key=True)
    datos = Column(Text)                 # JSON [resumen, rankeadas]
    fetched_at = Column(DateTime)


class KeywordObjetivo(Base):
    """Una de las (hasta) 3 keywords que se incorporaron a una ficha.

    Sirve para dos cosas: medir el efecto de CADA keyword y no asignar la misma
    keyword a dos fichas (anti-canibalización entre fichas ya editadas)."""
    __tablename__ = "cassoni_keyword_objetivo"
    id = Column(Integer, primary_key=True)
    url = Column(String(500), index=True, nullable=False)
    keyword = Column(String(255), index=True, nullable=False)
    origen = Column(String(20))          # gsc | competidor
    volume = Column(Integer)
    compartida_con = Column(String(500))  # URL de otra ficha que ya la usa (si no quedó otra)
    baseline_position = Column(Float)
    baseline_impressions = Column(Integer)
    baseline_clicks = Column(Integer)
    baseline_ctr = Column(Float)
    aplicada = Column(Integer, default=0)
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
    ("reason", "TEXT"),
    ("applied", "INTEGER DEFAULT 0"),
    ("edited_at", "TIMESTAMP"),
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

    # --- caché de volumen ---
    def volumenes_frescos(self, keywords: list[str], location: int,
                          max_dias: int) -> dict[str, dict]:
        """{kw: {volume, cpc, competition}} de lo que está en caché y no venció."""
        if not keywords:
            return {}
        limite = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=max_dias)
        with self.Session() as s:
            filas = s.execute(select(KeywordVolume).where(
                KeywordVolume.keyword.in_(keywords),
                KeywordVolume.location == location)).scalars().all()
            return {f.keyword: {"volume": f.volume, "cpc": f.cpc,
                                "competition": f.competition}
                    for f in filas if f.fetched_at and f.fetched_at >= limite}

    def competencia_fresca(self, consulta: str, location: int, max_dias: int):
        """(resumen, rankeadas) en caché y vigente, o None."""
        limite = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=max_dias)
        with self.Session() as s:
            row = s.get(CompetenciaCache, (consulta[:255], location))
            if not row or not row.fetched_at or row.fetched_at < limite:
                return None
            resumen, rank = json.loads(row.datos or "[[], []]")
            return resumen, rank

    def guardar_competencia(self, consulta: str, location: int, resumen: list, rank: list) -> None:
        with self.Session() as s:
            row = s.get(CompetenciaCache, (consulta[:255], location)) or CompetenciaCache(
                consulta=consulta[:255], location=location)
            row.datos = json.dumps([resumen, rank], ensure_ascii=False, default=str)
            row.fetched_at = datetime.now(timezone.utc).replace(tzinfo=None)
            s.merge(row)
            s.commit()

    def guardar_volumenes(self, datos: dict[str, dict | None], location: int) -> None:
        ahora = datetime.now(timezone.utc).replace(tzinfo=None)
        with self.Session() as s:
            for kw, d in datos.items():
                d = d or {}
                row = s.get(KeywordVolume, (kw, location)) or KeywordVolume(
                    keyword=kw, location=location)
                row.volume = d.get("volume")
                row.cpc = d.get("cpc")
                row.competition = d.get("competition")
                row.fetched_at = ahora
                s.merge(row)
            s.commit()

    # --- keywords objetivo ---
    def guardar_objetivos(self, url: str, objetivos: list[dict], *, aplicada: bool) -> None:
        """Reemplaza las keywords objetivo de la ficha por las de esta corrida."""
        with self.Session() as s:
            s.query(KeywordObjetivo).filter_by(url=url).delete()
            for o in objetivos:
                s.add(KeywordObjetivo(
                    url=url, keyword=o["keyword"], origen=o.get("origen", "gsc"),
                    volume=o.get("volume"), compartida_con=o.get("compartida_con"),
                    baseline_position=o.get("position"),
                    baseline_impressions=o.get("impressions"),
                    baseline_clicks=o.get("clicks"), baseline_ctr=o.get("ctr"),
                    aplicada=1 if aplicada else 0))
            s.commit()

    def objetivos_de(self, url: str) -> list[KeywordObjetivo]:
        with self.Session() as s:
            return list(s.execute(select(KeywordObjetivo).where(
                KeywordObjetivo.url == url).order_by(KeywordObjetivo.id)).scalars())

    def keywords_asignadas(self, excepto_url: str = "") -> dict[str, str]:
        """{keyword normalizada: url} de las keywords YA escritas en otras fichas."""
        with self.Session() as s:
            filas = s.execute(select(KeywordObjetivo).where(
                KeywordObjetivo.aplicada == 1,
                KeywordObjetivo.url != excepto_url)).scalars().all()
            return {" ".join(f.keyword.lower().split()): f.url for f in filas}

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
