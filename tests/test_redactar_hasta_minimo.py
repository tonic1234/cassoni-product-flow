# -*- coding: utf-8 -*-
"""Si el redactor omite una keyword por no entrar natural y la ficha queda debajo del
mínimo, se redacta una vez más con la siguiente reserva coherente (23-nov)."""
from cassoni.config import Config
from cassoni.validator import Validator


class _Val(Validator):
    def __init__(self, omite_siempre=()):
        self.cfg = Config(env="staging")
        self.llamadas = []
        self.omite = set(omite_siempre)

    def redactar_y_validar(self, *, ficha, keywords, redactor, max_passes=3):
        kws = [k["keyword"] for k in keywords]
        self.llamadas.append(kws)
        omitidas = [{"keyword": k, "motivo": "no entra natural"} for k in kws if k in self.omite]
        return {"aprobado": True, "intentos": 1, "validacion": {"aprobado": True},
                "edited": {"h1": "Frog Glass Coffee Table by Sovet Italia",
                           "description": "<p>" + ". ".join(kws) + ".</p>", "omitidas": omitidas}}


K = lambda *ks: [{"keyword": k, "origen": "gsc"} for k in ks]  # noqa: E731


def test_reemplaza_la_omitida_con_la_siguiente_reserva():
    v = _Val(omite_siempre={"tiffany style mirror"})
    out = v.redactar_hasta_minimo(ficha={}, keywords=K("frog table", "tiffany style mirror", "glass table"),
                                  reservas=K("modern glass coffee table", "curved glass table"),
                                  redactor=None, minimo=3)
    assert [k["keyword"] for k in out["objetivos"]] == ["frog table", "glass table", "modern glass coffee table"]
    assert out["reservas_usadas"] == ["modern glass coffee table"] and len(v.llamadas) == 2


def test_con_el_minimo_no_hay_segunda_vuelta():
    v = _Val()
    out = v.redactar_hasta_minimo(ficha={}, keywords=K("a b", "c d", "e f"), reservas=K("g h"),
                                  redactor=None, minimo=3)
    assert len(out["objetivos"]) == 3 and len(v.llamadas) == 1


def test_sin_reservas_queda_con_menos_y_no_fuerza():
    v = _Val(omite_siempre={"c d"})
    out = v.redactar_hasta_minimo(ficha={}, keywords=K("a b", "c d"), reservas=[],
                                  redactor=None, minimo=3)
    assert [k["keyword"] for k in out["objetivos"]] == ["a b"] and len(v.llamadas) == 1


def test_el_validador_no_objeta_el_h1_que_decidio_la_regla():
    from cassoni.validator import _nota_h1
    ficha = {"h1_fijo": "Rock Marble Coffee Table by Rugiano",
             "h1_regla": "opción más buscada: 'marble coffee table'"}
    assert "No lo objetes" in _nota_h1(ficha, {"h1": "Rock Marble Coffee Table by Rugiano"})
    assert _nota_h1(ficha, {"h1": "Otro H1"}) == ""
    assert _nota_h1({}, {"h1": "x"}) == ""


class _ValForzada(_Val):
    def redactar_y_validar(self, *, ficha, keywords, redactor, max_passes=3):
        out = super().redactar_y_validar(ficha=ficha, keywords=keywords, redactor=redactor)
        if "italian piano" in [k["keyword"] for k in keywords]:
            out["aprobado"] = False
            out["validacion"] = {"aprobado": False, "issues": [
                "Keyword forzada: «As an italian piano, it is a piece…» existe solo para meter «italian piano»."]}
        return out


def test_la_keyword_forzada_sale_en_vez_de_rechazar_la_ficha():
    v = _ValForzada()
    out = v.redactar_hasta_minimo(ficha={}, keywords=K("19800 steinway piano", "steinway and sons piano",
                                                       "italian piano"),
                                  reservas=K("mother of pearl piano"), redactor=None, minimo=3)
    assert out["aprobado"] and out["forzadas_sacadas"] == ["italian piano"]
    assert [k["keyword"] for k in out["objetivos"]] == [
        "19800 steinway piano", "steinway and sons piano", "mother of pearl piano"]
