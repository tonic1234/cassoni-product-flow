# -*- coding: utf-8 -*-
"""La landing que se comparte tiene tarjeta de previsualización y no filtra notas internas.

Dos cosas que se rompen en silencio y llegan al cliente:
  · el link se manda por WhatsApp/Teams y llega como un rectángulo sin imagen (og:image rota,
    apuntando a otro dominio o a un archivo que no está en la carpeta);
  · el HTML publicado arrastra una nota de cocina interna en el JSON embebido ("sin saldo",
    qué modelo redactó), que el equipo del cliente ve con ver código fuente.

El candado corre sobre el FUENTE (docs/landing-agente/), que es lo que se publica; la copia
servida en CASE se verifica aparte por md5 contra este archivo.

Se lee el JPEG a mano (sin Pillow): el repo no tiene PIL y el gate corre en CASE y en TARS.
"""
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CARPETA = RAIZ / "docs" / "landing-agente"
HTML = CARPETA / "index.html"
URL = "https://tarsterminal.duckdns.org/cassoni-agente-seo/"

SOF_BASELINE = 0xC0
SOF_PROGRESSIVE = 0xC2


def _html() -> str:
    assert HTML.exists(), f"falta la landing: {HTML}"
    return HTML.read_text(encoding="utf-8")


def _meta(nombre: str) -> str:
    m = re.search(r'<meta\s+(?:property|name)="%s"\s+content="([^"]*)"' % re.escape(nombre), _html())
    assert m, f"falta la etiqueta {nombre} en la landing"
    return m.group(1)


def _jpeg_medidas(datos: bytes):
    """(ancho, alto, marcador SOF) leyendo los segmentos del JPEG."""
    assert datos[:2] == b"\xff\xd8", "no es un JPEG"
    i = 2
    while i < len(datos) - 9:
        if datos[i] != 0xFF:
            i += 1
            continue
        marcador = datos[i + 1]
        if marcador in (SOF_BASELINE, SOF_PROGRESSIVE, 0xC1):
            alto = int.from_bytes(datos[i + 5:i + 7], "big")
            ancho = int.from_bytes(datos[i + 7:i + 9], "big")
            return ancho, alto, marcador
        largo = int.from_bytes(datos[i + 2:i + 4], "big")
        i += 2 + largo
    raise AssertionError("el JPEG no tiene cabecera SOF: no se pudo leer el tamaño")


def test_la_landing_esta_en_la_carpeta_publicada():
    assert HTML.stat().st_size > 500_000, "la landing quedó recortada"
    assert (CARPETA / "favicon.svg").exists()


def test_og_image_es_del_mismo_dominio_y_existe():
    img = _meta("og:image")
    assert img == URL + "og.jpg", f"og:image tiene que ser la del propio sitio: {img}"
    assert (CARPETA / "og.jpg").exists(), "la og:image declarada no está en la carpeta"
    assert _meta("twitter:image") == img, "twitter:image tiene que ser la misma imagen"


def test_og_image_mide_1200x630_y_es_jpeg_baseline():
    destino = CARPETA / "og.jpg"
    ancho, alto, marcador = _jpeg_medidas(destino.read_bytes())
    assert (ancho, alto) == (1200, 630), f"la tarjeta mide {ancho}x{alto}"
    assert marcador != SOF_PROGRESSIVE, "JPEG progresivo: algunos previsualizadores no lo dibujan"
    assert 40_000 < destino.stat().st_size < 400_000, "peso fuera de rango para una tarjeta"


def test_declara_el_alto_y_el_ancho():
    assert _meta("og:image:width") == "1200"
    assert _meta("og:image:height") == "630"
    assert _meta("og:image:type") == "image/jpeg"


def test_no_publica_notas_internas():
    """Una nota de cocina (qué modelo redactó, si había saldo) no va al material del cliente."""
    texto = _html()
    for prohibido in ("sin saldo", "redactó Claude", "en lugar de DeepSeek"):
        assert prohibido not in texto, f"la landing publicada filtra una nota interna: «{prohibido}»"


def test_nombra_a_alex_y_no_a_un_equipo_anonimo():
    """La página la lee Alex: se lo nombra. El candado evita que un HTML nuevo vuelva a la
    fórmula distante («el equipo SEO resolvió») sin que nadie lo note.

    Se lo nombra donde importa —la primera mención, el veredicto del 6-nov, el documento de
    ejemplo, el próximo paso y el cierre— y se deja «el SEO» como rol en el recorrido y en los
    comandos, que es donde repetir el nombre cansa.
    """
    texto = _html()
    assert texto.count("Alex") >= 8, f"la landing dejó de nombrar a Alex ({texto.count('Alex')} menciones)"
    assert "El equipo SEO resolvió" not in texto, "volvió la fórmula distante «el equipo SEO»"
    # El cierre es la frase exacta del bloque «Nada escrito en la tienda». El encabezado del
    # comando «Escribir de verdad (lo aprueba el SEO)» dice lo mismo pero es el rol en la lista de
    # comandos, y ahí el nombre sobra: se pide la frase entera, no el fragmento.
    assert "El primer lote real lo aprueba el SEO." not in texto, "el cierre volvió a decir «el SEO» en vez de Alex"
    assert "Que el SEO resuelva" not in texto, "el próximo paso volvió a decir «el SEO»"
    assert "el SEO" in texto, "se perdió el rol en el recorrido y en los comandos"
