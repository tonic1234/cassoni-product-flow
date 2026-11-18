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

from .checklist import strip_html
from .config import Config
from .db import DB
from .editor import Editor
from .extract import extract_slug, ExtractionError
from .gsc import GSCClient
from .h1 import nombre_para_woo, h1_plantilla, h1_respaldo, modelo_de, tipo_ee_uu
from .keywords import clave_variante, elegir_keywords
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


class _FalloGSC(Exception):
    pass


class Pipeline:
    def __init__(self, config: Config, *, db: Optional[DB] = None,
                 woo: Optional[WooCommerce] = None, gsc=_DEFECTO,
                 volumenes=_DEFECTO, competidores=_DEFECTO, investigacion=_DEFECTO,
                 intencion=_DEFECTO,
                 editor: Optional[Editor] = None, llm: Optional[LLMClient] = None,
                 redactor=None,
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
        # investigación de keywords (DataForSEO Labs): la fuente de keywords NUEVAS
        self.investigacion = (getattr(volumenes, "fetcher", None)
                              if investigacion is _DEFECTO else investigacion)
        # qué muestra Google para cada keyword (DataForSEO SERP): cualquier objeto
        # con serp_organico(keyword) -> [{title, url, domain}]
        if intencion is _DEFECTO:
            intencion = self.investigacion if config.dfs_intencion else None
        self.intencion = intencion if hasattr(intencion, "serp_organico") else None
        self._serp_cache: dict[str, list[dict]] = {}
        self.llm = llm or LLMClient(config)
        self.editor = editor or Editor(config, self.llm)
        from .redactor import Redactor
        from .criterio_seo import Referencia, SelectorSEO
        self.referencia = (Referencia.cargar(config.referencia_seo)
                           if config.modo_keywords in ("seo", "reglas") else None)
        self.selector_seo = SelectorSEO(self.llm, config.llm_editor_model, self.referencia)
        self.redactor = redactor or Redactor(config, self.llm, referencia=self.referencia)
        from .validator import Validator
        self.validator = Validator(config, self.llm)
        self._cat_names_cache: dict[int, tuple] = {}
        self._gsc_cache: dict[str, list[dict]] = {}
        self._woo_cache: dict[str, dict] = {}
        self._comp_cache: dict[str, tuple[list[dict], list[dict]]] = {}
        self._ideas_cache: dict[str, list[dict]] = {}

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
        """Arma el lote de DataForSEO en DOS pedidos de volumen para todo el día
        (cuesta lo mismo 10 keywords que 1.000):
          1) las keywords de GSC de todas las fichas;
          2) las candidatas de competidores de las fichas a las que GSC no les
             alcanzó (antes se pedían ficha por ficha, a US$ 0,09 cada una)."""
        todas: list[str] = []
        for u in urls:
            try:
                filas = self._gsc_de(u)
            except Exception as exc:
                log.warning("GSC falló en la precarga de %s (%s)", u, exc)
                continue
            ordenadas = sorted(filas, key=lambda f: f.get("impressions") or 0, reverse=True)
            todas.extend(f.get("keyword", "") for f in ordenadas[:MAX_KW_A_DFS_POR_FICHA])
            if self.cfg.modo_keywords in ("seo", "reglas"):
                try:
                    prod = self._producto(extract_slug(u)[0])
                    todas.extend(self._genericas(prod))
                    if self.cfg.modo_keywords == "reglas":
                        from .reglas_seo import nombre_de_busqueda
                        todas.append(nombre_de_busqueda(prod.get("name", "")))
                except Exception as exc:
                    log.warning("Genéricas no disponibles en la precarga de %s (%s)", u, exc)
            elif self.investigacion is not None:
                # las semillas de investigación también son candidatas: su volumen
                # va en el mismo pedido del lote (13-nov: ficha por ficha costaba
                # US$ 0,09 cada una y agotaba el presupuesto)
                try:
                    todas.extend(self._semillas(self._producto(extract_slug(u)[0])))
                except Exception as exc:
                    log.warning("Semillas no disponibles en la precarga de %s (%s)", u, exc)
        if self.volumenes is not None and todas:
            self.volumenes.obtener(todas)
        if self.competidores is None or self.volumenes is None:
            return
        de_competidores: list[str] = []
        for u in urls:
            try:
                ctx = self._contexto(u, self._producto(extract_slug(u)[0]))
            except Exception as exc:
                log.warning("Precarga de competidores salteada en %s (%s)", u, exc)
                continue
            if ctx["sel"]["faltan"] or self.cfg.dfs_competidores == "siempre":
                _, cands = self._paginas_competidores(ctx)
                de_competidores.extend(c["keyword"] for c in cands if c.get("volume") is None)
        if de_competidores:
            self.volumenes.obtener(de_competidores)

    def _producto(self, slug: str) -> dict:
        if slug not in self._woo_cache:
            self._woo_cache[slug] = self.woo.get_product_by_slug(slug)
        return self._woo_cache[slug]

    def _contexto(self, url: str, product: dict) -> dict:
        """Todo lo que se decide sin LLM: H1, keywords de GSC con volumen y la
        primera selección. Lo usan la precarga y el ciclo por ficha."""
        nombre = product.get("name", "")
        desc_orig = product.get("description", "") or ""
        categorias = tuple(c.get("name", "") for c in (product.get("categories") or [])
                           if c.get("name"))
        marca, atributos = _brand_y_atributos(product)
        ruta = self._ruta(product)
        tipo = tipo_ee_uu(nombre, [r["slug"] for r in ruta], atributos)
        if self.cfg.modo_descripcion == "reescritura":
            # el H1 final lo propone el redactor; este es el de respaldo (sin LLM)
            h1, h1_aviso = h1_respaldo(nombre, marca, tipo), ""
        else:
            h1, h1_aviso = h1_plantilla(nombre, marca)
        texto_producto = " ".join([nombre, *categorias, marca, *atributos]).strip()
        permalink = product.get("permalink") or url
        try:
            kw_rows = self._gsc_de(url) or (self._gsc_de(permalink) if permalink != url else [])
        except Exception as exc:
            raise _FalloGSC(str(exc)) from exc
        kw_rows = self._con_volumen(kw_rows)
        ideas = self._ideas(url, product, tipo)
        from .investigacion import materiales_del_texto
        materiales = materiales_del_texto(strip_html(desc_orig))
        elegir = dict(descripcion=desc_orig, texto_producto=texto_producto,
                      h1_hermanas=self._keywords_ya_usadas(product), categorias=categorias,
                      asignadas=self.db.keywords_asignadas(excepto_url=url),
                      min_volume=self.cfg.dfs_min_volume, n=reglas.KW_OBJETIVO,
                      texto_especifico=" ".join([nombre, marca, *atributos, *materiales]),
                      nombre=nombre, marca=marca,
                      texto_ficha=" ".join([nombre, marca, *atributos, strip_html(desc_orig)]),
                      reescritura=self.cfg.modo_descripcion == "reescritura")
        return dict(nombre=nombre, desc_orig=desc_orig, categorias=categorias,
                    marca=marca, atributos=atributos, h1=h1, h1_aviso=h1_aviso,
                    ruta=ruta, tipo=tipo,
                    texto_producto=texto_producto, kw_rows=kw_rows + ideas, elegir=elegir,
                    sel=elegir_keywords(kw_rows + ideas, **elegir))

    def _ruta(self, product: dict) -> list[dict]:
        """Ruta de la categoría principal ('furniture > dining-room > fixed-tables').
        Si Woo no la da, queda la hoja sola."""
        cats = product.get("categories") or []
        if not cats:
            return []
        fn = getattr(self.woo, "ruta_categoria", None)
        if callable(fn) and cats[0].get("id"):
            try:
                return fn(cats[0]["id"])
            except Exception as exc:
                log.warning("Ruta de categoría no disponible (%s)", exc)
        return [{"id": c.get("id"), "name": c.get("name", ""), "slug": c.get("slug", "")}
                for c in cats[:1]]

    def _serp(self, keyword: str) -> list[dict]:
        if keyword not in self._serp_cache:
            try:
                self._serp_cache[keyword] = self.intencion.serp_organico(keyword) or []
            except Exception as exc:
                log.warning("SERP no disponible para %r (%s)", keyword, exc)
                self._serp_cache[keyword] = []
        return self._serp_cache[keyword]

    def _filtrar_por_intencion(self, sel: dict, candidatas: list[dict], elegir: dict,
                               ctx: dict, rondas: int = 3) -> dict:
        """Saca de las elegidas las que una ficha no puede ganar (Google muestra
        colecciones, otro tema u otro producto) y vuelve a elegir sin ellas."""
        if self.intencion is None:
            return sel
        from .intencion import veredicto
        from .keywords import tipo_de_producto
        tipos = tipo_de_producto(ctx["nombre"], ctx["categorias"]) | set(ctx["tipo"].split())
        # la ruta de categorías también es de la ficha: 'game' en una mesa de
        # ping-pong que cuelga de 'Game Tables' (prueba ciega 11-nov)
        texto = " ".join([elegir.get("texto_ficha") or ctx["texto_producto"],
                          *(r.get("name", "") for r in ctx.get("ruta") or [])])
        fuera: dict[str, str] = {}
        originales: dict[str, str] = {}
        for _ in range(rondas):
            nuevas = {}
            for e in sel["elegidas"]:
                serp = self._serp(e["keyword"])
                # sin datos de Google (presupuesto agotado, API caída) no se elige a
                # ciegas: mejor ninguna keyword que una de categoría (prueba 11-nov)
                v = (veredicto(e["keyword"], serp, tipos, texto) if serp else
                     {"ok": False, "motivo": "sin datos de Google para comprobarla"})
                if not v["ok"]:
                    nuevas[clave_variante(e["keyword"])] = v["motivo"]
                    originales.setdefault(clave_variante(e["keyword"]), e["keyword"])
            if not nuevas:
                break
            fuera.update(nuevas)
            restantes = [c for c in candidatas
                         if clave_variante(c.get("keyword") or "") not in fuera]
            sel = elegir_keywords(restantes, **elegir)
        else:
            # se acabaron las rondas: las que todavía no pasan, afuera sin reemplazo
            for e in list(sel["elegidas"]):
                serp = self._serp(e["keyword"])
                v = (veredicto(e["keyword"], serp, tipos, texto) if serp else
                     {"ok": False, "motivo": "sin datos de Google para comprobarla"})
                if not v["ok"]:
                    fuera[clave_variante(e["keyword"])] = v["motivo"]
                    originales.setdefault(clave_variante(e["keyword"]), e["keyword"])
                    sel["elegidas"].remove(e)
        sel["descartadas"] = [{"keyword": originales.get(k, k),
                               "motivo": f"{m} (intención en Google)"}
                              for k, m in fuera.items()] + list(sel["descartadas"])
        return sel

    def _semillas(self, product: dict) -> list[str]:
        from .investigacion import semillas
        nombre = product.get("name", "")
        marca, atributos = _brand_y_atributos(product)
        categorias = tuple(c.get("name", "") for c in (product.get("categories") or [])
                           if c.get("name"))
        tipo = tipo_ee_uu(nombre, [r["slug"] for r in self._ruta(product)], atributos)
        return semillas(nombre, marca, categorias, atributos, tipo=tipo,
                        descripcion=strip_html(product.get("description", "") or ""))

    def _genericas(self, product: dict) -> list[str]:
        from .criterio_seo import genericas
        nombre = product.get("name", "")
        marca, atributos = _brand_y_atributos(product)
        tipo = tipo_ee_uu(nombre, [r["slug"] for r in self._ruta(product)], atributos)
        return genericas(nombre, marca, tipo, atributos, product.get("description", "") or "")

    def _seleccion_reglas(self, url: str, product: dict, ctx: dict) -> dict:
        from .criterio_seo import candidatas_gsc, con_volumen
        from .investigacion import materiales_del_texto
        from .reglas_seo import (elegir_keywords, h1_por_datos, nombre_de_busqueda,
                                 rasgos_con_volumen)
        gen = self._genericas(product)
        nombre_q = nombre_de_busqueda(ctx["nombre"])
        tipo = ctx["tipo"]
        nucleo = tipo[len("outdoor "):] if tipo.startswith("outdoor ") else tipo
        # el rasgo sale primero de nombre + atributos; la descripción, solo si no hay
        mats = (materiales_del_texto(" ".join([ctx["nombre"], *ctx["atributos"]]))
                or materiales_del_texto(strip_html(ctx["desc_orig"])))
        consultas = gen + [nombre_q] + [f"{m} {nucleo}" for m in mats]
        vol = self.volumenes.obtener(consultas) if self.volumenes is not None else {}
        rasgos = rasgos_con_volumen(mats, nucleo, vol)
        from .reglas_seo import (genericas_opcionales, keywords_de_opciones,
                                 marca_ajena_en, opciones_de_material)
        # 18-nov: si la parte principal viene en opciones («wood or marble»), el H1 lleva
        # la más buscada y la descripción cubre todas; una marca ajena en el nombre
        # («Steinway») no cuenta como «el nombre ya se busca»
        opciones = opciones_de_material(strip_html(ctx["desc_orig"]), mats)
        ajena = marca_ajena_en(ctx["nombre"], ctx["marca"])
        r = h1_por_datos(ctx["nombre"], ctx["marca"], tipo,
                         (vol.get(nombre_q) or {}).get("volume"), rasgos,
                         umbral=self.cfg.h1_umbral_nombre, opciones=opciones,
                         marca_ajena=ajena)
        ctx["h1_regla"] = r["regla"]
        # H1 fijo: el nombre solo, sin tipo o la opción más buscada. Con rasgo libre: el
        # redactor elige entre los rasgos con su volumen el que tienen TODAS las versiones
        ctx["h1_fijo"] = r["h1"] if r["fijo"] else ""
        ctx["h1_rasgos"] = sorted(((m, v) for m, v in rasgos if v), key=lambda x: -x[1])
        kw_opciones = keywords_de_opciones(opciones, nucleo, vol) if len(opciones) >= 2 else []
        ctx["opciones"] = opciones if len(opciones) >= 2 else []
        # con opciones, las genéricas son las de cada opción (van como objetivo)
        ctx["genericas_opcionales"] = [] if ctx["opciones"] else genericas_opcionales(mats, nucleo, vol)
        cands = candidatas_gsc(ctx["kw_rows"], ctx["nombre"], ctx["marca"]) + con_volumen(gen, vol)
        texto = " ".join([ctx["nombre"], ctx["marca"], *ctx["atributos"],
                          *ctx["categorias"], strip_html(ctx["desc_orig"])])
        sel = elegir_keywords(cands, nombre=ctx["nombre"], marca=ctx["marca"], tipo=tipo,
                              h1=r["h1"], rasgo=r["rasgo"], texto_ficha=texto,
                              opciones=kw_opciones, marca_ajena=ajena)
        for e in sel["elegidas"]:
            e["volume"], e["impressions"] = e.get("volumen"), e.get("impresiones")
        sel["faltan"] = 0
        return sel

    def _seleccion_seo(self, url: str, product: dict, ctx: dict) -> dict:
        from .criterio_seo import candidatas_gsc, con_volumen
        from .investigacion import materiales_del_texto
        gen = self._genericas(product)
        vol = self.volumenes.obtener(gen) if (self.volumenes is not None and gen) else {}
        cands = candidatas_gsc(ctx["kw_rows"], ctx["nombre"], ctx["marca"]) + con_volumen(gen, vol)
        ficha = {"nombre": ctx["nombre"], "marca": ctx["marca"], "tipo": ctx["tipo"],
                 "materiales": materiales_del_texto(" ".join(
                     [ctx["nombre"], *ctx["atributos"], strip_html(ctx["desc_orig"])])),
                 "candidatas": cands}
        sel = self.selector_seo.elegir(ficha, excluir_url=url)
        sel["faltan"] = 0
        return sel

    def _ideas(self, url: str, product: dict, tipo: str = "") -> list[dict]:
        """Keywords que la ficha todavía no atrae (una consulta por ficha, en caché):
        las ideas de DataForSEO que nombran el tipo, más las semillas mismas con su
        volumen ('brass chandelier' es la keyword, no solo el punto de partida)."""
        if self.investigacion is None:
            return []
        if url not in self._ideas_cache:
            from .investigacion import nucleos
            sem = self._semillas(product)
            try:
                ideas = (self.investigacion.ideas_de_keywords(
                    sem, contiene=nucleos(tipo) or None) if sem else [])
            except Exception as exc:
                log.warning("Investigación de keywords no disponible (%s)", exc)
                ideas = []
            ya = {(i.get("keyword") or "").lower() for i in ideas}
            propias = [{"keyword": k, "origen": "investigacion"} for k in sem if k not in ya]
            propias = [r for r in self._con_volumen(propias) if r.get("volume")]
            for r in propias:
                r["origen"] = "investigacion"
            from .investigacion import motivo_idea
            for r in ideas:
                m = motivo_idea(r.get("keyword") or "", tipo)
                if m:
                    r["descartar"] = m
            self._ideas_cache[url] = ideas + propias
        return self._ideas_cache[url]

    def _con_volumen(self, filas: list[dict]) -> list[dict]:
        if self.volumenes is None or not filas:
            return filas
        try:
            return self.volumenes.anotar(filas)
        except Exception as exc:
            log.warning("Volumen degradado (%s): sigo con GSC", exc)
            return filas

    def _costos(self) -> dict:  # noqa: D401
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
            product = self._producto(slug)
        except WooError as exc:
            return self._cerrar(row_id, url, "failed", f"WooCommerce: {exc}")
        if product.get("status") != "publish":
            return self._cerrar(row_id, url, "skipped",
                                f"producto status='{product.get('status')}'")
        sc_orig = product.get("short_description", "") or ""
        # 2-3) H1 por plantilla + keywords de GSC con volumen (sin LLM)
        try:
            ctx = self._contexto(url, product)
        except _FalloGSC as exc:
            return self._cerrar(row_id, url, "failed", f"GSC: {exc}")
        nombre, desc_orig, categorias = ctx["nombre"], ctx["desc_orig"], ctx["categorias"]
        marca, atributos, h1, h1_aviso = ctx["marca"], ctx["atributos"], ctx["h1"], ctx["h1_aviso"]
        kw_rows, elegir, sel = ctx["kw_rows"], ctx["elegir"], ctx["sel"]

        # 4) si faltan: el mismo producto en competidores mejor posicionados
        competidores: list[dict] = []
        candidatas = list(kw_rows)
        if self.cfg.modo_keywords == "reglas":
            # reglas del SEO en código (Alex, 17-nov): H1 por volumen, keywords de
            # Search Console + marca y tipo; el modelo solo redacta
            sel = self._seleccion_reglas(url, product, ctx)
        elif self.cfg.modo_keywords == "seo":
            # criterio del SEO (documento del 6-nov), con sus fichas como ejemplo
            try:
                sel = self._seleccion_seo(url, product, ctx)
            except LLMError as exc:
                return self._cerrar(row_id, url, "failed", f"LLM (selección): {exc}")
        elif (sel["faltan"] or self.cfg.dfs_competidores == "siempre") and self.competidores is not None:
            competidores, cands = self._paginas_competidores(ctx)
            extra = self._con_volumen(cands)
            if extra:
                candidatas += extra
                sel = elegir_keywords(candidatas, **elegir)
        # 4b) que una ficha pueda ganarlas: qué muestra Google (devolución SEO 6-nov)
        if self.cfg.modo_keywords == "filtros":
            sel = self._filtrar_por_intencion(sel, candidatas, elegir, ctx)
        objetivos = sel["elegidas"]
        motivo_sel = self._motivo_seleccion(sel, competidores)

        comunes = dict(original_h1=nombre, original_description=desc_orig,
                       gsc_keywords=kw_rows[:10], selection_reason=motivo_sel)

        # 5') modo reescritura: H1 + descripción con la plantilla del SEO, haya o no
        # keywords (el SEO reescribe todas las fichas)
        if self.cfg.modo_descripcion == "reescritura":
            ficha = self._ficha_para_redactor(url, product, ctx, sc_orig)
            try:
                val = self.validator.redactar_y_validar(ficha=ficha, keywords=objetivos,
                                                        redactor=self.redactor)
            except LLMError as exc:
                return self._cerrar(row_id, url, "failed", f"LLM: {exc}", **comunes)
            aprobado, vres, intentos = val["aprobado"], val["validacion"], val["intentos"]
            edited = val["edited"]
            h1 = edited.get("h1") or h1
            # las que el redactor no pudo meter natural no son objetivo de la ficha
            omitidas = {(o.get("keyword") or "").lower() for o in edited.get("omitidas") or []}
            objetivos = [o for o in objetivos if o["keyword"].lower() not in omitidas]
            if ficha.get("genericas_opcionales") and aprobado:
                from .reglas_seo import generica_usada
                g = generica_usada(strip_html(edited.get("description") or ""), h1,
                                   ficha["genericas_opcionales"])
                if g and g[2] and g[0] not in {o["keyword"].lower() for o in objetivos}:
                    objetivos.append({"keyword": g[0], "origen": "generica", "volume": g[1],
                                      "volumen": g[1], "por_que": "el material del H1 con el tipo"})
            vres = dict(vres, omitidas=edited.get("omitidas") or [], mismo_nombre=ficha["mismo_nombre"], tipo=ficha["tipo"],
                        url_categoria=ficha["url_categoria"],
                        h1_respaldo_usado=bool(edited.get("h1_respaldo_usado")))
        # 5) sin keywords que agregar: solo el H1 de plantilla
        elif len(objetivos) < reglas.KW_MIN:
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
                       "apply_name": nombre_para_woo(h1, marca),
                       "apply_desc_len": len(edited.get("description", ""))}
        elif aprobado:
            try:
                wc_resp = self.woo.update_product(
                    # la tienda agrega 'by {Marca}' (con logo) al H1: el name va sin marca
                    product["id"], name=nombre_para_woo(h1, marca),
                    description=edited.get("description", ""),
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
        elif self.cfg.modo_descripcion == "reescritura":
            reason = ("dry_run (sin tocar WooCommerce)" if self.cfg.dry_run else "escrita") + \
                ("" if objetivos else " · sin keywords objetivo que una ficha pueda ganar")
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

    def _ficha_para_redactor(self, url: str, product: dict, ctx: dict, corta: str) -> dict:
        from .redactor import medidas_ee_uu
        ruta = ctx["ruta"]
        base = (self.cfg.wc_base or "https://cassoni.com").rstrip("/")
        base = re.sub(r"/wp-json.*$", "", base)
        url_cat = (f"{base}/product-category/{'/'.join(r['slug'] for r in ruta)}/"
                   if ruta and all(r.get("slug") for r in ruta) else "")
        mismo = []
        fn = getattr(self.woo, "mismo_nombre", None)
        if callable(fn):
            try:
                mismo = fn(html.unescape(ctx["nombre"]).strip(), product.get("id") or 0)
            except Exception as exc:
                log.warning("No se pudo buscar fichas con el mismo nombre (%s)", exc)
        return {"url": url, "nombre": html.unescape(ctx["nombre"]), "marca": ctx["marca"],
                "modelo": modelo_de(html.unescape(ctx["nombre"]), ctx["marca"]),
                "tipo": ctx["tipo"], "categorias": [html.unescape(r["name"]) for r in ruta],
                "url_categoria": url_cat, "atributos": list(ctx["atributos"]),
                "medidas": medidas_ee_uu(ctx["atributos"]), "descripcion": ctx["desc_orig"],
                "corta": corta, "mismo_nombre": mismo, "h1_respaldo": ctx["h1"],
                "h1_fijo": ctx.get("h1_fijo", ""), "h1_regla": ctx.get("h1_regla", ""),
                "h1_rasgos": ctx.get("h1_rasgos", []),
                "genericas_opcionales": ctx.get("genericas_opcionales", []),
                "opciones": ctx.get("opciones", []),
                "keywords_obligatorias": self.cfg.modo_keywords == "reglas"}

    def _paginas_competidores(self, ctx: dict) -> tuple[list[dict], list[dict]]:
        """(competidores leídos, candidatas SIN volumen) para el mismo producto.
        Con caché por consulta: la precarga y la ficha no pagan la búsqueda dos
        veces."""
        from .competidores import candidatas_de_competidores
        consulta = ctx["h1"].replace(" by ", " ") if ctx["marca"] else ctx["h1"]
        if consulta in self._comp_cache:
            return self._comp_cache[consulta]
        # 1) lo que los competidores RANKEAN (DataForSEO): el dato más fuerte
        try:
            resumen, rankeadas = self.competidores.rankeadas(consulta)
        except Exception as exc:
            log.warning("Keywords de competidores no disponibles (%s)", exc)
            resumen, rankeadas = [], []
        if rankeadas:
            ajenas = {w for r in resumen for w in (r.get("domain") or "").split(".")[:1]}
            cands = [c for c in rankeadas
                     if not any(a and a in c["keyword"].replace(" ", "") for a in ajenas)]
            self._comp_cache[consulta] = (resumen, cands[:60])
            return resumen, cands[:60]
        # 2) respaldo: leer sus páginas y tomar frases que se repiten
        try:
            paginas = self.competidores.buscar(consulta)
        except Exception as exc:
            log.warning("Competidores no disponibles (%s)", exc)
            paginas = []
        ajenas = [p.get("domain", "").split(".")[0] for p in paginas]
        cands = candidatas_de_competidores(paginas, descripcion_propia=ctx["desc_orig"],
                                           texto_producto=ctx["texto_producto"],
                                           marcas_ajenas=ajenas)[:30] if paginas else []
        resumen = [{"url": p.get("url"), "rank": p.get("rank")} for p in paginas]
        self._comp_cache[consulta] = (resumen, cands)
        return resumen, cands

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
