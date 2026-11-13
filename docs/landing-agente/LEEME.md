# Landing del agente SEO — la que se le manda al cliente

Publicada en **https://tarsterminal.duckdns.org/cassoni-agente-seo/** (v3, 13-nov-2026).

Es la página que se comparte por link con el equipo de Cassoni: qué cambió respecto de la v2 y por
qué, el recorrido de una ficha, y tres pruebas en seco — las 10 fichas del documento del SEO contra
el agente, 10 fichas nuevas elegidas al azar, y DeepSeek contra Claude en esas mismas 10. Cada
afirmación de la página sale de una corrida registrada, no de una descripción.

Reemplazó a la v2 del 4-nov. La v2 está guardada en la rama `agent/landing-agente` (commit 2867841)
y su copia servida se conserva en CASE como `index-v2.html`.

## Qué hay acá

| Archivo | Qué es |
|---|---|
| `index.html` | La landing v3, autocontenida (CSS, JS y las fotos de las fichas en base64). Es el archivo que se publica. |
| `og.jpg` | Tarjeta 1200×630 para que el link muestre imagen al compartirlo. |
| `favicon.svg` | Ícono de la pestaña. |
| `../../tools/marca/armar_landing.py` | Arma `index.html` desde el archivo que entrega Antonio: le pone las etiquetas de `<head>` (og:*, twitter:*, descripción, noindex, favicon) y cierra `<head>`/`<body>`, que el original no traía. No toca el contenido. |
| `../../tools/marca/og-landing.html` | Generador de la tarjeta: se abre en un navegador a 1200×630 y se captura. |

## Republicar

```
H=cassoni-agente-seo
cd docs/landing-agente
scp -i /root/.ssh/tars_key index.html og.jpg favicon.svg \
    root@100.76.81.111:/root/caddy/data/$H/
```

No hace falta tocar el Caddyfile: el handle ya existe. Para que el navegador no muestre una
versión vieja, el link se comparte con `?v=<algo>` la primera vez.

## Antes de compartirla afuera

- **Todas las corridas son en seco**: no se escribió nada en WooCommerce. La página lo dice en
  «Nada escrito en la tienda» y en el pie; si algún día se corre con `--write`, esa frase deja de
  ser cierta.
- **La columna de Claude es una simulación y la página lo dice**: la escribió Claude Opus 5.5 a mano
  en la sesión de trabajo y pasó por los controles en código y por el validador del agente como
  juez. La comparación con Claude por API no se hizo: falta la clave. Si el cliente pregunta por
  esa prueba, la respuesta es esa, no «está corrida».
- **El JSON embebido (`#datos`) viaja con el HTML** y se ve con «ver código fuente». No lleva claves
  ni datos personales, pero sí las fichas, las descripciones, los costos por corrida y los commits:
  antes de publicarla en un sitio público conviene revisar qué dice.
- **El enlace al repo** (`github.com/tonic1234/cassoni-product-flow`) está en el pie y es un repo
  público, pensado para auditoría externa. Si el cliente no tiene que ver el código, se saca del pie.

## Candado

`tests/test_og_landing.py` (dentro de `bash scripts/verify.sh`) falla si la og:image declarada no
existe en la carpeta, no mide 1200×630, es JPEG progresivo, o si la landing vuelve a publicar una
nota interna del proceso.
