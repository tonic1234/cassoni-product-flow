# Landing del agente SEO — la que se le manda al cliente

Publicada en **https://tarsterminal.duckdns.org/cassoni-agente-seo/**

Es la página que se comparte por link con el equipo de Cassoni: el recorrido de una ficha, las
keywords, lo que le funciona a la competencia, la medición a 14/28 días y la corrida en seco
sobre 10 fichas reales. Cada afirmación de la página sale del código que corre, no de una
descripción.

## Qué hay acá

| Archivo | Qué es |
|---|---|
| `index.html` | La landing, autocontenida (CSS, JS y las 10 fotos en base64). Es el archivo que se publica. |
| `og.jpg` | Tarjeta 1200×630 para que el link muestre imagen al compartirlo. |
| `favicon.svg` | Ícono de la pestaña. |
| `../../tools/marca/og-landing.html` | Generador de la tarjeta: se abre en un navegador a 1200×630 y se captura. |

## Republicar

```
H=cassoni-agente-seo
scp -i /root/.ssh/tars_key index.html og.jpg favicon.svg \
    root@100.76.81.111:/root/caddy/data/$H/
```

No hace falta tocar el Caddyfile: el handle ya existe. Para que el navegador no muestre una
versión vieja, el link se comparte con `?v=<algo>` la primera vez.

## Antes de compartirla afuera

- **La corrida es en seco**: no se escribió nada en WooCommerce. La página lo dice en la sección
  «Prueba real» y en el pie; si algún día se corre con `--write`, esa frase deja de ser cierta.
- **El JSON embebido (`#revision-data`) viaja con el HTML** y se ve con «ver código fuente». No
  lleva claves ni datos personales, pero sí las fichas y los costos de la corrida: antes de
  publicarla en un sitio público conviene revisar qué dice.
- **El enlace al repo** (`github.com/tonic1234/cassoni-product-flow`) está en el pie y es un repo
  público, pensado para auditoría externa. Si el cliente no tiene que ver el código, se saca del pie.

## Candado

`tests/test_og_landing.py` (dentro de `bash scripts/verify.sh`) falla si la og:image declarada no
existe en la carpeta, no mide 1200×630, es JPEG progresivo, o si la landing vuelve a publicar una
nota interna del proceso.
