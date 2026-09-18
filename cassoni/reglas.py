# -*- coding: utf-8 -*-
"""Reglas del agente SEO — fuente ÚNICA de la spec del cliente
(docs/REGLA-SEO-FICHAS.md). Constantes numéricas + textos en español que los
prompts del editor/validador copian literal. Si cambia el documento del cliente,
se cambia este archivo (con sus tests) y se regenera la doc.
"""
from __future__ import annotations

# --- Límites duros de la spec ---
H1_MAX_CHARS = 60                     # título: máx 60 caracteres
LARGA_MIN_WORDS = 150                 # descripción larga: mínimo
LARGA_MAX_WORDS = 300                 # descripción larga: máximo
MAX_H2 = 2                            # máx 2 H2 en la descripción larga
SEC_MIN = 2                           # mínimo de keywords secundarias
SEC_MAX = 3                           # máximo de keywords secundarias
SEC_MAX_USOS = 2                      # cada secundaria aparece máx 2 veces
CONSERVACION_MIN = 0.6                # mínimo de oraciones del original que deben
                                      # sobrevivir intactas en la desc larga editada
REPETICION_MAX_PALABRA = 8            # tope de veces que una misma palabra (no
                                      # funcional) puede aparecer en la desc larga

# --- Texto canónico de reglas (lo que ve el LLM, mismo origen que el checklist) ---
REGLAS_H1 = ("Título/H1: máximo 60 caracteres; marca (si aplica) + modelo + categoría "
             "completa; es la keyword principal, EXACTA.")
REGLAS_DESC_CORTA = ("Descripción corta (above the fold): incluye la keyword principal "
                     "exacta tal cual el H1; corta; una sola idea central; SIN H2.")
REGLAS_DESC_LARGA = ("Descripción larga (below the fold): 150 a 300 palabras; 1 o 2 H2 "
                     "como máximo; 2 o 3 keywords secundarias repartidas entre H2 y "
                     "párrafos; cada secundaria aparece como máximo 2 veces.")
REGLAS_SECUNDARIAS = ("Keywords secundarias: variantes por material, estilo, uso o "
                      "sinónimo de categoría; específicas de ESTE producto, nunca "
                      "genéricas de toda la categoría.")
REGLAS_ANTICANIBALIZACION = ("Filtro anti canibalización: descartar una candidata si ya "
                             "es la principal de otra ficha, si compite con la página de "
                             "categoría, o si responde mejor a un blog o guía de compra "
                             "que a una ficha.")
REGLAS_NO_GO = ("No hacer: no inventar atributos que no estén en los inputs; no copiar "
                "descripciones de competidores; no repetir la misma secundaria en varias "
                "fichas sin chequear; no forzar una keyword en una oración donde no "
                "encaja natural.")
REGLAS_CONSERVAR = ("Sobre la descripción larga: PARTÍ DE LA ACTUAL tal cual viene; "
                    "editála QUIRÚRGICAMENTE; NUNCA la reescribas desde cero. La versión "
                    "editada conserva la estructura, la redacción y el tono del original.")
REGLAS_TONO = ("TONO DE LA MARCA: el registro de Cassoni es sobrio y técnico, ficha de "
               "catálogo de lujo. Nada de frases comerciales genéricas, nada de "
               "subtítulos estilo blog si el original NO los tiene: si el original es "
               "prosa continua, la edición sigue en prosa continua. El texto nuevo debe "
               "sonar escrito por la misma persona que el original.")
REGLAS_DIVERSIFICAR = ("DIVERSIFICACIÓN (anti-repetición): si varias keywords comparten "
                       "una palabra (p. ej. 'sofa'), cada keyword COMPLETA aparece como "
                       "máximo 2 veces y el resto del texto usa SUS PARTES (material, "
                       "estilo, uso) como variaciones naturales. Repetir la palabra "
                       "compartida una y otra vez ('sofa sofa sofa') está prohibido.")
REGLAS_OUTPUT = ("Output por ficha: H1 / descripción larga con H2 "
                 "marcados / keywords secundarias + por qué son específicas / descartadas "
                 "+ a qué contenido pertenecen.")


def reglas_completas() -> str:
    """Bloque de reglas completo para los prompts (editor y validador)."""
    return "\n".join([
        REGLAS_H1, REGLAS_DESC_CORTA, REGLAS_DESC_LARGA, REGLAS_SECUNDARIAS,
        REGLAS_ANTICANIBALIZACION, REGLAS_NO_GO, REGLAS_CONSERVAR, REGLAS_OUTPUT,
    ])