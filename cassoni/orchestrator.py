# -*- coding: utf-8 -*-
"""Orquestador — ciclo por producto con fallbacks y degradación elegante.

Pasos por producto:
  extract -> woo ficha -> gsc keywords -> mapeo+volumen -> editor -> validador
        -> aplicar a WooCommerce SOLO si gate abierto (write_enabled + validez).
Fallbacks:
  - Slug no es producto         -> skip (no procesar)
  - WooCommerce sin datos       -> skip + log
  - GSC sin keywords            -> skip (esperable en productos nuevos) + log
  - DataForSEO sin volumen      -> usa las de GSC igual (degradación)
  - LLM inválido / edición no    -> re-prompt 1x; si falla -> fallido
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from .config import Config
from .db import DB
from .editor import Editor
from .extract import extract_slug, ExtractionError
from .gsc import GSCClient
from .llm import LLMClient, LLMError
from .woo import WooCommerce, WooError
from .dataforseo import DataForSEOFetcher, KeywordMapper
from .opportunities import annotate as annotate_opportunities

log = logging.getLogger("cassoni.orchestrator")


@dataclass
class Result:
    url: str
    status: str                      # processed | skipped | failed
    reason: str = ""
    keywords: list = field(default_factory=list)
    selected: list = field(default_factory=list)
    edited_h1: Optional[str] = None
    edited_description: Optional[str] = None
    aprobado: bool = True
    aplicado: bool = False
    wc_response: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "processed"


class Pipeline:
    def __init__(self, config: Config, *, db: Optional[DB] = None,
                 woo: Optional[WooCommerce] = None, gsc: Optional[GSCClient] = None,
                 mapper: Optional[KeywordMapper] = None, editor: Optional[Editor] = None,
                 llm: Optional[LLMClient] = None, dry_run: bool | None = None):
        self.cfg = config
        if dry_run is not None:
            self.cfg.dry_run = dry_run
        self.db = db or DB(config)
        self.woo = woo or WooCommerce(config)
        self.gsc = gsc or GSCClient(config)
        self.mapper = mapper  # opcional: se puede pre-cargar el mapping global
        self.llm = llm or LLMClient(config)
        self.editor = editor or Editor(config, self.llm)
        from .validator import Validator
        self.validator = Validator(config, self.llm)

    def process(self, url: str) -> Result:
        # 0) identificar
        try:
            slug, kind = extract_slug(url)
        except ExtractionError as exc:
            return Result(url=url, status="skipped", reason=f"no es URL de producto: {exc}")
        if kind != "product":
            return Result(url=url, status="skipped", reason=f"tipo '{kind}' no se procesa (solo productos)")

        row_id = self.db.enqueue(url, slug)
        self._log_state(row_id, url)

        # 1) ficha WooCommerce
        try:
            product = self.woo.get_product_by_slug(slug)
        except WooError as exc:
            return self._fail(row_id, url, f"WooCommerce: {exc}")
        if product.get("status") != "publish":
            return Result(url=url, status="skipped", reason=f"producto status='{product.get('status')}'")
        h1_orig = product.get("name", "")
        desc_orig = product.get("description", "")

        # 2/3) keywords de GSC
        try:
            permalink = product.get("permalink") or url
            kw_rows = self.gsc.top_keywords_for_url(permalink or url)
            # etiquetar oportunidades (aditivo: categories+score en cada fila)
            kw_rows = annotate_opportunities(kw_rows) if kw_rows else kw_rows
        except Exception as exc:  # GSC fail -> no bloquea
            return self._fail(row_id, url, f"GSC: {exc}")
        if not kw_rows:
            return Result(url=url, status="skipped", reason="sin keywords en GSC (esperable en producto nuevo)")
            # NOTE: no llamar _fail; skip

        # 4) volumen DataForSEO (o degradación sin volumen)
        candidates = kw_rows
        if self.mapper is not None:
            try:
                selected = self.mapper.keywords_for_url(permalink or url)
                candidates = selected or candidates
            except Exception as exc:
                log.warning("DataForSEO degradado (%s) -> uso GSC bare", exc)
        candidates = candidates[: self.cfg_dfs_keep()]

        # 5) editor LLM
        try:
            edited = self.editor.edit(url=url, current_h1=h1_orig,
                                      current_description=desc_orig,
                                      keywords=candidates)
        except LLMError as exc:
            return self._fail(row_id, url, f"editor LLM: {exc}")

        # 6) validador (con re-trabajo)
        val = self.validator.pass_or_rework(
            url=url, original_h1=h1_orig, original_desc=desc_orig,
            edited_h1=edited["h1"], edited_desc=edited["description"],
            target_keywords=[k["keyword"] for k in candidates if isinstance(k, dict)],
            editor=self.editor, backup_keywords=candidates)
        vres = val["validacion"]

        # 7) aplicar (solo si gate abierto)
        applied = False
        wc_resp = {}
        if self.cfg.dry_run:
            wc_resp = {"dry_run": True, "apply_h1": val["edited"]["h1"],
                       "apply_desc_len": len(val["edited"]["description"])}
            applied = True  # en dry_run "aplicar" = intento registrado
        elif val["aprobado"]:
            try:
                wc_resp = self.woo.update_product(product["id"],
                                                  name=val["edited"]["h1"],
                                                  description=val["edited"]["description"],
                                                  allowed=True)
                applied = True
            except WooError as exc:
                self.record(row_id, status="failed", validation_result=vres,
                            reason=f"apply WooCommerce: {exc}")

        self.db.record(
            row_id,
            original_h1=h1_orig, original_description=desc_orig,
            edited_h1=val["edited"]["h1"], edited_description=val["edited"]["description"],
            gsc_keywords=kw_rows[:10], selected_keywords=candidates,
            validation_result=vres, validation_attempts=val["intentos"],
            status="processed" if (applied or val["aprobado"]) else "failed",
        )
        # para traza sin aplicar: dry_run deja en processed (no toca producción)
        return Result(
            url=url, status="processed",
            reason=("dry_run (sin tocar WooCommerce)" if self.cfg.dry_run
                    else vres.get("razon", "")),
            keywords=kw_rows, selected=candidates,
            edited_h1=val["edited"]["h1"], edited_description=val["edited"]["description"],
            aprobado=val["aprobado"], aplicado=applied, wc_response=wc_resp)

    def cfg_dfs_keep(self) -> int:
        return 10

    def _log_state(self, pid, url):
        self.db.record(pid, status="in_queue")

    def record(self, pid, **kw):
        self.db.record(pid, **kw)

    def _fail(self, pid, url: str, reason: str) -> Result:
        log.error("FALLO %s: %s", url, reason)
        self.db.record(pid, status="failed", reason=reason)
        return Result(url=url, status="failed", reason=reason)