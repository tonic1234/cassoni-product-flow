# Prueba ciega · observaciones registradas ANTES de ver la versión del SEO

Fecha: 11-nov-2026. Código congelado en `8e1ab82` (sin cambios sin commitear).
Corridas en seco sobre ese commit:

- `2026-11-11-ciega-10-fichas-8e1ab82.json`: 10 fichas nuevas, elegidas al azar
  (`2026-11-11-muestra-ciega.txt`, semilla 20261111).
- `2026-11-11-control-10-fichas-8e1ab82.json`: las 10 fichas de ajuste otra vez.

Estos son errores que encontró quien desarrolló el agente revisando su propia
salida. Se registran ahora para que no puedan "descubrirse" después, al ver la
versión del SEO. **No se corrigen hasta terminar la evaluación**: corregirlos
ahora rompería la prueba.

## Errores confirmados en código

1. **W017 Sideboard pierde el modelo.** `sin_codigos` borra "W017" porque parece
   un código de catálogo, pero es el único nombre del producto. El H1 queda
   "Sideboard with Mother-of-Pearl Inlay by Zanaboni". Criterio 3: un código que es
   el nombre del modelo tiene que quedar.
2. **Kin Suspension Lamp: tipo mal resuelto.** `tipo_ee_uu` devuelve "lamp"
   en vez de "pendant light" ("suspension" no está entre los prefijos de tipo). El H1
   queda "Kin Suspension Flared Cast Aluminum Lamp": el rasgo cae en el medio del
   tipo. Criterios 1 y 2.
3. **"mirror home" pasa en Tiffany Mirror (control).** La marca "DV Home
   Collection" tiene la palabra "home". `es_marca_y_modelo` lo toma como búsqueda
   de marca + modelo y `nucleo_al_final` la deja pasar. Criterios 4 y 5. (En la
   corrida de ajuste v3c el redactor la había omitido; en esta la usó).

## Dudas de criterio (que decida el evaluador)

- "large piano" (Steinway): "large" es un modificador neutro, pero la ficha no
  dice que sea grande.
- "Balloon Dog - White Diamond Hand-Painted Pop Art Sculpture": conserva el guion
  del nombre y suma 7 palabras.
- Rock Coffee Table, "with Bronzed Brass Legs": la tapa es de mármol o de madera
  y el agente no eligió ninguna de las dos.

## Variación entre corridas

Las corridas de ajuste v3c y de control usan casi el mismo código y no dan los
mismos H1 (Club: "Brushed Brass Sofa" contra "Brass Tube Sofa"; Shibari: "Tubular
Knot Armchair" contra "with Curved Tubular Metal Legs"). Dos causas: el LLM con
temperatura 0,4 y Google, que no devuelve siempre los mismos resultados. Por eso
se evalúa una sola corrida congelada, sin elegir la mejor de varias.
