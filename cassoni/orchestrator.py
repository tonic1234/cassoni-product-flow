# -*- coding: utf-8 -*-
"""Orquestador — ciclo por producto con fallbacks y degradación elegante.

Pasos por producto:
  extract -> woo ficha -> GSC keywords -> mapeo+volumen -> editor LLM (ficha
  completa: H1 + desc corta + desc larga + secundarias/descartadas)
        -> validador (reglas mecánicas en código + LLM) -> aplicar a WooCommerce
        SOLO si gate abierto (write_enabled + validez).
Inputs nuevos del editor (spec cliente): categorías, marca, atributos técnicos y
keywords ya usadas en otras fichas de la categoría (anti-canibalización).
Fallbacks:
  - Slug no es producto         -> skip (no procesar)
  - WooCommerce sin datos       -> skip + log
  - GSC sin keywords            -> skip (esperable en productos nuevos) + log
  - DataForSEO sin volumen      -> usa las de GSC igual (degradación)
  - LLM inválido / edición no    -> re-prompt 1x; si falla -> fallido
"""

from __future__ import annotations

import logging
import re
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

BRAND_ATTR_NAMES = ("marca", "brand")
_WS_RX = re.compile(r"\s+")


def norm_name(s: str) -> str:
    return _WS_RX.sub(" ", (s or "").strip().lower())


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


def _brand_y_atributos(product: dict) -> tuple[str, tuple]:
    """Marca (atributo 'marca'/'brand') y lista de atributos técnicos legibles.
    No inventa nada: solo lo que trae el JSON del producto (regla del cliente)."""
    attrs = product.get("attributes") or []
    brand = ""
    tecnicos = []
    for a in attrs:
        name = (a.get("name") or "").strip()
        opts = [o for o in (a.get("options") or []) if o]
        if not name:
            continue
        if name.lower().strip() in BRAND_ATTR_NAMES:
            if opts:
                brand = opts[0]
            continue
        if opts:
            tecnicos.append(f"{name}: {', '.join(str(o) for o in opts)}")
    return brand, tuple(tecnicos)


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
        self._cat_names_cache: dict[int, tuple] = {}

    # --- helpers ---
    def _keywords_ya_usadas(self, product: dict) -> tuple:
        """H1 (name) de las OTRAS fichas publicadas de las mismas categorías
        (input del filtro anti-canibalización). Con caché por categoría;
        opcional: si listar hermanos falla, se sigue sin esa señal."""
        cats = product.get("categories") or []
        nombres: list[str] = []
        for c in cats:
            cid = c.get("id")
            if not cid:
                continue
            if cid not in self._cat_names_cache:
                try:
                    hermanos = self.woo.products_by_category(cid, per_page=100)
                    self._cat_names_cache[cid] = tuple(
                        h["name"] for h in hermanos if h.get("name"))
                except Exception as exc:
                    log.warning("No se pudieron listar fichas de categoría %s (%s)",
                                cid, exc)
                    self._cat_names_cache[cid] = ()
            nombres.extend(self._cat_names_cache[cid])
        propio = norm_name((product.get("name") or "").strip())
        uniq = list(dict.fromkeys(nombres))
        return tuple(n for n in uniq if norm_name(n) != propio)

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
        sc_orig = product.get("short_description", "") or ""
        desc_orig = product.get("description", "")
        categorias = tuple(c.get("name", "") for c in (product.get("categories") or [])
                           if c.get("name"))
        marca, atributos = _brand_y_atributos(product)
        ya_usadas = self._keywords_ya_usadas(product)

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
        principal = candidates[0]["keyword"] if candidates else ""

        # 5) editor LLM (ficha completa, reglas del cliente)
        context = {
            "current_short_description": sc_orig,
            "categories": categorias,
            "brand": marca,
            "attributes": atributos,
            "keywords_ya_usadas": ya_usadas,
            "keyword_principal": principal,
        }
        try:
            edited = self.editor.edit(
                url=url, current_h1=h1_orig, current_description=desc_orig,
                keywords=candidates, **context)
        except LLMError as exc:
            return self._fail(row_id, url, f"editor LLM: {exc}")

        # 6) validador (reglas mecánicas + LLM, con re-trabajo)
        val = self.validator.pass_or_rework(
            url=url, original_h1=h1_orig, original_desc=desc_orig,
            edited=edited,
            target_keywords=[k["keyword"] for k in candidates if isinstance(k, dict)],
            editor=self.editor, backup_keywords=candidates, context=context)
        vres = val["validacion"]
        edited_final = val["edited"]

        # 7) aplicar (solo si gate abierto)
        applied = False
        wc_resp = {}
        if self.cfg.dry_run:
            wc_resp = {"dry_run": True, "apply_h1": edited_final.get("h1", ""),
                       "apply_desc_len": len(edited_final.get("description", ""))}
            applied = True  # en dry_run "aplicar" = intento registrado
        elif val["aprobado"]:
            try:
                wc_resp = self.woo.update_product(
                    product["id"],
                    name=edited_final.get("h1", ""),
                    description=edited_final.get("description", ""),
                    allowed=True)
                applied = True
            except WooError as exc:
                self.record(row_id, status="failed", validation_result=vres,
                            reason=f"apply WooCommerce: {exc}")

        self.db.record(
            row_id,
            original_h1=h1_orig, original_description=desc_orig,
            edited_h1=edited_final.get("h1", ""),
            edited_description=edited_final.get("description", ""),
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
            edited_h1=edited_final.get("h1", ""),
            edited_description=edited_final.get("description", ""),
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