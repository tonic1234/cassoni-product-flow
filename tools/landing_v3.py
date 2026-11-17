# -*- coding: utf-8 -*-
"""Landing v3: el agente que imita al SEO, con todos los resultados del 13-nov.
Usa el CSS de la landing v2 (docs/landing/index.html) y le suma las secciones nuevas.

    python tools/landing_v3.py \\
        --vs-seo evidencia/2026-11-13-control-v41-vs-seo.json \\
        --vs-seo-base evidencia/2026-11-13-control-v32-vs-seo.json \\
        --nuevas evidencia/2026-11-13-tanda-v41.json \\
        --out docs/landing-v3/index.html
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CSS_EXTRA = r"""
/* v3 */
.cmp { display: grid; gap: 1px; background: var(--paper-2); border: 1px solid var(--paper-2); border-radius: var(--radius); overflow: hidden; }
.cmp-row { display: grid; grid-template-columns: minmax(0, 1.6fr) repeat(3, minmax(0, 1fr)); background: #fff; }
.cmp-row > div { padding: 14px 16px; font-size: 15px; }
.cmp-row.h > div { font-family: var(--mono); font-size: 11px; letter-spacing: .1em; text-transform: uppercase; color: var(--paper-mute); background: #FAF9FB; }
.cmp-row .n { font-family: var(--mono); font-variant-numeric: tabular-nums; color: var(--paper-mute); }
.cmp-row .n.now { color: var(--violet-deep); font-weight: 600; }
@media (max-width: 640px) { .cmp-row { grid-template-columns: minmax(0, 1.4fr) repeat(3, minmax(0, .8fr)); } .cmp-row > div { padding: 12px 10px; font-size: 13px; } }
.par { display: grid; gap: 14px; }
.par-item { background: #fff; border: 1px solid var(--paper-2); border-radius: 16px; padding: clamp(16px, 2.6vw, 24px); display: grid; gap: 12px; min-width: 0; }
.par-top { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px 14px; align-items: baseline; }
.par-top h3 { color: var(--paper-fg); }
.par-top span { font-family: var(--mono); font-size: 12px; color: var(--paper-mute); }
.duo { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.duo > div { min-width: 0; display: grid; gap: 8px; align-content: start; padding: 12px 14px; border-radius: 12px; background: #F7F6F9; }
.duo .who { font-family: var(--mono); font-size: 11px; letter-spacing: .12em; text-transform: uppercase; color: var(--paper-mute); }
.duo .who.ag { color: var(--violet-deep); }
.duo .t { font-family: var(--display); font-size: 18px; line-height: 1.2; color: var(--paper-fg); overflow-wrap: anywhere; }
.duo .t .igual { font-family: var(--body); font-size: 11px; font-weight: 700; color: #1E6B47; background: #DDF3E8; border-radius: 999px; padding: 2px 8px; margin-left: 6px; vertical-align: 3px; white-space: nowrap; }
.pill { display: inline-block; font-family: var(--mono); font-size: 12px; padding: 3px 8px; border-radius: 6px; border: 1px solid var(--paper-2); color: var(--paper-mute); margin: 0 4px 4px 0; background: #fff; }
.pill.hit { background: #DDF3E8; color: #1E6B47; border-color: transparent; font-weight: 600; }
@media (max-width: 680px) { .duo { grid-template-columns: 1fr; } }
.duo-desc { font-size: 14px; line-height: 1.65; border-left: 0; padding-left: 0; padding-top: 10px; border-top: 1px solid var(--paper-2); gap: 8px; }
.duo-desc h2 { font-size: 15px; }
.palabras { font-family: var(--mono); font-size: 11px; color: var(--paper-mute); }
.aprende { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; background: var(--line); border: 1px solid var(--line); border-radius: 20px; overflow: hidden; }
.aprende > div { background: var(--ink); padding: 26px; display: grid; gap: 10px; align-content: start; }
.aprende p { color: var(--mute); font-size: 15px; }
.aprende .n { font-family: var(--mono); font-size: 12px; color: var(--violet); letter-spacing: .1em; }
@media (max-width: 860px) { .aprende { grid-template-columns: 1fr; } }
.par-item { grid-template-columns: 132px minmax(0, 1fr); align-items: start; column-gap: 18px; }
.par-item > .par-foto { grid-row: span 2; }
.par-foto { display: block; aspect-ratio: 1; border-radius: 12px; overflow: hidden; background: #F3F1F6; }
.par-foto img { width: 100%; height: 100%; object-fit: cover; display: block; }
.par-foto span { display: grid; place-items: center; height: 100%; font-family: var(--mono); font-size: 11px; color: var(--paper-mute); }
@media (max-width: 680px) { .par-item { grid-template-columns: 84px minmax(0, 1fr); } .par-item > .duo { grid-column: 1 / -1; } .par-item > .par-foto { grid-row: auto; } }
a.ficha-foto { text-decoration: none; }
.ficha-foto img { aspect-ratio: 1; }
.kw .org.gsc { background: rgba(255,255,255,.14); }
.kw .org.gen { background: var(--ok); color: var(--paper-fg); }
.desc h2, .desc .bh2 { font-family: var(--display); font-size: 17px; font-weight: 500; margin: 4px 0 0; letter-spacing: 0; }
.desc p { margin: 0; max-width: none; }
.desc ul { margin: 0; padding-left: 18px; }
.desc a { color: var(--violet-deep); }
.desc mark { background: linear-gradient(transparent 55%, #E3D0FF 55%); color: inherit; }
.pend { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.pend > div { border: 1px solid var(--line); border-radius: 14px; padding: 18px; display: grid; gap: 6px; }
.pend b { font-family: var(--display); font-weight: 500; font-size: 18px; }
.pend span { color: var(--mute); font-size: 15px; }
@media (max-width: 720px) { .pend { grid-template-columns: 1fr; } }
"""

BODY = r"""
<nav class="nav" aria-label="Secciones">
  <a class="brand" href="#top">cassoni<b>·</b>seo <span style="font-size:13px;color:var(--mute)">v3</span></a>
  <ul>
    <li><a class="l" href="#cambios">Qué cambió</a></li>
    <li><a class="l" href="#flujo">Flujo</a></li>
    <li><a class="l" href="#vs-seo">Agente vs SEO</a></li>
    <li><a class="l" href="#nuevas">10 fichas nuevas</a></li>
    <li><a class="l" href="#modelos">Modelos</a></li>
    <li><a class="l" href="#garantias">Garantías</a></li>
  </ul>
</nav>

<header class="band hero" id="top">
  <div class="wrap">
    <span class="eyebrow">Agente SEO · fichas de producto · v3 · 13-nov-2026</span>
    <h1>Lo que haría el SEO,<br><span class="v">en cada ficha.</span></h1>
    <p class="lead">El equipo SEO resolvió 10 fichas a mano: el H1, las palabras clave y la descripción. El agente aprende de esas fichas para hacer lo mismo en las otras 13.000. Esta página muestra cómo, cuánto se parece hoy a lo del SEO y cómo queda en diez fichas que nadie había mirado.</p>
    <div class="btns">
      <a class="btn primary" href="#vs-seo"><span>Agente vs SEO</span><i aria-hidden="true">↘</i></a>
      <a class="btn ghost" href="#nuevas"><span>Diez fichas nuevas</span><i aria-hidden="true">↘</i></a>
    </div>
    <div class="hero-meta" id="hero-stats"></div>
  </div>
  <canvas id="waves" aria-hidden="true"></canvas>
</header>

<section class="band paper" id="cambios">
  <div class="wrap">
    <div class="head">
      <span class="eyebrow">Desde la v2</span>
      <h2>Qué cambió <span class="v">y por qué.</span></h2>
      <p class="lead">La v2 sumaba una oración por keyword a la descripción y elegía las palabras por volumen. El SEO la calificó el 6-nov (2 Crítico, 4 Mal, 3 Aceptable, 1 Bien) y mandó cómo lo haría él en cada ficha. La v3 sigue ese documento.</p>
    </div>
    <div class="ftable reveal"><div class="ftable-scroll"><table>
      <thead><tr><th></th><th>v2 (4-nov)</th><th>v3 (13-nov)</th></tr></thead>
      <tbody>
        <tr><td><b>H1</b></td><td>{Nombre} by {Marca}</td><td>{Nombre} + {rasgo real} + {tipo en inglés de EE. UU.} + by {Marca}</td></tr>
        <tr><td><b>Descripción</b></td><td>La original + una oración por keyword</td><td>Reescrita con la estructura del SEO: apertura, 2 secciones, un dato para decidir la compra, medidas en pulgadas</td></tr>
        <tr><td><b>Keywords</b></td><td>Por volumen (50+/mes), competencia e investigación</td><td>Como el SEO: variantes del nombre que ya traen impresiones, marca + tipo y una genérica corta</td></tr>
        <tr><td><b>Quién decide</b></td><td>Reglas fijas</td><td>Un modelo que ve las elecciones reales del SEO como ejemplo, con controles en código</td></tr>
        <tr><td><b>Largo</b></td><td>Lo que tenía + ~15%</td><td>60 a 110 palabras, como las del SEO</td></tr>
      </tbody>
    </table></div></div>
  </div>
</section>

<section class="band" id="flujo">
  <div class="wrap">
    <div class="head">
      <span class="eyebrow">De punta a punta</span>
      <h2>El recorrido de <span class="v">una ficha.</span></h2>
      <p class="lead">Cada ficha de la lista pasa por el mismo camino. Si algo falla, queda registrada con el motivo y el lote sigue.</p>
    </div>
    <div class="steps">
      <div class="step reveal"><span class="n">01 · FICHA</span><h3>Lee WooCommerce</h3><p>Nombre, marca, ruta de categorías, atributos y descripción. Todo dato que se escribe sale de acá.</p></div>
      <div class="step reveal"><span class="n">02 · TIPO</span><h3>Qué es, en inglés de EE. UU.</h3><p>Del nombre y la categoría: <code>wall sconce</code>, <code>bar stool</code>, <code>foosball table</code>. Lo decide el código, no el modelo.</p></div>
      <div class="step reveal"><span class="n">03 · CANDIDATAS</span><h3>Lo que ya atrae + genéricas</h3><p>Búsquedas de Search Console por las que la ficha ya aparece (posición ≤ 30), y genéricas armadas con sus materiales y su marca, con volumen de DataForSEO.</p></div>
      <div class="step reveal"><span class="n">04 · ELECCIÓN</span><h3>1 a 3, como el SEO</h3><p>Un modelo elige viendo qué eligió el SEO en sus fichas. Solo puede elegir de la lista; el código descarta tipeos, otro idioma, precio y contenido sensible.</p></div>
      <div class="step reveal"><span class="n">05 · REDACCIÓN</span><h3>H1 y descripción</h3><p>Con las descripciones del SEO como ejemplo de estructura, tono y largo. Los números se controlan en código contra la ficha.</p></div>
      <div class="step reveal"><span class="n">06 · VALIDACIÓN</span><h3>Código y un segundo modelo</h3><p>Keyword exacta, 1–2 secciones, un solo enlace a la categoría, nada inventado, sin frases de relleno. Hasta 3 intentos con los motivos.</p></div>
      <div class="step reveal"><span class="n">07 · ESCRITURA</span><h3>Solo si aprueba</h3><p>Con <code>--write</code> y aprobada, escribe <code>name</code> y <code>description</code>. Sin <code>--write</code>, todo corre en seco.</p></div>
      <div class="step reveal"><span class="n">08 · RITMO</span><h3>Diez por día</h3><p>De la lista del SEO, en horario hábil y con pausas, para no editar en masa.</p></div>
      <div class="step reveal"><span class="n">09 · MEDICIÓN</span><h3>Cada keyword, a 14 y 28 días</h3><p>Los mismos días antes y después de la edición, para cada palabra.</p></div>
    </div>
  </div>
</section>

<section class="band">
  <div class="wrap">
    <div class="head">
      <span class="eyebrow">Cómo aprende</span>
      <h2>Diez fichas del SEO,<br><span class="v">probadas sin ver la respuesta.</span></h2>
      <p class="lead">Si el agente viera la respuesta del SEO para la ficha que está procesando, la copiaría y la prueba no diría nada sobre el resto del catálogo. Por eso cada ficha se procesa viendo solo las otras nueve.</p>
    </div>
    <div class="aprende">
      <div class="reveal"><span class="n">EL DOCUMENTO</span><h3>Lo que hizo el SEO</h3><p>Para 10 fichas: H1, 1 a 3 keywords y la descripción completa. Además, para cada una, qué falló en la versión anterior del agente.</p></div>
      <div class="reveal"><span class="n">LOS EJEMPLOS</span><h3>Nueve por ficha</h3><p>Al procesar Cruise Sofa, el agente ve cómo el SEO resolvió las otras nueve, nunca Cruise Sofa. Es la misma situación que una ficha nueva del catálogo.</p></div>
      <div class="reveal"><span class="n">LA MEDICIÓN</span><h3>Comparado palabra por palabra</h3><p>H1 idéntico o no, keywords en común (plural y posesivo cuentan igual), estructura y largo de la descripción.</p></div>
    </div>
  </div>
</section>

<section class="band paper" id="vs-seo">
  <div class="wrap">
    <div class="head">
      <span class="eyebrow">Prueba 1 · las 10 fichas del documento del SEO</span>
      <h2>Agente vs SEO,<br><span class="v">en las mismas fichas.</span></h2>
      <p class="lead" id="vs-lead"></p>
    </div>
    <div class="cmp reveal" id="cmp" role="table" aria-label="Parecido con el SEO por versión"></div>
    <p class="note" style="margin-top:22px;color:var(--paper-mute);border-color:var(--violet-deep)" id="nota-v2"></p>
    <p class="lead" style="margin:28px 0 22px">En verde, lo que eligieron los dos.</p>
    <div class="par" id="par"></div>
  </div>
</section>

<section class="band paper" id="nuevas" style="padding-top:0">
  <div class="wrap">
    <div class="head">
      <span class="eyebrow">Prueba 2 · diez fichas que nadie había mirado</span>
      <h2>Diez fichas nuevas,<br><span class="v">elegidas por código.</span></h2>
      <p class="lead" id="nuevas-lead"></p>
    </div>
    <div class="resumen" id="nuevas-stats"></div>
    <div class="fichas" id="fichas"></div>
  </div>
</section>

<section class="band paper" id="modelos" style="padding-top:0">
  <div class="wrap">
    <div class="head">
      <span class="eyebrow">Prueba 3 · el mismo trabajo, otro modelo</span>
      <h2>DeepSeek vs Claude,<br><span class="v">en las diez fichas nuevas.</span></h2>
      <p class="lead">Las mismas entradas (datos de la ficha, candidatas y ejemplos del SEO) y los mismos controles. Lo de DeepSeek es la corrida del agente; lo de Claude es una simulación: lo escribió Claude Opus 5.5 en la sesión de trabajo, a mano, y pasó por los controles en código y por el validador del agente como juez. La prueba con Claude Sonnet 5.5 por API se hace cuando esté la clave.</p>
    </div>
    <div class="cmp reveal" id="cmp-mod" role="table" aria-label="DeepSeek contra Claude"></div>
    <div class="pend" style="margin:22px 0 28px" id="mod-notas"></div>
    <p class="lead" style="margin:0 0 22px">En verde, las keywords que eligieron los dos.</p>
    <div class="par" id="par-mod"></div>
  </div>
</section>

<section class="band" id="pendiente">
  <div class="wrap">
    <div class="head">
      <span class="eyebrow">Dónde estamos</span>
      <h2>Lo que ya está,<br><span class="v">y lo que falta.</span></h2>
    </div>
    <div class="pend">
      <div class="reveal"><b>H1 y estructura: listos</b><span>La fórmula y la plantilla de la descripción ya son las del SEO. Cuando el H1 difiere, suele ser en una palabra de rasgo.</span></div>
      <div class="reveal"><b>Keywords: lo que más falta</b><span>Coincide en 7 de las 22 del SEO, una menos que la v2, de la que el SEO partió para armar su lista. Hay criterios que no están escritos y conviene que el SEO los confirme.</span></div>
      <div class="reveal"><b>Próximo paso</b><span>Que el SEO resuelva 10 fichas más con el mismo formato. Sirven como ejemplos nuevos y como segunda prueba.</span></div>
      <div class="reveal"><b>Nada escrito en la tienda</b><span>Todas las corridas son en seco. El primer lote real lo aprueba el SEO.</span></div>
    </div>
  </div>
</section>

<section class="band" id="garantias" style="padding-top:0">
  <div class="wrap">
    <div class="head">
      <span class="eyebrow">Garantías</span>
      <h2>Lo que hace,<br><span class="v">y lo que nunca.</span></h2>
    </div>
    <div class="vs">
      <div>
        <h3>Nunca</h3>
        <p>Escribir en la tienda sin <code>--write</code> y sin aprobación.</p>
        <p>Editar dos veces la misma ficha sin que se le pida.</p>
        <p>Inventar medidas, materiales, diseñadores o colecciones.</p>
        <p>Elegir una keyword que no esté en la lista de candidatas.</p>
        <p>Copiar texto de la competencia o de las fichas del SEO.</p>
        <p>Tocar la descripción corta, los metadatos o los ALT, que son de n8n.</p>
        <p>Escribir en Search Console.</p>
      </div>
      <div>
        <h3>Siempre</h3>
        <p>Corre en seco por defecto.</p>
        <p>Deja cada ficha con su estado, su motivo y lo que descartó.</p>
        <p>Controla en código cada número de la descripción contra la ficha.</p>
        <p>Pone un solo enlace, a la categoría de la ficha.</p>
        <p>Escribe solo <code>name</code> y <code>description</code>.</p>
        <p>Lee GSC con permiso de solo lectura.</p>
      </div>
    </div>
  </div>
</section>

<section class="band" style="padding-top:0">
  <div class="wrap">
    <div class="head">
      <span class="eyebrow">Para repetirlo</span>
      <h2>Cuatro comandos.</h2>
    </div>
    <div class="cmds">
      <div class="cmd"><header><span>Armar los ejemplos desde el documento del SEO</span></header><pre>python tools/armar_referencia_seo.py --seo evidencia/2026-11-06-seo-referencia-descripciones.json --out evidencia/referencia-seo.json</pre></div>
      <div class="cmd"><header><span>Correr un lote en seco</span></header><pre>python tools/correr_lote.py --urls lista.txt --out evidencia/lote.json</pre></div>
      <div class="cmd"><header><span>Medir el parecido con el SEO</span></header><pre>python tools/evaluar_vs_seo.py --lote evidencia/lote.json --out evidencia/lote-vs-seo.json</pre></div>
      <div class="cmd"><header><span>Escribir de verdad (lo aprueba el SEO)</span></header><pre>python -m cassoni.cli --env prod --urls lista.txt --write --scheduler</pre></div>
    </div>
  </div>
</section>

<footer><div class="wrap"><span>Agente SEO Cassoni · v3</span><span id="pie"></span></div></footer>

<script type="application/json" id="datos">__DATOS__</script>
<script>
(function(){
  document.documentElement.classList.add("js");
  const D = JSON.parse(document.getElementById("datos").textContent);
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const fmt = n => n == null ? "s/d" : Number(n).toLocaleString("es-AR");
  const pct = x => Math.round(x * 100) + "%";
  const clave = k => k.toLowerCase().replace(/&/g," and ").replace(/['’]s\b/g,"").replace(/[^a-z0-9 ]/g," ").split(/\s+/).filter(Boolean).map(w => w.length>3 && w.endsWith("s") && !w.endsWith("ss") ? w.slice(0,-1) : w).join(" ");
  const A = D.vs.resumen, B = D.base.resumen, N = D.nuevas;

  // hero
  const aprob = N.fichas.filter(f => f.status === "processed").length;
  const conKw = N.fichas.filter(f => (f.keywords || []).length).length;
  const costo = ((N.meta.costos.usd || 0) + (N.meta.costos.dfs_usd || 0)) / N.fichas.length;
  $("#hero-stats").innerHTML = [
    [`${A.h1_iguales}/10`, "H1 idénticos al del SEO"],
    [`${A.keywords_en_comun}/${A.keywords_seo}`, "keywords en común con el SEO"],
    [`${aprob}/10`, "fichas nuevas aprobadas"],
    [`US$ ${costo.toFixed(2)}`, "por ficha"]
  ].map(s => `<div class="stat"><b>${s[0]}</b><small>${s[1]}</small></div>`).join("");

  // prueba 1
  $("#vs-lead").textContent = `Tres versiones del agente sobre las 10 fichas que resolvió el SEO. La v2 es la que el SEO calificó el 6-nov; la v3.2, la primera corrección; la v4.1, la que imita su documento.`;
  const filas = [
    ["H1 idéntico al del SEO", `${D.v2.h1_iguales} de 10`, `${B.h1_iguales} de 10`, `${A.h1_iguales} de 10`],
    ["Palabras del H1 en común", "—", pct(B.h1_parecido_promedio), pct(A.h1_parecido_promedio)],
    ["Keywords del SEO que eligió el agente", `${D.v2.keywords_en_comun} de 22`, `${B.keywords_en_comun} de 22`, `${A.keywords_en_comun} de 22`],
    [`Palabras de la descripción (SEO: ${A.palabras_seo_prom})`, "—", B.palabras_agente_prom, A.palabras_agente_prom],
    ["Aprobadas por el validador", "—", `${B.aprobadas} de 10`, `${A.aprobadas} de 10`]
  ];
  $("#cmp").innerHTML = `<div class="cmp-row h" role="row"><div>Medida</div><div>v2</div><div>v3.2</div><div>v4.1</div></div>` +
    filas.map(f => `<div class="cmp-row" role="row"><div>${esc(f[0])}</div><div class="n">${esc(f[1])}</div><div class="n">${esc(f[2])}</div><div class="n now">${esc(f[3])}</div></div>`).join("");
  $("#nota-v2").textContent = `Sobre las keywords: el SEO armó su lista partiendo de la que le propuso la v2. Conservó ${D.v2.keywords_en_comun} de sus keywords (incluso «wood table» y «marble table», que en su devolución marcó como búsquedas de categoría) y sumó variantes del nombre y marca + tipo. Por eso la v2 coincide tanto. La v4.1 acierta en ${A.keywords_en_comun}, sobre todo en lo que el SEO sumó. Lo que la v2 hacía mal era meter cada keyword con una oración forzada, y eso ya no pasa.`;
  const foto = (url, alt, cls) => {
    const src = (D.fotos || {})[url] || "";
    return `<a class="${cls}" href="${esc(url)}" target="_blank" rel="noopener" title="Ver en cassoni.com">${src ? `<img src="${src}" alt="${esc(alt)}" loading="lazy">` : "<span>sin foto</span>"}</a>`;
  };
  const pills = (lista, otras) => { const c = new Set(otras.map(clave)); return lista.length ? lista.map(k => `<span class="pill ${c.has(clave(k)) ? "hit" : ""}">${esc(k)}</span>`).join("") : `<span class="pill">ninguna</span>`; };
  $("#par").innerHTML = D.vs.fichas.map(f => `
    <article class="par-item reveal">
      ${foto(f.url, f.nombre, "par-foto")}
      <div class="par-top"><h3>${esc(f.nombre)}</h3><span>${f.kw_en_comun.length}/${f.kw_seo.length} keywords en común · ${f.palabras_agente} vs ${f.palabras_seo} palabras</span></div>
      <div class="duo">
        <div><span class="who">SEO</span><div class="t">${esc(f.h1_seo)}</div><div>${pills(f.kw_seo, f.kw_agente)}</div>
          <div class="desc duo-desc">${limpio(textoSEO(f.descripcion_seo), f.kw_seo)}</div><span class="palabras">${f.palabras_seo} palabras</span></div>
        <div><span class="who ag">Agente v4.1</span><div class="t">${esc(f.h1_agente)}${f.h1_igual ? '<span class="igual">igual</span>' : ""}</div><div>${pills(f.kw_agente, f.kw_seo)}</div>
          <div class="desc duo-desc">${limpio(f.descripcion_agente, f.kw_agente)}</div><span class="palabras">${f.palabras_agente} palabras</span></div>
      </div>
    </article>`).join("");

  // prueba 2
  $("#nuevas-lead").textContent = `Elegidas al azar (semilla ${D.semilla}) entre las ${fmt(D.universo)} fichas con al menos 50 impresiones en Google, una por familia, sin repetir ninguna de las 30 que ya se usaron. Ninguna está en el documento del SEO: el agente las resolvió con los 10 ejemplos.`;
  const kwN = N.fichas.reduce((a, f) => a + (f.keywords || []).length, 0);
  $("#nuevas-stats").innerHTML = [
    [`${aprob} de 10`, "aprobadas por el validador"],
    [`${conKw} de 10`, "con keywords"],
    [kwN, "keywords en total"],
    [`US$ ${costo.toFixed(3)}`, "costo por ficha"]
  ].map(s => `<div class="stat"><b>${s[0]}</b><small>${s[1]}</small></div>`).join("");

  // texto del documento del SEO: títulos en MAYÚSCULAS, viñetas con •
  function textoSEO(t){
    const out = []; let lista = [];
    const cerrar = () => { if (lista.length){ out.push("<ul>" + lista.map(x => `<li>${esc(x)}</li>`).join("") + "</ul>"); lista = []; } };
    (t || "").split(/\r?\n/).map(l => l.trim()).filter(Boolean).forEach(l => {
      if (l.startsWith("•")) { lista.push(l.replace(/^•\s*/, "")); return; }
      cerrar();
      out.push(l === l.toUpperCase() && /[A-Z]/.test(l) ? `<h2>${esc(l)}</h2>` : `<p>${esc(l)}</p>`);
    });
    cerrar(); return out.join("");
  }
  function limpio(html, kws){
    const t = document.createElement("template"); t.innerHTML = html || "";
    const OK = new Set(["P","H2","UL","LI","STRONG","EM","A","BR"]);
    (function rec(n){ [...n.childNodes].forEach(c => {
      if (c.nodeType === 1){ if (!OK.has(c.tagName)){ rec(c); c.replaceWith(...c.childNodes); return; }
        [...c.attributes].forEach(a => { if (!(c.tagName === "A" && a.name === "href")) c.removeAttribute(a.name); });
        if (c.tagName === "A"){ const h = c.getAttribute("href") || ""; if (!/^https:\/\//.test(h)) c.removeAttribute("href"); else { c.target = "_blank"; c.rel = "noopener"; } }
        rec(c); } else if (c.nodeType !== 3) c.remove(); }); })(t.content);
    if (kws.length){
      const rx = new RegExp("(" + kws.map(k => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).sort((a,b) => b.length - a.length).join("|") + ")", "gi");
      const w = document.createTreeWalker(t.content, NodeFilter.SHOW_TEXT); const ns = []; while (w.nextNode()) ns.push(w.currentNode);
      ns.forEach(n => { if (!rx.test(n.nodeValue)) return; rx.lastIndex = 0; const s = document.createElement("span"); s.innerHTML = esc(n.nodeValue).replace(rx, "<mark>$1</mark>"); n.replaceWith(...s.childNodes); });
    }
    const d = document.createElement("div"); d.append(t.content); return d.innerHTML;
  }
  $("#fichas").innerHTML = N.fichas.map(f => {
    const ok = f.status === "processed";
    const kws = f.keywords_detalle || [];
    const v = f.validacion || {};
    const kwHtml = kws.length ? kws.map(k => `<span class="kw"><span>${esc(k.keyword)}</span><small>${k.origen === "gsc" ? fmt(k.impresiones || k.impressions) + " impr." : fmt(k.volumen || k.volume) + "/mes"}</small><span class="org ${k.origen === "gsc" ? "gsc" : "gen"}">${k.origen === "gsc" ? "ya aparece" : "genérica"}</span></span>`).join("")
      : `<span class="aporte"><span class="cero">Ninguna candidata cumplió el criterio: queda con H1 y descripción nuevos</span></span>`;
    return `<article class="ficha reveal">
      ${foto(f.url, f.h1_original, "ficha-foto")}
      <div class="ficha-cuerpo">
        <div class="ficha-top"><a class="meta" href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.url.replace("https://cassoni.com/product/", ""))}</a>
          <span class="estado ${ok ? "ok" : "no"}">${ok ? "Aprobada" : (f.status === "failed" ? "Falló" : "Rechazada")}</span></div>
        <div class="h1-cambio"><span class="antes">${esc(f.h1_original)}</span><span class="despues">${esc(f.h1 || "—")}</span></div>
        <div class="kws">${kwHtml}</div>
        ${f.descripcion ? `<div class="desc">${limpio(f.descripcion, kws.map(k => k.keyword))}</div>` : ""}
        ${!ok ? `<p style="font-size:14px;color:var(--paper-mute)"><b>Motivo:</b> ${esc((v.issues || []).join(" ") || f.reason)}</p>` : ""}
        <details><summary>Descripción original</summary><div class="desc" style="margin-top:10px;opacity:.75">${limpio(f.descripcion_original, [])}</div></details>
      </div></article>`;
  }).join("");


  // prueba 3: modelos
  if (D.sim && D.sim.fichas) {
    const S = D.sim.fichas, porUrl = Object.fromEntries(S.map(f => [f.url, f]));
    const pares = N.fichas.filter(f => porUrl[f.url]).map(f => [f, porUrl[f.url]]);
    const ok = arr => arr.filter(f => f.status === "processed").length;
    const nkw = arr => arr.reduce((x, f) => x + (f.keywords || []).length, 0);
    const conkw = arr => arr.filter(f => (f.keywords || []).length).length;
    const prom = arr => Math.round(arr.reduce((x, f) => x + (f.palabras || 0), 0) / Math.max(arr.length, 1));
    const comunes = pares.reduce((x, [d, c]) => { const k = new Set((c.keywords || []).map(clave)); return x + (d.keywords || []).filter(w => k.has(clave(w))).length; }, 0);
    const h1iguales = pares.filter(([d, c]) => d.h1 === c.h1).length;
    const ds = pares.map(p => p[0]), cl = pares.map(p => p[1]);
    const segundo = cl.filter(f => (f.intentos || 1) > 1).length;
    const filasM = [
      ["Aprobadas (código + validador)", `${ok(ds)} de ${ds.length}`, `${ok(cl)} de ${cl.length}` + (segundo ? ` (${segundo} al 2.º intento)` : "")],
      ["Fichas con keywords", `${conkw(ds)} de ${ds.length}`, `${conkw(cl)} de ${cl.length}`],
      ["Keywords en total", nkw(ds), nkw(cl)],
      ["Palabras por descripción", prom(ds), prom(cl)],
      ["Costo de redacción por ficha", `US$ ${((N.meta.costos.usd || 0) / Math.max(ds.length, 1)).toFixed(3)}`, "se mide con la API"],
    ];
    $("#cmp-mod").innerHTML = `<div class="cmp-row h" role="row" style="grid-template-columns:minmax(0,1.6fr) repeat(2,minmax(0,1fr))"><div>Medida</div><div>DeepSeek</div><div>Claude (simulación)</div></div>` +
      filasM.map(f => `<div class="cmp-row" role="row" style="grid-template-columns:minmax(0,1.6fr) repeat(2,minmax(0,1fr))"><div>${esc(f[0])}</div><div class="n">${esc(f[1])}</div><div class="n now">${esc(f[2])}</div></div>`).join("");
    $("#mod-notas").innerHTML = [
      ["Coinciden en la mitad", `Eligen ${comunes} keywords iguales y el mismo H1 en ${h1iguales} de ${pares.length} fichas. Las dos versiones siguen la estructura del SEO.`],
      ["Dónde difieren", "Claude no eligió keywords que la ficha no respalda: dejó Ciclotte sin keywords, mientras DeepSeek usó «professional exercise bike». En Palatial evitó «marble table» (esta versión no tiene mármol) y «palatial furniture»."],
    ].concat(D.sim_notas || []).map(n => `<div class="reveal" style="border-color:var(--paper-2)"><b style="color:var(--paper-fg)">${esc(n[0])}</b><span style="color:var(--paper-mute)">${esc(n[1])}</span></div>`).join("");
    $("#par-mod").innerHTML = pares.map(([d, c]) => `
      <article class="par-item reveal">
        ${foto(d.url, d.h1_original, "par-foto")}
        <div class="par-top"><h3>${esc(d.h1_original)}</h3><span>${d.palabras} vs ${c.palabras} palabras${(c.intentos || 1) > 1 ? " · Claude al 2.º intento" : ""}</span></div>
        <div class="duo">
          <div><span class="who">DeepSeek</span><div class="t">${esc(d.h1)}${d.h1 === c.h1 ? '<span class="igual">igual</span>' : ""}</div><div>${pills(d.keywords || [], c.keywords || [])}</div>
            <div class="desc duo-desc">${limpio(d.descripcion, d.keywords || [])}</div></div>
          <div><span class="who ag">Claude (simulación)</span><div class="t">${esc(c.h1)}</div><div>${pills(c.keywords || [], d.keywords || [])}</div>
            <div class="desc duo-desc">${limpio(c.descripcion, c.keywords || [])}</div></div>
        </div>
      </article>`).join("");
  }
  $("#pie").textContent = D.pie;

  // revelado
  if (!matchMedia("(prefers-reduced-motion: reduce)").matches && "IntersectionObserver" in window){
    const els = document.querySelectorAll(".reveal");
    const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting){ e.target.classList.remove("pre"); io.unobserve(e.target); } }), {rootMargin: "0px 0px -8% 0px"});
    els.forEach(el => { const r = el.getBoundingClientRect(); if (r.top > innerHeight) { el.classList.add("pre"); io.observe(el); } });
  }
  // ondas del hero
  const cv = document.getElementById("waves");
  if (cv && cv.getContext){
    const ctx = cv.getContext("2d"); let t = 0;
    const quieto = matchMedia("(prefers-reduced-motion: reduce)").matches;
    function draw(){
      const w = cv.clientWidth, h = cv.clientHeight, dpr = Math.min(devicePixelRatio || 1, 2);
      if (cv.width !== w * dpr){ cv.width = w * dpr; cv.height = h * dpr; }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, w, h);
      for (let i = 0; i < 18; i++){
        ctx.beginPath();
        for (let x = 0; x <= w; x += 8){
          const y = h * .55 + Math.sin(x * .006 + t + i * .35) * (18 + i * 2.2) + Math.cos(x * .002 - t * .6 + i) * 22;
          x ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
        }
        ctx.strokeStyle = `rgba(174,98,255,${.05 + i * .018})`; ctx.lineWidth = 1; ctx.stroke();
      }
      if (!quieto){ t += .006; requestAnimationFrame(draw); }
    }
    draw();
  }
})();
</script>
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vs-seo", required=True)
    ap.add_argument("--vs-seo-base", required=True)
    ap.add_argument("--nuevas", required=True)
    ap.add_argument("--muestra", default="evidencia/2026-11-13-tanda-v41.txt")
    ap.add_argument("--css-de", default="docs/landing/index.html")
    ap.add_argument("--v2", default="", help='JSON {"h1_iguales": n, "keywords_en_comun": n}')
    ap.add_argument("--fotos", default="", help="JSON {url: data URI} (tools/fotos_fichas.py)")
    ap.add_argument("--sim", default="", help="corrida simulada de otro modelo (mismo formato)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    v2 = Path(a.css_de).read_text(encoding="utf-8")
    css = re.search(r"<style>(.*?)</style>", v2, re.S).group(1)
    leer = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))   # noqa: E731
    cab = Path(a.muestra).read_text(encoding="utf-8").splitlines()[0] if Path(a.muestra).exists() else ""
    m = re.search(r"semilla (\d+), (\d+) fichas", cab)
    nuevas = leer(a.nuevas)
    datos = {"vs": leer(a.vs_seo), "base": leer(a.vs_seo_base), "v2": json.loads(a.v2),
             "nuevas": {"meta": nuevas["meta"], "fichas": nuevas["fichas"]},
             "fotos": leer(a.fotos) if a.fotos else {},
             "sim": leer(a.sim) if a.sim else None,
             "semilla": m.group(1) if m else "", "universo": int(m.group(2)) if m else None,
             "pie": f"Corridas en seco del 13-nov-2026 · código {nuevas['meta']['commit'][:7]}"
                    f"{' + cambios sin commitear' if nuevas['meta'].get('codigo_con_cambios_sin_commit') else ''}"
                    f" · {nuevas['meta']['llm']}"}
    from cassoni.checklist import word_count
    for corrida in (datos["nuevas"], datos.get("sim") or {"fichas": []}):
        for f in corrida["fichas"]:
            f["palabras"] = word_count(f.get("descripcion") or "")
    seguro = (json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
              .replace("</", "<\\/").replace("<!--", "<\\!--"))
    html = ('<meta charset="utf-8">\n<title>Agente SEO Cassoni v3</title>\n'
            '<meta name="claude:viewport-fit-sides" content="cover">\n'
            '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700'
            '&family=Space+Grotesk:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">\n'
            f"<style>{css}{CSS_EXTRA}</style>\n" + BODY.replace("__DATOS__", seguro))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"guardado en {out} ({len(html) // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
