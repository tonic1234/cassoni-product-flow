# -*- coding: utf-8 -*-
"""Orquestador — ciclo por ficha (flujo v2, equipo SEO 3-nov-2026).

  lista del día → ficha WooCommerce → H1 = "{Nombre} by {Marca}" (plantilla)
    → keywords de GSC + volumen DataForSEO → las que NO están en la descripción
    → (si faltan) mismo producto en 3 competidores mejor posicionados
    → 3 keywords con anti-canibalización → editor LLM (solo descripción larga)
    → validador (reglas en código + LLM, con re-trabajo)
    → escribe name + description SOLO con --write y aprobación
    → guarda las 3 keywords objetivo con su línea base para medir a 14/28 días

Garantías:
  - Idempotente: una ficha ya escrita (applied=1) no se vuelve a editar salvo
    --forzar. Re-correr la lista no edita encima de lo editado ni pisa la base.
  - Cada salida deja la fila con su status y su motivo (nada queda in_queue).
  - Un fallo de una ficha (Woo, GSC, LLM) no tumba el lote.

Fallbacks:
  - URL que no es de producto / ficha no publicada → skipped
  - GSC sin datos                → se intenta con competidores
  - DataForSEO sin volumen       → se usa la demanda real de GSC (impresiones)
  - Sin keywords que agregar     → solo se aplica el H1 de plantilla
  - LLM inválido                 → failed (la ficha queda para otro día)
"""

from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

from .config import Config
from .db import DB
from .editor import Editor
from .extract import extract_slug, ExtractionError
from .gsc import GSCClient
from .h1 import h1_plantilla
from .keywords import elegir_keywords
from .llm import LLMClient, LLMError
from .woo import WooCommerce, WooError
from . import reglas

log = logging.getLogger("cassoni.orchestrator")

BRAND_ATTR_NAMES = ("marca", "brand")
_WS_RX = re.compile(r"\s+")
MAX_KW_A_DFS_POR_FICHA = 100     # las de más impresiones: el pedido es por tarea


def norm_name(s: str) -> str:
    return _WS_RX.sub(" ", (s or "").strip().lower())


@dataclass
class Result:
    url: str
    status: str                      # processed | rejected | skipped | failed
    reason: str = ""
    keywords: list = field(default_factory=list)
    selected: list = field(default_factory=list)
    edited_h1: Optional[str] = None
    edited_description: Optional[str] = None
    aprobado: bool = True
    aplicado: bool = False
    wc_response: dict = field(default_factory=dict)
    h1_aviso: str = ""
    competidores: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "processed"


def _brand_y_atributos(product: dict) -> tuple[str, tuple]:
    """Marca y lista de atributos técnicos legibles. No inventa nada: sólo lo que
    trae el JSON del producto (regla del cliente).

    La marca vive en el campo `brands` de WooCommerce (`[{'id':..,'name':'Slide'}]`),
    medido el 13-oct-2026: 150/150 fichas lo traen y 0/150 tienen un atributo
    'marca'/'brand'. El atributo queda como respaldo por si alguna ficha no lo trae.
    """
    attrs = product.get("attributes") or []
    brand = ""
    for b in (product.get("brands") or []):
        nombre = html.unescape((b or {}).get("name") or "").strip()
        if nombre:
            brand = nombre
            break
    tecnicos = []
    for a in attrs:
        name = (a.get("name") or "").strip()
        opts = [o for o in (a.get("options") or []) if o]
        if not name:
            continue
        if name.lower().strip() in BRAND_ATTR_NAMES:
            if not brand and opts:
                brand = html.unescape(str(opts[0])).strip()      # respaldo
            continue
        if opts:
            tecnicos.append(f"{name}: {', '.join(str(o) for o in opts)}")
    return brand, tuple(tecnicos)


def _gsc_por_defecto(config):
    try:
        return GSCClient(config)
    except Exception as exc:          # sin credenciales de GSC: se sigue con competidores
        log.warning("GSC no disponible (%s)", exc)
        return None


def _dfs_por_defecto(config, db):
    """Volumen + competidores si hay credenciales de DataForSEO; si no, None."""
    if not (config.dfs_login and config.dfs_password):
        return None, None
    from .competidores import Competidores
    from .dataforseo import DataForSEOFetcher
    from .volumen import Volumenes
    fetcher = DataForSEOFetcher(config)
    propios = tuple(config.prod_hosts) + ((config.wc_host,) if config.wc_host else ())
    return Volumenes(config, db, fetcher), Competidores(fetcher, propios=propios)


_DEFECTO = object()


class Pipeline:
    def __init__(self, config: Config, *, db: Optional[DB] = None,
                 woo: Optional[WooCommerce] = None, gsc=_DEFECTO,
                 volumenes=_DEFECTO, competidores=_DEFECTO,
                 editor: Optional[Editor] = None, llm: Optional[LLMClient] = None,
                 dry_run: bool | None = None, forzar: bool = False):
        self.cfg = config
        if dry_run is not None:
            self.cfg.dry_run = dry_run
        self.forzar = forzar
        self.db = db or DB(config)
        self.woo = woo or WooCommerce(config)
        self.gsc = _gsc_por_defecto(config) if gsc is _DEFECTO else gsc
        if volumenes is _DEFECTO or competidores is _DEFECTO:
            vol_def, comp_def = _dfs_por_defecto(config, self.db)
            volumenes = vol_def if volumenes is _DEFECTO else volumenes
            competidores = comp_def if competidores is _DEFECTO else competidores
        self.volumenes = volumenes
        self.competidores = competidores
        self.llm = llm or LLMClient(config)
        self.editor = editor or Editor(config, self.llm)
        from .validator import Validator
        self.validator = Validator(config, self.llm)
        self._cat_names_cache: dict[int, tuple] = {}
        self._gsc_cache: dict[str, list[dict]] = {}

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

    def _gsc_de(self, url: str) -> list[dict]:
        if url in self._gsc_cache:
            return self._gsc_cache[url]
        filas = self.gsc.top_keywords_for_url(url) if self.gsc is not None else []
        self._gsc_cache[url] = filas or []
        return self._gsc_cache[url]

    def precargar(self, urls: list[str]) -> None:
        """Junta las keywords de GSC de todo el lote y pide el volumen en UN solo
        pedido a DataForSEO (cuesta lo mismo 10 keywords que 1.000)."""
        todas: list[str] = []
        for u in urls:
            try:
                filas = self._gsc_de(u)
            except Exception as exc:
                log.warning("GSC falló en la precarga de %s (%s)", u, exc)
                continue
            ordenadas = sorted(filas, key=lambda f: f.get("impressions") or 0, reverse=True)
            todas.extend(f.get("keyword", "") for f in ordenadas[:MAX_KW_A_DFS_POR_FICHA])
        if self.volumenes is not None and todas:
            self.volumenes.obtener(todas)

    def _con_volumen(self, filas: list[dict]) -> list[dict]:
        if self.volumenes is None or not filas:
            return filas
        try:
            return self.volumenes.anotar(filas)
        except Exception as exc:
            log.warning("Volumen degradado (%s): sigo con GSC", exc)
            return filas

    def _costos(self) -> dict:
        fn = getattr(self.llm, "consumo", None)
        llm = {"tokens_in": 0, "tokens_out": 0, "usd": 0.0, "llamadas": 0}
        if callable(fn):
            try:
                llm = dict(fn())
            except Exception:
                pass
        dfs = float(getattr(self.volumenes, "costo_usd", 0.0) or 0.0)
        return {**llm, "dfs_usd": dfs}

    # --- ciclo por ficha ---
    def process(self, url: str) -> Result:
        try:
            slug, kind = extract_slug(url)
        except ExtractionError as exc:
            return Result(url=url, status="skipped", reason=f"no es URL de producto: {exc}")
        if kind != "product":
            return Result(url=url, status="skipped",
                          reason=f"tipo '{kind}' no se procesa (solo productos)")

        previo = self.db.get_state(url)
        if previo is not None and previo.applied and not self.forzar:
            cuando = previo.edited_at.strftime("%Y-%m-%d") if previo.edited_at else "antes"
            return Result(url=url, status="skipped",
                          reason=f"ya editada ({cuando}): no se edita encima "
                                 f"(usar --forzar para rehacerla)")

        row_id = self.db.enqueue(url, slug)
        self.db.record(row_id, status="in_queue", host_env=self.cfg.env,
                       dry_run=1 if self.cfg.dry_run else 0)
        costo_0 = self._costos()
        try:
            return self._procesar(url, row_id, costo_0)
        except Exception as exc:        # nada inesperado deja la fila colgada
            log.exception("Error inesperado en %s", url)
            return self._cerrar(row_id, url, "failed", f"error inesperado: {exc}")

    def _procesar(self, url: str, row_id: int, costo_0: dict) -> Result:
        slug, _ = extract_slug(url)
        # 1) ficha WooCommerce
        try:
            product = self.woo.get_product_by_slug(slug)
        except WooError as exc:
            return self._cerrar(row_id, url, "failed", f"WooCommerce: {exc}")
        if product.get("status") != "publish":
            return self._cerrar(row_id, url, "skipped",
                                f"producto status='{product.get('status')}'")
        nombre = product.get("name", "")
        desc_orig = product.get("description", "") or ""
        sc_orig = product.get("short_description", "") or ""
        categorias = tuple(c.get("name", "") for c in (product.get("categories") or [])
                           if c.get("name"))
        marca, atributos = _brand_y_atributos(product)

        # 2) H1 por plantilla (sin LLM)
        h1, h1_aviso = h1_plantilla(nombre, marca)
        texto_producto = " ".join([nombre, *categorias, marca, *atributos]).strip()

        # 3) keywords de GSC + volumen
        permalink = product.get("permalink") or url
        try:
            kw_rows = self._gsc_de(url) or (self._gsc_de(permalink) if permalink != url else [])
        except Exception as exc:
            return self._cerrar(row_id, url, "failed", f"GSC: {exc}")
        kw_rows = self._con_volumen(kw_rows)

        hermanas = self._keywords_ya_usadas(product)
        asignadas = self.db.keywords_asignadas(excepto_url=url)
        elegir = dict(descripcion=desc_orig, texto_producto=texto_producto,
                      h1_hermanas=hermanas, categorias=categorias, asignadas=asignadas,
                      min_volume=self.cfg.dfs_min_volume, n=reglas.KW_OBJETIVO,
                      texto_especifico=" ".join([nombre, marca, *atributos]),
                      nombre=nombre, marca=marca)
        sel = elegir_keywords(kw_rows, **elegir)

        # 4) si faltan: el mismo producto en competidores mejor posicionados
        competidores: list[dict] = []
        if sel["faltan"] and self.competidores is not None:
            competidores, extra = self._de_competidores(h1, marca, desc_orig, texto_producto)
            if extra:
                sel = elegir_keywords(list(kw_rows) + extra, **elegir)
        objetivos = sel["elegidas"]
        motivo_sel = self._motivo_seleccion(sel, competidores)

        comunes = dict(original_h1=nombre, original_description=desc_orig,
                       gsc_keywords=kw_rows[:10], selection_reason=motivo_sel)

        # 5) sin keywords que agregar: solo el H1 de plantilla
        if len(objetivos) < reglas.KW_MIN:
            edited = {"h1": h1, "description": desc_orig, "keywords": []}
            aprobado, vres, intentos = bool(h1), {"aprobado": bool(h1), "issues": [],
                                                  "razon": "sin keywords: solo H1"}, 0
            if h1 == nombre:
                return self._cerrar(row_id, url, "skipped",
                                    "sin keywords con volumen que falten y el H1 ya "
                                    "cumple la plantilla", **comunes)
        else:
            context = {"current_short_description": sc_orig, "categories": categorias,
                       "brand": marca, "attributes": atributos}
            try:
                edited = self.editor.edit(url=url, h1=h1, current_description=desc_orig,
                                          keywords=objetivos, **context)
                val = self.validator.pass_or_rework(
                    url=url, original_desc=desc_orig, edited=edited, keywords=objetivos,
                    editor=self.editor, context=context)
            except LLMError as exc:
                return self._cerrar(row_id, url, "failed", f"LLM: {exc}", **comunes)
            aprobado, vres, intentos = val["aprobado"], val["validacion"], val["intentos"]
            edited = val["edited"]

        # 6) aplicar (solo con --write y aprobación)
        aplicado, wc_resp = False, {}
        if self.cfg.dry_run:
            wc_resp = {"dry_run": True, "apply_h1": h1,
                       "apply_desc_len": len(edited.get("description", ""))}
        elif aprobado:
            try:
                wc_resp = self.woo.update_product(
                    product["id"], name=h1, description=edited.get("description", ""),
                    allowed=True)
                aplicado = True
            except WooError as exc:
                self.db.guardar_objetivos(url, objetivos, aplicada=False)
                return self._cerrar(row_id, url, "failed", f"escritura WooCommerce: {exc}",
                                    validation_result=vres, **comunes)

        # 7) traza + keywords objetivo con su línea base
        self.db.guardar_objetivos(url, objetivos, aplicada=aplicado)
        costo = self._costos()
        status = "processed" if aprobado else "rejected"
        if not aprobado:
            issues = "; ".join((vres.get("issues") or [])[:3])
            reason = f"rechazada por el validador: {issues or vres.get('razon', 'sin motivo')}"
        elif not objetivos:
            reason = "solo H1 de plantilla (sin keywords con volumen que falten)"
        else:
            reason = "dry_run (sin tocar WooCommerce)" if self.cfg.dry_run else "escrita"
        llamadas = costo.get("llamadas", 0) - costo_0.get("llamadas", 0)
        self.db.record(
            row_id, status=status, reason=reason, applied=1 if aplicado else 0,
            edited_at=datetime.now(timezone.utc) if aplicado else None,
            llm_cost=(f"{costo.get('usd', 0) - costo_0.get('usd', 0):.6f}"
                      if llamadas else None),
            llm_tokens_in=(costo.get("tokens_in", 0) - costo_0.get("tokens_in", 0)) or None,
            llm_tokens_out=(costo.get("tokens_out", 0) - costo_0.get("tokens_out", 0)) or None,
            dfs_cost=f"{costo['dfs_usd'] - costo_0['dfs_usd']:.6f}",
            edited_h1=h1, edited_description=edited.get("description", ""),
            selected_keywords=objetivos, validation_result=vres,
            validation_attempts=intentos, **comunes)
        return Result(url=url, status=status, reason=reason, keywords=kw_rows,
                      selected=objetivos, edited_h1=h1,
                      edited_description=edited.get("description", ""),
                      aprobado=aprobado, aplicado=aplicado, wc_response=wc_resp,
                      h1_aviso=h1_aviso, competidores=competidores)

    def _de_competidores(self, h1: str, marca: str, desc: str,
                         texto_producto: str) -> tuple[list[dict], list[dict]]:
        """(competidores leídos, candidatas con volumen) para el mismo producto."""
        from .competidores import candidatas_de_competidores
        consulta = h1.replace(" by ", " ") if marca else h1
        try:
            paginas = self.competidores.buscar(consulta)
        except Exception as exc:
            log.warning("Competidores no disponibles (%s)", exc)
            return [], []
        if not paginas:
            return [], []
        ajenas = [p.get("domain", "").split(".")[0] for p in paginas]
        cands = candidatas_de_competidores(paginas, descripcion_propia=desc,
                                           texto_producto=texto_producto,
                                           marcas_ajenas=ajenas)[:30]
        resumen = [{"url": p.get("url"), "rank": p.get("rank")} for p in paginas]
        return resumen, self._con_volumen(cands)

    @staticmethod
    def _motivo_seleccion(sel: dict, competidores: list[dict]) -> str:
        partes = [f"{e['keyword']} ({e.get('origen', 'gsc')}, vol {e.get('volume') or 's/d'})"
                  for e in sel["elegidas"]]
        texto = "elegidas: " + (", ".join(partes) or "ninguna")
        if competidores:
            texto += " | competidores: " + ", ".join(c["url"] for c in competidores)
        if sel["descartadas"]:
            texto += " | descartadas: " + "; ".join(
                f"{d['keyword']} ({d['motivo']})" for d in sel["descartadas"][:8])
        return texto

    def _cerrar(self, row_id: int, url: str, status: str, reason: str, **campos) -> Result:
        if status == "failed":
            log.error("FALLO %s: %s", url, reason)
        self.db.record(row_id, status=status, reason=reason, **campos)
        return Result(url=url, status=status, reason=reason,
                      aprobado=status != "rejected")
