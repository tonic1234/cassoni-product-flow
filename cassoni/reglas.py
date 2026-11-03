# -*- coding: utf-8 -*-
"""Reglas del agente SEO — fuente ÚNICA de la spec del cliente
(docs/REGLA-SEO-FICHAS.md). Constantes numéricas + textos en español que los
prompts del editor/validador copian literal. Si cambia el documento del cliente,
se cambia este archivo (con sus tests) y se regenera la doc.
"""
from __future__ import annotations

# --- Límites duros de la spec ---
H1_PLANTILLA = "{nombre} by {marca}"  # H1 fijo (SEO 3-nov-2026): sin LLM, misma
                                      # estructura en todas las fichas (cassoni/h1.py)
KW_OBJETIVO = 3                       # keywords que se incorporan a la desc larga
KW_MIN = 1                            # con menos de 1 no hay nada que editar
LARGA_MIN_WORDS = 150                 # referencia del cliente; desde el 3-nov NO bloquea
                                      # (con originales cortos obligaba a rellenar)
PALABRAS_POR_KEYWORD = 30             # lo que puede crecer una ficha ya larga por keyword
LARGA_MAX_WORDS = 300                 # descripción larga: máximo
MAX_H2 = 2                            # máx 2 H2 en la descripción larga
SEC_MIN = 2                           # mínimo de keywords secundarias
SEC_MAX = 3                           # máximo de keywords secundarias
SEC_MAX_USOS = 2                      # cada secundaria aparece máx 2 veces
CONSERVACION_MIN = 0.8                # mínimo de oraciones del original que deben
                                      # sobrevivir intactas en la desc larga editada
                                      # (subido de 0.6: la v3 del piloto tocó una
                                      # oración para meter 'modular sofa' — 0.75; la
                                      # regla de Antonio es MAXIMA conservación)
REPETICION_MAX_PALABRA = 8            # tope de veces que una misma palabra (no
                                      # funcional) puede aparecer en la desc larga

# --- Texto canónico de reglas (lo que ve el LLM, mismo origen que el checklist) ---
REGLAS_H1 = ("Título/H1: siempre '{Nombre} by {Marca}', armado por código con la "
             "misma estructura en todas las fichas. El editor NO lo toca.")
REGLAS_KEYWORDS = ("Keywords objetivo: hasta 3 por ficha, elegidas por código (GSC + "
                   "volumen de DataForSEO, o competidores que venden el mismo producto). "
                   "Son keywords que NO estaban en la descripción: cada una tiene que "
                   "quedar EXACTA en la descripción larga, 1 o 2 veces, en una oración "
                   "donde encaje natural.")
REGLAS_KEYWORD_JUNTA = ("Las palabras de cada keyword van JUNTAS y en el MISMO orden "
                        "('leather sofa' es 'leather sofa'). La única variable aceptable "
                        "es que se antecedan por un artículo ('of', 'the', etc.). "
                        "Prohibido intercalar palabras u ordenarlas al revés.")
REGLAS_DESC_CORTA = ("Descripción corta (above the fold): incluye la keyword principal "
                     "exacta tal cual el H1; corta; una sola idea central; SIN H2.")
REGLAS_DESC_LARGA = ("Descripción larga (below the fold): hasta 300 palabras; 1 o 2 H2 "
                     "como máximo; cada keyword aparece como máximo 2 veces. Si el "
                     "original es corto, queda corto: se agregan SOLO las oraciones de "
                     "las keywords, nunca relleno para llegar a 150 palabras.")
REGLAS_SIN_MEDIDAS = ("No agregues medidas ni dimensiones (pulgadas, centímetros, ancho x "
                      "profundidad x alto): la ficha ya las muestra en su tabla de atributos.")
REGLAS_HTML = ("HTML: no agregues scripts, iframes, estilos, formularios, atributos "
               "de evento (onclick...) ni enlaces o imágenes que no estén en el original.")
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
                "encaja natural. PROHIBIDO agregar medidas, dimensiones, pulgadas, "
                "centímetros, años ni nombres de colección que no aparezcan "
                "LITERALMENTE en el texto original o en los atributos: aunque los "
                "conozcas, no están en los inputs (el validador los marca como dato "
                "inventado y rebota la ficha).")
REGLAS_CONSERVAR = ("Sobre la descripción larga: PARTÍ DE LA ACTUAL tal cual viene; "
                    "editála QUIRÚRGICAMENTE; NUNCA la reescribas desde cero. La versión "
                    "editada conserva la estructura, la redacción y el tono del original. "
                    "Al menos el 80% de las ORACIONES originales deben sobrevivir "
                    "INTACTAS: agregá oraciones nuevas ENTRE las existentes; no partas, "
                    "fusiones ni reformules las que ya están.")
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
REGLAS_OUTPUT = ("Output por ficha: descripción larga con H2 marcados / dónde quedó "
                 "cada keyword objetivo y por qué encaja en ESTE producto.")


def reglas_completas() -> str:
    """Bloque de reglas completo para los prompts (editor y validador)."""
    return "\n".join([
        REGLAS_H1, REGLAS_KEYWORDS, REGLAS_DESC_LARGA, REGLAS_ANTICANIBALIZACION,
        REGLAS_NO_GO, REGLAS_CONSERVAR, REGLAS_HTML,
    ])