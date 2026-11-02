# -*- coding: utf-8 -*-
"""Test de la lógica de oportunidades de GSC — puro, sin red."""
import warnings

import pytest

from cassoni import opportunities as opp


def _row(position=None, impressions=None, clicks=None, ctr=None):
    r = {}
    if position is not None:
        r["position"] = position
    if impressions is not None:
        r["impressions"] = impressions
    if clicks is not None:
        r["clicks"] = clicks
    if ctr is not None:
        r["ctr"] = ctr
    return r


class TestClassify:
    def test_materialize_demand_cusp(self):
        # posición 12 con demanda real -> oportunidad de materializar demanda (la mejor)
        assert opp.classify(_row(position=12, impressions=300)) == opp.MATERIALIZE_DEMAND

    def test_materialize_demand_edge_bottom(self):
        # llega hasta posición 20 y 150 impresiones
        assert opp.classify(_row(position=20, impressions=150)) == opp.MATERIALIZE_DEMAND

    def test_position_21_no_es_materialize(self):
        # pasó la frontera: fuera de la ventana de oportunidades
        assert opp.classify(_row(position=21, impressions=1500)) != opp.MATERIALIZE_DEMAND

    def test_lift_ctr_mucho_aparecer_nadie_entra(self):
        # 800 impresiones, ctr 1% -> aparece pero no entra nadie
        assert opp.classify(_row(position=2, impressions=800, ctr=0.01)) == opp.LIFT_CTR

    def test_lift_ctr_umbral_ctr(self):
        # ctr justo en el umbral (3%) aún es lift_ctr; por encima deja de serlo
        assert opp.classify(_row(impressions=600, ctr=0.03)) == opp.LIFT_CTR
        assert opp.classify(_row(impressions=600, ctr=0.031)) != opp.LIFT_CTR

    def test_hold_top(self):
        # rankea en top y el ctr es sano -> mantener (keyword principal)
        assert opp.classify(_row(position=2, impressions=900, ctr=0.08)) == opp.HOLD_TOP

    def test_long_tail(self):
        # posición lejana, poca demanda -> no prioridad
        assert opp.classify(_row(position=30, impressions=30)) == opp.LONG_TAIL

    def test_prioridad_sobre_lift_ctr(self):
        # cumple materialize (pos 12, 300 impr) aunque el ctr sea bajísimo: manda la demanda
        assert opp.classify(_row(position=12, impressions=300, ctr=0.01)) == opp.MATERIALIZE_DEMAND

    def test_sin_datos_no_crashea(self):
        assert opp.classify(_row()) == opp.LONG_TAIL


class TestScore:
    def test_materialize_acota_a_100(self):
        # pos 20, 2500 impresiones -> cap en 100
        assert 0 <= opp.opportunity_score(_row(position=20, impressions=2500)) <= 100

    def test_long_tail_cero(self):
        assert opp.opportunity_score(_row(position=30, impressions=30)) == 0

    def test_materialize_mas_demanda_mas_score(self):
        a = opp.opportunity_score(_row(position=12, impressions=300))
        b = opp.opportunity_score(_row(position=12, impressions=900))
        assert b >= a

    def test_materialize_cerca_del_top_mayor(self):
        # pos 8 debería puntuar más que pos 20 (más cerca de rankear bien)
        near = opp.opportunity_score(_row(position=8, impressions=300))
        far = opp.opportunity_score(_row(position=20, impressions=300))
        assert near > far

    def test_any_score_in_0_100(self):
        for row in (dict(position=5, impressions=200),
                    dict(position=2, impressions=2000, ctr=0.02),
                    dict(position=1, impressions=500, ctr=0.10)):
            assert 0 <= opp.opportunity_score(row) <= 100


class TestAnnotateAndTop:
    def test_annotate_no_muta_entrada(self):
        r = _row(position=12, impressions=300)
        before = dict(r)
        opp.annotate([r])
        assert r == before  # el dict original no se toca
        assert "opportunity" not in r

    def test_annotate_agrega_categoria_y_score(self):
        out = opp.annotate([_row(position=12, impressions=300)])
        assert out[0]["opportunity"] == opp.MATERIALIZE_DEMAND
        assert isinstance(out[0]["opportunity_score"], int)

    def test_top_opportunities_ordena_y_respeta_top_n(self):
        rows = [_row(position=12, impressions=300),   # materialize
                _row(position=30, impressions=30),    # long_tail (0)
                _row(position=8, impressions=500),    # materialize (alto)
                _row(position=2, impressions=900, ctr=0.08)]  # hold_top (40)
        tops = opp.top_opportunities(rows, top_n=2)
        assert len(tops) == 2
        assert tops[0]["position"] == 8 < tops[1]["position"]  # el de mayor score primero
        # long_tail nunca entra (score 0)
        assert all(t["opportunity_score"] > 0 for t in tops)

    def test_top_opportunities_vacio_si_no_hay(self):
        assert opp.top_opportunities([_row(position=30, impressions=30)]) == []

    def test_has_opportunity(self):
        assert opp.has_opportunity(_row(position=12, impressions=300))
        assert not opp.has_opportunity(_row(position=30, impressions=30))

class TestElegirPrincipal:
    """La principal manda por OPORTUNIDAD, no por volumen.

    Caso real medido (auditoría 13-oct): la consulta con 5.000 impresiones en
    posición 2 no tiene nada que ganar; la de 300 impresiones en posición 12 sí.
    """

    def test_manda_la_oportunidad_y_no_el_volumen(self):
        cands = [
            {"keyword": "sofa de cuero", "volume": 5000, "impressions": 5000,
             "clicks": 400, "ctr": 0.08, "position": 2.0},
            {"keyword": "sofa modular", "volume": 120, "impressions": 300,
             "clicks": 0, "ctr": 0.0, "position": 12.0},
        ]
        assert opp.elegir_principal(cands) == "sofa modular"

    def test_sin_datos_de_oportunidad_respeta_el_orden_recibido(self):
        # degradación: si no hay filas de GSC, el orden de entrada (volumen) decide
        assert opp.elegir_principal([{"keyword": "a"}, {"keyword": "b"}]) == "a"

    def test_el_volumen_desempata_oportunidades_iguales(self):
        cands = [
            {"keyword": "pequena", "volume": 90, "impressions": 300,
             "clicks": 0, "ctr": 0.0, "position": 12.0},
            {"keyword": "grande", "volume": 900, "impressions": 300,
             "clicks": 0, "ctr": 0.0, "position": 12.0},
        ]
        assert opp.elegir_principal(cands) == "grande"

    def test_lista_vacia_devuelve_cadena_vacia(self):
        assert opp.elegir_principal([]) == ""

    def test_no_muta_las_candidatas(self):
        cands = [{"keyword": "a", "position": 12.0, "impressions": 300},
                 {"keyword": "b", "position": 2.0, "impressions": 5000, "ctr": 0.08}]
        antes = [dict(c) for c in cands]
        opp.elegir_principal(cands)
        assert cands == antes

    def test_ordenar_candidatas_pone_la_principal_primero(self):
        cands = [
            {"keyword": "sofa de cuero", "volume": 5000, "impressions": 5000,
             "clicks": 400, "ctr": 0.08, "position": 2.0},
            {"keyword": "sofa modular", "volume": 120, "impressions": 300,
             "clicks": 0, "ctr": 0.0, "position": 12.0},
        ]
        out = opp.ordenar_candidatas(cands)
        assert out[0]["keyword"] == "sofa modular"
        assert len(out) == 2


def test_score_es_entero_aunque_la_posicion_venga_con_decimales():
    """GSC devuelve posiciones con decimales (7.466...). El score 0-100 es entero:
    si se cuela un float, el lote publica '80.53382352941176' y deja de ser auditable."""
    r = _row(position=7.466176470588235, impressions=1360)
    s = opp.opportunity_score(r)
    assert isinstance(s, int)
    assert opp.annotate([r])[0]["opportunity_score"] == s
