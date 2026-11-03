# -*- coding: utf-8 -*-
"""Test end-to-end del orquestador (flujo v2, equipo SEO 3-nov-2026).

    H1 = "{Nombre} by {Marca}" (plantilla, sin LLM) en el campo name
    3 keywords: GSC + volumen DFS, solo las que NO están en la descripción
    si faltan: el mismo producto en competidores mejor posicionados
    anti-canibalización: hermanas, categorías y keywords ya escritas en otras fichas
    idempotencia: una ficha escrita no se vuelve a editar salvo --forzar

Todo con fakes: sin red, sin LLM real.
"""
import re

from cassoni.config import Config
from cassoni.db import DB
from cassoni.orchestrator import Pipeline

URL = "https://x.com/product/cas-cprn-pedro-sofa-01/"

# descripción ORIGINAL de >150 palabras: el editor fake solo AGREGA una oración,
# así la conservación queda en 100% y el largo dentro de 150-300
_FRASES = [
    "Elegante sofá de cuero negro.",
    "Diseñado en líneas sobrias, este mueble combina estructura de madera maciza "
    "con tapicería de cuero, y cada costura queda rematada a mano.",
    "El respaldo ofrece un descanso profundo, los apoyabrazos redondeados completan "
    "una silueta equilibrada y la pieza aporta presencia sin recargar el ambiente.",
    "Se fabrica bajo pedido, puede personalizarse en distintos acabados y la entrega "
    "incluye montaje en el domicilio y garantía de cinco años.",
    "El cuero madura con los años ganando carácter, mientras la madera de roble "
    "sostiene el conjunto con firmeza y el mantenimiento se reduce a la limpieza habitual.",
    "Las medidas y las fichas técnicas completas figuran al pie de la página, junto "
    "con las opciones de color disponibles de fábrica y los tiempos estimados de entrega.",
    "Cada unidad pasa por un control de calidad previo al despacho, se embala con "
    "protección en todas sus aristas y el transportista coordina la recepción con el cliente.",
]
DESC_ORIG = ("<h2>Diseño</h2><p>" + " ".join(_FRASES[:4]) + "</p>"
             "<h2>Materiales</h2><p>" + " ".join(_FRASES[4:]) + "</p>")


class FakeWoo:
    def __init__(self):
        self.product = {
            "id": 120563, "name": "Pedro Sofá", "slug": "cas-cprn-pedro-sofa-01",
            "status": "publish", "type": "simple",
            "permalink": URL,
            "short_description": "Elegante sofá de cuero negro.",
            "description": DESC_ORIG,
            "categories": [{"id": 5, "name": "Sofas"}],
            "brands": [{"id": 1, "name": "Cassoni"}],
            "attributes": [{"name": "Material", "options": ["Cuero"]},
                           {"name": "Estilo", "options": ["Chesterfield"]},
                           {"name": "Acabado", "options": ["Tapizado"]},
                           {"name": "Configuración", "options": ["Modular"]}],
        }
        self.writes = []
        self.sibling_calls = []
        self.falla_escritura = None

    def get_product_by_slug(self, slug):
        assert slug == "cas-cprn-pedro-sofa-01"
        return self.product

    def products_by_category(self, category_id, per_page=100):
        self.sibling_calls.append(category_id)
        return [{"id": 120563, "name": "Pedro Sofá", "slug": "p1"},
                {"id": 999, "name": "sofá belinda", "slug": "p2"}]

    def update_product(self, product_id, *, name, description, allowed=True):
        if self.falla_escritura:
            raise self.falla_escritura
        self.writes.append((name, description))
        return {"id": product_id, "name": name}


def _q(kw, impr=100, pos=8.0, clics=2):
    return {"keyword": kw, "clicks": clics, "impressions": impr, "position": pos,
            "ctr": clics / impr if impr else 0}


class FakeGSC:
    def __init__(self, filas=None):
        self.filas = filas if filas is not None else [
            _q("sofá de cuero", 900),            # ya está en la descripción
            _q("sofá chesterfield", 400),
            _q("modular pedro", 300),
            _q("cuero capitoné", 200),
            _q("mesa de comedor", 500),          # no es de este producto
        ]
        self.llamadas = 0

    def top_keywords_for_url(self, url, **kw):
        self.llamadas += 1
        return list(self.filas)


class FakeVolumenes:
    def __init__(self, vol):
        self.vol = vol
        self.pedidos = []
        self.costo_usd = 0.0

    def obtener(self, kws):
        kws = list(kws)
        self.pedidos.append(kws)
        self.costo_usd += 0.075
        return {k: {"volume": self.vol.get(k)} for k in kws}

    def anotar(self, filas):
        return [{**f, "volume": self.vol.get(f["keyword"])} for f in filas]


class FakeCompetidores:
    def __init__(self, paginas):
        self.paginas = paginas
        self.consultas = []

    def buscar(self, consulta, n=3):
        self.consultas.append(consulta)
        return self.paginas


def _objetivo(user):
    bloque = user.split("KEYWORDS OBJETIVO")[1].split("Responde SOLO")[0]
    return re.findall(r"^- (.+?) \(volumen", bloque, flags=re.M)


class FakeLLM:
    """Editor: agrega UNA oración con todas las keywords. Validador: aprueba."""

    def __init__(self, aprueba=True):
        self.aprueba = aprueba
        self.editor_user = ""
        self.calls = 0

    def complete_json(self, system, user, **kw):
        self.calls += 1
        if "control de calidad" in system.lower():
            return {"aprobado": self.aprueba, "issues": [] if self.aprueba else ["tono"],
                    "razon": "ok" if self.aprueba else "no"}
        self.editor_user = user
        kws = _objetivo(user)
        frase = "Pensado como " + ", ".join(kws) + "."
        desc = user.split("Descripción larga actual (HTML, la que hay que editar):\n")[1]
        desc = desc.split("\n\nKEYWORDS OBJETIVO")[0]
        return {"description": desc.replace("</p>", f" {frase}</p>", 1),
                "keywords": [{"keyword": k, "why": "x"} for k in kws]}

    def consumo(self):
        return {"tokens_in": 100 * self.calls, "tokens_out": 50 * self.calls,
                "usd": 0.001 * self.calls, "llamadas": self.calls}


def _cfg(tmp_path, dry_run=True):
    c = Config(env="staging", dry_run=dry_run)
    c.db_url = f"sqlite:///{tmp_path}/e2e.db"
    c.llm_editor_model = "editor"
    c.llm_validator_model = "validator"
    return c


VOL = {"sofá chesterfield": 1900, "modular pedro": 90,
       "cuero capitoné": 40, "mesa de comedor": 5000}


def _pipeline(tmp_path, dry_run=True, gsc=None, vol=VOL, competidores=None,
              aprueba=True, forzar=False, db=None):
    cfg = _cfg(tmp_path, dry_run)
    from cassoni.editor import Editor
    llm = FakeLLM(aprueba)
    return Pipeline(cfg, db=db or DB(cfg), woo=FakeWoo(), gsc=gsc or FakeGSC(),
                    volumenes=FakeVolumenes(vol) if vol is not None else None,
                    competidores=competidores, llm=llm, editor=Editor(cfg, llm),
                    dry_run=dry_run, forzar=forzar)


# --- H1 por plantilla ---------------------------------------------------------
def test_h1_es_nombre_by_marca(tmp_path):
    pipe = _pipeline(tmp_path, dry_run=False)
    res = pipe.process(URL)
    assert res.status == "processed"
    assert res.edited_h1 == "Pedro Sofá by Cassoni"
    assert pipe.woo.writes[0][0] == "Pedro Sofá by Cassoni"     # va al campo name


def test_el_llm_no_decide_el_h1(tmp_path):
    pipe = _pipeline(tmp_path)
    pipe.process(URL)
    assert "H1 (fijo, NO se edita): Pedro Sofá by Cassoni" in pipe.llm.editor_user


# --- selección de keywords ----------------------------------------------------
def test_tres_keywords_con_volumen_que_no_estan_en_la_descripcion(tmp_path):
    pipe = _pipeline(tmp_path)
    res = pipe.process(URL)
    elegidas = [k["keyword"] for k in res.selected]
    assert len(elegidas) == 3
    assert "sofá de cuero" not in elegidas           # ya estaba en la descripción
    assert "mesa de comedor" not in elegidas         # no es de este producto
    assert elegidas[0] == "sofá chesterfield"        # la de más volumen primero


def test_sin_volumen_alcanza_con_impresiones_reales(tmp_path):
    pipe = _pipeline(tmp_path, vol={})               # DFS no informa nada
    res = pipe.process(URL)
    assert res.status == "processed"
    assert len(res.selected) == 3


def test_keyword_ya_escrita_en_otra_ficha_no_se_repite_si_hay_alternativa(tmp_path):
    pipe = _pipeline(tmp_path)
    pipe.db.guardar_objetivos("https://x.com/product/otra/",
                              [{"keyword": "sofá chesterfield"}], aplicada=True)
    pipe.gsc.filas.append(_q("sofá tapizado", 150))
    res = pipe.process(URL)
    elegidas = [k["keyword"] for k in res.selected]
    assert "sofá chesterfield" not in elegidas
    assert "sofá tapizado" in elegidas


def test_categoria_real_no_se_usa_como_keyword(tmp_path):
    gsc = FakeGSC([_q("sofas", 900), _q("sofá chesterfield", 400)])
    pipe = _pipeline(tmp_path, gsc=gsc, vol={"sofas": 9000, "sofá chesterfield": 1900})
    res = pipe.process(URL)
    assert [k["keyword"] for k in res.selected] == ["sofá chesterfield"]


def test_un_solo_pedido_de_volumen_para_todo_el_lote(tmp_path):
    pipe = _pipeline(tmp_path)
    pipe.precargar([URL])
    pipe.process(URL)
    assert len(pipe.volumenes.pedidos) == 1
    assert pipe.gsc.llamadas == 1                     # GSC también queda en caché


# --- competidores (paso ② de la pizarra) --------------------------------------
PAGINAS = [
    {"url": f"https://tienda{i}.com/p", "domain": f"tienda{i}.com", "rank": i,
     "title": "Pedro Sofa", "h1": ["Pedro Sofá Velvet Edition"],
     "h2": ["Velvet upholstery"], "texto": "A pedro sofá in velvet upholstery."}
    for i in (1, 2, 3)
]


def test_sin_gsc_busca_el_mismo_producto_en_competidores(tmp_path):
    comp = FakeCompetidores(PAGINAS)
    pipe = _pipeline(tmp_path, gsc=FakeGSC([]), competidores=comp,
                     vol={"pedro sofa": 50, "velvet upholstery": 0})
    res = pipe.process(URL)
    assert comp.consultas == ["Pedro Sofá Cassoni"]
    assert res.competidores
    assert any(k.get("origen") == "competidor" for k in res.selected)


def test_competidores_solo_si_faltan_keywords(tmp_path):
    comp = FakeCompetidores(PAGINAS)
    pipe = _pipeline(tmp_path, competidores=comp)
    pipe.process(URL)
    assert comp.consultas == []                      # GSC ya dio 3


# --- sin keywords: solo H1 ----------------------------------------------------
def test_sin_keywords_aplica_solo_el_h1(tmp_path):
    pipe = _pipeline(tmp_path, dry_run=False, gsc=FakeGSC([]), vol={})
    res = pipe.process(URL)
    assert res.status == "processed"
    assert pipe.woo.writes == [("Pedro Sofá by Cassoni", DESC_ORIG)]
    assert pipe.llm.calls == 0


def test_sin_keywords_y_h1_que_ya_cumple_se_saltea(tmp_path):
    pipe = _pipeline(tmp_path, dry_run=False, gsc=FakeGSC([]), vol={})
    pipe.woo.product["name"] = "Pedro Sofá by Cassoni"
    res = pipe.process(URL)
    assert res.status == "skipped"
    assert pipe.db.get_state(URL).status == "skipped"


# --- escritura, dry-run e idempotencia ----------------------------------------
def test_dry_run_no_escribe_y_no_cuenta_como_aplicada(tmp_path):
    pipe = _pipeline(tmp_path, dry_run=True)
    res = pipe.process(URL)
    assert res.status == "processed"
    assert res.aplicado is False
    assert pipe.woo.writes == []
    row = pipe.db.get_state(URL)
    assert row.applied == 0 and row.dry_run == 1
    assert row.original_h1 == "Pedro Sofá"


def test_write_escribe_name_y_description(tmp_path):
    pipe = _pipeline(tmp_path, dry_run=False)
    res = pipe.process(URL)
    assert res.aplicado is True
    name, desc = pipe.woo.writes[0]
    assert desc == res.edited_description
    row = pipe.db.get_state(URL)
    assert row.applied == 1 and row.edited_at is not None and row.dry_run == 0


def test_una_ficha_escrita_no_se_vuelve_a_editar(tmp_path):
    """Auditoría 3-nov: re-correr la lista editaba encima de lo editado y
    pisaba la línea base con métricas de después."""
    pipe = _pipeline(tmp_path, dry_run=False)
    pipe.process(URL)
    res = pipe.process(URL)
    assert res.status == "skipped"
    assert "ya editada" in res.reason
    assert len(pipe.woo.writes) == 1


def test_forzar_permite_rehacerla(tmp_path):
    pipe = _pipeline(tmp_path, dry_run=False)
    pipe.process(URL)
    pipe.forzar = True
    pipe.process(URL)
    assert len(pipe.woo.writes) == 2


def test_dry_run_se_puede_repetir(tmp_path):
    pipe = _pipeline(tmp_path, dry_run=True)
    pipe.process(URL)
    assert pipe.process(URL).status == "processed"


# --- estados y fallos ---------------------------------------------------------
def test_rechazada_no_escribe_y_queda_rejected(tmp_path):
    pipe = _pipeline(tmp_path, dry_run=False, aprueba=False)
    res = pipe.process(URL)
    assert res.status == "rejected"
    assert pipe.woo.writes == []
    assert pipe.db.get_state(URL).status == "rejected"


def test_fallo_al_escribir_queda_failed_con_motivo(tmp_path):
    """Antes quedaba 'rejected' (como si lo hubiera rechazado el validador) y el
    motivo se perdía: la tabla no tenía columna `reason`."""
    from cassoni.woo import WooError
    pipe = _pipeline(tmp_path, dry_run=False)
    pipe.woo.falla_escritura = WooError("POST products/120563: 503")
    res = pipe.process(URL)
    assert res.status == "failed"
    row = pipe.db.get_state(URL)
    assert row.status == "failed"
    assert "503" in row.reason
    assert row.applied == 0


def test_ficha_no_publicada_no_queda_in_queue(tmp_path):
    pipe = _pipeline(tmp_path)
    pipe.woo.product["status"] = "draft"
    res = pipe.process(URL)
    assert res.status == "skipped"
    row = pipe.db.get_state(URL)
    assert row.status == "skipped" and "draft" in row.reason


def test_un_fallo_del_llm_no_tumba_el_lote(tmp_path):
    from cassoni.llm import LLMError
    pipe = _pipeline(tmp_path)

    def roto(*a, **k):
        raise LLMError("timeout")
    pipe.llm.complete_json = roto
    res = pipe.process(URL)
    assert res.status == "failed"
    assert "timeout" in pipe.db.get_state(URL).reason


def test_url_que_no_es_producto(tmp_path):
    assert _pipeline(tmp_path).process("https://x.com/product-category/sofas/").status == "skipped"


# --- traza y medición ---------------------------------------------------------
def test_guarda_las_tres_keywords_con_su_linea_base(tmp_path):
    pipe = _pipeline(tmp_path, dry_run=False)
    pipe.process(URL)
    objetivos = pipe.db.objetivos_de(URL)
    assert len(objetivos) == 3
    o = next(x for x in objetivos if x.keyword == "sofá chesterfield")
    assert o.baseline_impressions == 400 and o.baseline_position == 8.0
    assert o.volume == 1900 and o.aplicada == 1


def test_registra_costos_llm_y_dataforseo(tmp_path):
    pipe = _pipeline(tmp_path)
    pipe.precargar([URL])
    pipe.process(URL)
    row = pipe.db.get_state(URL)
    assert float(row.llm_cost) > 0
    assert row.llm_tokens_in > 0
    assert row.dfs_cost is not None


def test_el_editor_recibe_el_contexto_de_la_ficha(tmp_path):
    pipe = _pipeline(tmp_path)
    pipe.process(URL)
    assert pipe.woo.sibling_calls == [5]
    u = pipe.llm.editor_user
    assert "Categoría(s): Sofas" in u and "Marca: Cassoni" in u and "Material: Cuero" in u


def test_la_precarga_hace_dos_pedidos_de_volumen_para_todo_el_lote(tmp_path):
    """Prueba real 3-nov: las candidatas de competidores pedían volumen ficha por
    ficha (US$ 0,09 cada una). Ahora: uno para GSC y uno para competidores."""
    comp = FakeCompetidores(PAGINAS)
    pipe = _pipeline(tmp_path, gsc=FakeGSC([]), competidores=comp,
                     vol={"pedro sofa": 50})
    pipe.precargar([URL])
    pipe.process(URL)
    assert len(pipe.volumenes.pedidos) == 1        # sin GSC: solo el de competidores
    assert len(comp.consultas) == 1                # la búsqueda no se paga dos veces
