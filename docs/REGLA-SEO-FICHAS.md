# Reglas de contenido SEO para fichas de producto

Fuente: documento del cliente (adjunto por Antonio, 18-sep-2026). Esta versión en el repo es la
spec canónica del agente; si el cliente actualiza el documento, se actualiza este archivo y se
ajustan `cassoni/reglas.py` (constantes) con sus tests.

## Inputs
- H1, categoría, marca, atributos técnicos
- Keywords ya usadas en otras fichas de la categoría

## Título (H1)
- Máximo 60 caracteres
- Marca (si aplica) + modelo + categoría completa
- Es la keyword principal, exacta

## Descripción corta (above the fold)
- Incluye la keyword principal exacta, tal cual el H1
- Sin cantidad de palabras fija, pero corta
- Una sola idea central, sin H2

## Descripción larga (below the fold)
- 150 a 300 palabras
- 1 o 2 H2 como máximo
- 2 o 3 keywords secundarias, repartidas entre H2 y párrafos
- Cada secundaria aparece como máximo 2 veces

## Investigación de secundarias
- Variantes por material, estilo, uso, sinónimo de categoría
- Específicas de este producto, no genéricas de toda la categoría

## Filtro anti canibalización
Descartar una keyword candidata si:
- Ya es la principal de otra ficha
- Compite con la página de categoría
- Responde mejor a un blog o guía de compra que a una ficha

## No hacer
- No inventar atributos que no están en los datos de input
- No copiar descripciones de competidores
- No repetir la misma secundaria en varias fichas sin chequear
- No forzar una keyword en una oración donde no encaja natural

## Ejemplos de referencia
- https://www.cantoni.com/product/belinda-side-chair
- https://www.bostoninteriors.com/belinda-side-chair
- https://www.2modern.com/products/twiggy-floor-lamp
- https://www.roomservice360.com/foscarini-twiggy-arc-floor-lamp.html

## Output por ficha
```
H1:
Descripción corta:
Descripción larga (H2 marcados):
Keywords secundarias + por qué son específicas:
Descartadas + a qué contenido pertenecen:
```