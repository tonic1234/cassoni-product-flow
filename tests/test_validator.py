# -*- coding: utf-8 -*-
"""Validador: reglas mecánicas + LLM, con re-trabajo que no pierde datos.

Hallazgos que siguen cubiertos (piloto 2-nov): el re-trabajo le dice al editor
POR QUÉ rechazaron, y el validador juzga con los atributos oficiales de la
ficha. Nuevo (3-nov): el validador ve el texto completo (antes cortaba en 2.500
caracteres) y el H1 de plantilla viaja intacto por los re-trabajos.
"""
from cassoni.config import Config
from cassoni.validator import MAX_CHARS_TEXTO, Validator

ORIG = ("<p>This is a designer Italian Sofa, part of the exclusive Club collection. "
        "It stands out for the innovative structure created by refined brushed brass "
        "or bronze drawn tubes that, combined with the upholstered leather or fabric, "
        "create a stylish pattern. A high-end Glamour furniture, ideal to fit in any "
        "sophisticated living area. Made in Italy.</p>")
RELLENO = ("<p>The piece is conceived as a quiet statement rather than a decorative "
           "gesture, and its presence grows the longer one stays in the room. "
           "Proportion, material and finish are balanced so that this club sofa can sit "
           "at the centre of a living area without ever competing with it. "
           "Each element is finished by hand, and the result is a furniture piece "
           "meant to age slowly and well. The upholstery sits taut over the frame, "
           "and the joints are kept visible on purpose, so that the construction "
           "reads clearly from every angle. Nothing is hidden and nothing is "
           "overstated: the sofa states its quality through restraint, and that "
           "restraint is precisely what makes it feel at home in a room that is "
           "already full of objects.</p>")
EDITADA = ORIG + RELLENO
FICHA = {"h1": "Club Sofa by Rugiano", "description": EDITADA,
         "keywords": [{"keyword": "club sofa", "why": "es un club sofa"}]}
KWS = [{"keyword": "club sofa", "volume": 880}]


class _EditorFake:
    def __init__(self, salida):
        self.salida = salida
        self.llamadas = []

    def edit(self, **kw):
        self.llamadas.append(kw)
        return dict(self.salida)


def _cfg():
    c = Config(env="staging", dry_run=True)
    c.llm_validator_model = "validator"
    return c


class _LLMCaptura:
    def __init__(self, respuestas=None):
        self.users = []
        self.respuestas = list(respuestas or [])

    @property
    def user(self):
        return self.users[-1] if self.users else ""

    def complete_json(self, system, user, **kw):
        self.users.append(user)
        if self.respuestas:
            return self.respuestas.pop(0)
        return {"aprobado": True, "issues": [], "razon": "ok"}


def test_aprueba_si_reglas_y_llm_aprueban():
    v = Validator(_cfg(), _LLMCaptura())
    res = v.pass_or_rework(url="u", original_desc=ORIG, edited=dict(FICHA), keywords=KWS,
                           editor=_EditorFake(FICHA))
    assert res["aprobado"] is True, res["validacion"]
    assert res["intentos"] == 1


def test_segunda_pasada_aprueba_y_conserva_el_h1():
    llm = _LLMCaptura([{"aprobado": False, "issues": ["dato inventado"], "razon": "x"},
                       {"aprobado": True, "issues": [], "razon": "ok"}])
    editor = _EditorFake(FICHA)
    res = Validator(_cfg(), llm).pass_or_rework(
        url="u", original_desc=ORIG, edited=dict(FICHA), keywords=KWS, editor=editor)
    assert res["aprobado"] is True
    assert res["intentos"] == 2
    assert editor.llamadas[0]["h1"] == "Club Sofa by Rugiano"


def test_rechaza_si_la_keyword_no_quedo():
    sin_kw = dict(FICHA, description=EDITADA.replace("this club sofa", "this piece"))
    res = Validator(_cfg(), _LLMCaptura()).pass_or_rework(
        url="u", original_desc=ORIG, edited=sin_kw, keywords=KWS,
        editor=_EditorFake(sin_kw))
    assert res["aprobado"] is False
    assert any("club sofa" in i for i in res["validacion"]["issues"])


def test_el_rework_le_dice_al_editor_por_que_rechazaron():
    """El editor rehacía a ciegas y repetía el error (piloto 2-nov)."""
    llm = _LLMCaptura([{"aprobado": False, "issues": ["conserva solo 67%"], "razon": "x"}] * 2)
    editor = _EditorFake(FICHA)
    Validator(_cfg(), llm).pass_or_rework(url="u", original_desc=ORIG, edited=dict(FICHA),
                                          keywords=KWS, editor=editor)
    assert "67%" in " ".join(editor.llamadas[0]["feedback"])


def test_el_validador_ve_los_atributos_oficiales_de_la_ficha():
    """Piloto real (2-nov): marcó como 'inventadas' medidas que eran atributos."""
    llm = _LLMCaptura()
    Validator(_cfg(), llm).validate(
        url="u", h1="Club Sofa by Rugiano", original_desc="<p>corto</p>",
        edited_desc="<p>Available from 62\"3/8 to 122\"W</p>", target_keywords=["club sofa"],
        attributes=("Size: 62\"3/8W x 33\"1/2D x 28\"H", "Collection: New Glamour Collection"),
        brand="Rugiano", categories=("Sofas & Sectionals",))
    assert "Atributos oficiales de la ficha" in llm.user
    assert "New Glamour Collection" in llm.user
    assert "Rugiano" in llm.user


def test_el_validador_ve_el_texto_completo():
    """Antes cortaba en 2.500 caracteres: lo inventado al final no se revisaba."""
    llm = _LLMCaptura()
    largo = "<p>" + "x" * 5000 + " DATO-FINAL</p>"
    Validator(_cfg(), llm).validate(url="u", h1="h", original_desc="<p>o</p>",
                                    edited_desc=largo, target_keywords=["k"])
    assert "DATO-FINAL" in llm.user
    assert MAX_CHARS_TEXTO >= 10000


def test_el_editor_imprime_el_feedback_en_el_prompt():
    from cassoni.editor import Editor
    llm = _LLMCaptura([dict(FICHA)])
    Editor(_cfg(), llm).edit(url="u", h1="H", current_description="<p>x</p>",
                             keywords=[{"keyword": "club sofa"}],
                             feedback=["conserva solo 67% de las oraciones originales"])
    assert "RECHAZADA" in llm.user.upper()
    assert "67%" in llm.user
