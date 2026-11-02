# -*- coding: utf-8 -*-
"""El re-trabajo del validador no puede perder datos de la ficha.

Hallazgo del piloto real (2-nov): el 2do pase rebotaba con "Falta la keyword
principal" y "hay 0 secundarias" porque `_rework` devolvía sólo h1 y description.
El editor sí las producía: las tiraba el validador.
"""
from cassoni.config import Config
from cassoni.validator import Validator


class _EditorFake:
    def __init__(self, salida):
        self.salida = salida
        self.llamadas = 0

    def edit(self, **kw):
        self.llamadas += 1
        return dict(self.salida)


def _cfg():
    c = Config(env="staging", dry_run=True)
    c.llm_validator_model = "validator"
    return c


FICHA = {"h1": "Rugiano Club Sofa", "description": "<p>texto</p>",
         "keyword_principal": "club sofa",
         "secondary_keywords": [{"keyword": "leather upholstery", "why": "tapizado"},
                                {"keyword": "brass structure", "why": "estructura"}],
         "discarded": [], "used_keywords": ["club sofa"],
         "selection_reason": "única candidata"}


def test_rework_conserva_la_ficha_completa():
    v = Validator(_cfg(), llm=None)
    v._context = {}
    out = v._rework(_EditorFake(FICHA), "u",
                    {"h1": "h", "description": "d"}, [{"keyword": "club sofa"}], ["issue"])
    assert out["keyword_principal"] == "club sofa"
    assert len(out["secondary_keywords"]) == 2
    assert out["h1"] == "Rugiano Club Sofa"


def test_segunda_pasada_no_se_auto_rechaza_por_campos_perdidos(monkeypatch):
    """Con un validador LLM que aprueba, el 2do pase debe aprobar si el editor
    devolvió una ficha completa (antes rebotaba por sus propios campos borrados)."""
    v = Validator(_cfg(), llm=None)

    class LLMQueRechazaLaPrimera:
        def __init__(self):
            self.n = 0

        def complete_json(self, system, user, **kw):
            self.n += 1
            if self.n == 1:
                return {"aprobado": False, "issues": ["dato inventado"], "razon": "x"}
            return {"aprobado": True, "issues": [], "razon": "ok"}

    v.llm = LLMQueRechazaLaPrimera()
    editor = _EditorFake(FICHA)
    orig = ("<p>This is a designer Italian Sofa, part of the exclusive Club collection. "
            "It stands out for the innovative structure created by refined brushed brass "
            "or bronze drawn tubes that, combined with the upholstered leather or fabric, "
            "create a stylish pattern. A high-end Glamour furniture, ideal to fit in any "
            "sophisticated living area. Made in Italy.</p>")
    # el editor devuelve la MISMA descripción original: conservación 100% -> sin issues mecánicos
    relleno = ("The piece is conceived as a quiet statement rather than a decorative "
               "gesture, and its presence grows the longer one stays in the room. "
               "Proportion, material and finish are balanced so that the sofa can sit "
               "at the centre of a living area without ever competing with it. "
               "Each element is finished by hand, and the result is a furniture piece "
               "meant to age slowly and well. The upholstery sits taut over the frame, "
               "and the joints are kept visible on purpose, so that the construction "
               "reads clearly from every angle. Nothing is hidden and nothing is "
               "overstated: the sofa states its quality through restraint, and that "
               "restraint is precisely what makes it feel at home in a room that is "
               "already full of objects.")
    ficha = dict(FICHA, description=orig + " " + relleno)
    res = v.pass_or_rework(url="u", original_h1="Club Sofa", original_desc=orig,
                           edited=dict(ficha), target_keywords=["club sofa"],
                           editor=_EditorFake(ficha), backup_keywords=[{"keyword": "club sofa"}],
                           context={}, max_passes=2)
    assert res["aprobado"] is True, res["validacion"]
    assert res["edited"]["keyword_principal"] == "club sofa"


class _LLMCaptura:
    def __init__(self):
        self.user = ""

    def complete_json(self, system, user, **kw):
        self.user = user
        return {"aprobado": True, "issues": [], "razon": "ok"}


def test_el_validador_ve_los_atributos_oficiales_de_la_ficha():
    """Piloto real (2-nov): marcó como 'inventadas' las medidas 62"3/8 y 122" y la
    'New Glamour Collection'. Todo eso son atributos REALES de WooCommerce; el
    validador los juzgaba sin verlos (falso positivo)."""
    llm = _LLMCaptura()
    v = Validator(_cfg(), llm)
    v.validate(url="u", original_h1="Club Sofa", original_desc="<p>corto</p>",
               edited_h1="Rugiano Club Sofa",
               edited_desc="<p>Available from 62\"3/8 to 122\"W</p>",
               target_keywords=["club sofa"],
               attributes=("Size: 62\"3/8W x 33\"1/2D x 28\"H", "Collection: New Glamour Collection"),
               brand="Rugiano", categories=("Sofas & Sectionals",))
    assert "Atributos oficiales de la ficha" in llm.user
    assert 'New Glamour Collection' in llm.user
    assert "62\"3/8W" in llm.user
    assert "Rugiano" in llm.user


def test_pass_or_rework_pasa_los_atributos_al_validador():
    llm = _LLMCaptura()
    v = Validator(_cfg(), llm)
    orig = ("<p>" + " ".join(["Elegante sofá de cuero negro con estructura de latón "
                              "cepillado y tapizado italiano."] * 1) + "</p>")
    v.pass_or_rework(url="u", original_h1="Club Sofa", original_desc=orig,
                     edited=dict(FICHA, description=orig + " " + "palabra " * 160),
                     target_keywords=["club sofa"], editor=_EditorFake(FICHA),
                     backup_keywords=[{"keyword": "club sofa"}],
                     context={"attributes": ("Size: 122\"W",),
                              "brand": "Rugiano", "categories": ("Sofas & Sectionals",)})
    assert "122\"W" in llm.user


class _EditorEspia:
    def __init__(self):
        self.ultimo_kw = {}

    def edit(self, **kw):
        self.ultimo_kw = kw
        return dict(FICHA)


def test_el_rework_le_dice_al_editor_por_que_rechazaron():
    """El validador recibía los issues y los descartaba: el editor rehacía a
    ciegas y el segundo pase repetía el mismo error (piloto 2-nov)."""
    v = Validator(_cfg(), llm=None)
    v._context = {}
    ed = _EditorEspia()
    v._rework(ed, "u", {"h1": "h", "description": "d"}, [{"keyword": "k"}],
              ["conserva solo 67% de las oraciones originales"])
    assert ed.ultimo_kw.get("feedback")
    assert "67%" in " ".join(ed.ultimo_kw["feedback"])


def test_el_editor_imprime_el_feedback_en_el_prompt():
    from cassoni.editor import Editor
    capturado = {}

    class LLM:
        def complete_json(self, system, user, **kw):
            capturado["user"] = user
            return dict(FICHA)

    ed = Editor(_cfg(), LLM())
    ed.edit(url="u", current_h1="H", current_description="<p>x</p>",
            keywords=[{"keyword": "k"}], keyword_principal="k",
            feedback=["conserva solo 67% de las oraciones originales"])
    assert "RECHAZADA" in capturado["user"].upper()
    assert "67%" in capturado["user"]
