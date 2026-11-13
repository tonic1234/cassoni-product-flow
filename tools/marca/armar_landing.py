# -*- coding: utf-8 -*-
"""Arma docs/landing-agente/index.html a partir del v3 que mandó Antonio.

Qué hace, exactamente (y nada más):
  1. mete en <head> las etiquetas que el archivo del v3 no traía (descripción, og:*,
     twitter:*, favicon, robots noindex) — sin ellas el link se comparte sin tarjeta;
  2. cierra <head> y abre/cierra <body>: el archivo venía sin esos cierres y el
     navegador los inventaba al encontrar el <nav>.

No toca el contenido de la página ni una palabra.
"""
import re
import sys
from pathlib import Path

URL = "https://tarsterminal.duckdns.org/cassoni-agente-seo/"
DESC = ("El equipo SEO resolvió 10 fichas a mano. El agente aprende de esas fichas y hace lo "
        "mismo con diez que nadie había mirado: tres pruebas en seco, las fichas lado a lado.")
TITULO = "Agente SEO Cassoni · v3 — lo que haría el SEO en cada ficha"

CABEZA = f"""<meta charset="utf-8">
<title>{TITULO}</title>
<meta name="description" content="{DESC}">
<meta name="robots" content="noindex">
<meta name="theme-color" content="#111014">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<meta property="og:type" content="website">
<meta property="og:site_name" content="cassoni · seo">
<meta property="og:locale" content="es_UY">
<meta property="og:url" content="{URL}">
<meta property="og:title" content="{TITULO}">
<meta property="og:description" content="{DESC}">
<meta property="og:image" content="{URL}og.jpg">
<meta property="og:image:type" content="image/jpeg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="Lo que haría el SEO, en cada ficha: diez fichas del SEO contra diez fichas nuevas">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{TITULO}">
<meta name="twitter:description" content="{DESC}">
<meta name="twitter:image" content="{URL}og.jpg">"""


def armar(origen: Path, destino: Path) -> None:
    s = origen.read_text(encoding="utf-8")

    # 1. cabecera: se reemplazan SOLO las etiquetas que ya están (viewport, charset,
    #    title, claude:viewport-fit-sides) y se agrega el bloque nuevo en su lugar.
    s, n = re.subn(r"<meta charset=\"utf-8\">\n<title>[^<]*</title>\n"
                   r"<meta name=\"claude:viewport-fit-sides\" content=\"cover\">",
                   CABEZA, s, count=1)
    assert n == 1, "no se encontró el bloque de cabecera esperado en el v3"

    # 2. cierres estructurales que el archivo no traía
    s, n = re.subn(r"</style>\n\n(<nav class=\"nav\")", r"</style>\n</head>\n<body>\n\n\1", s, count=1)
    assert n == 1, "no se encontró el fin del <style> antes del <nav>"
    assert s.rstrip().endswith("</script>"), "el archivo no termina en </script>"
    s = s.rstrip() + "\n</body>\n</html>\n"

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(s, encoding="utf-8")


if __name__ == "__main__":
    origen = Path(sys.argv[1] if len(sys.argv) > 1 else "/root/.hermes/cache/scratch/cassoni-seo-v3/cassoni-agente-seo-v3/cassoni-agente-seo-v3.html")
    destino = Path(sys.argv[2] if len(sys.argv) > 2 else "docs/landing-agente/index.html")
    armar(origen, destino)
    print(f"escrito {destino} · {destino.stat().st_size} bytes")
