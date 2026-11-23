# -*- coding: utf-8 -*-
"""Landing v4 para Alex (23-nov-2026): sus devoluciones del 17-nov en el código, sus 10
fichas en tres fechas y 30 fichas nuevas elegidas por código. Mismo diseño que la v3
(tools/landing_v3.py, CSS de docs/landing/index.html). Todo en seco.

    python tools/landing_v4.py \\
        --vs-seo evidencia/AAAA-MM-DD-control-alex-vs-seo.json \\
        --nuevas evidencia/AAAA-MM-DD-tanda-30.json --muestra evidencia/AAAA-MM-DD-tanda-30.txt \\
        --out docs/landing-v4/index.html
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from landing_v3 import CSS_EXTRA  # noqa: E402

URL = "https://tarsterminal.duckdns.org/cassoni-agente-seo/"
TITULO = "Agente SEO Cassoni · v4 — lo que pidió Alex, en cada ficha"
DESC = ("Las devoluciones de Alex del 17-nov, en el código: sus 10 fichas en tres fechas y 30 "
        "fichas nuevas elegidas por código. Todo en seco: nada se escribió en la tienda.")

BODY = r"""
<nav class="nav" aria-label="Secciones">
  <a class="brand" href="#top">cassoni<b>·</b>seo <span style="font-size:13px;color:var(--mute)">v4</span></a>
  <ul>
    <li><a class="l" href="#cambios">Qué cambió</a></li>
    <li><a class="l" href="#vs-seo">Agente vs Alex</a></li>
    <li><a class="l" href="#nuevas">Fichas nuevas</a></li>
    <li><a class="l" href="#preguntas">Para confirmar</a></li>
    <li><a class="l" href="#garantias">Garantías</a></li>
  </ul>
</nav>

<header class="band hero" id="top">
  <div class="wrap">
    <span class="eyebrow" id="eyebrow">Agente SEO · fichas de producto · v4</span>
    <h1>Lo que pidió Alex,<br><span class="v">en cada ficha.</span></h1>
    <p class="lead">El 17-nov Alex pidió priorizar lo que la gente busca: el nombre cuando ya se busca, el rasgo más buscado cuando no, y las keywords que ya traen impresiones en Search Console. Esta página muestra cómo quedó en sus 10 fichas y en fichas que nadie había mirado. <b>Todo en seco: nada se escribió en la tienda.</b></p>
    <div class="btns">
      <a class="btn primary" href="#vs-seo"><span>Agente vs Alex</span><i aria-hidden="true">↘</i></a>
      <a class="btn ghost" href="#nuevas"><span id="btn-nuevas">Fichas nuevas</span><i aria-hidden="true">↘</i></a>
    </div>
    <div class="hero-meta" id="hero-stats"></div>
  </div>
  <canvas id="waves" aria-hidden="true"></canvas>
</header>

<section class="band paper" id="cambios">
  <div class="wrap">
    <div class="head">
      <span class="eyebrow">Desde el 17-nov</span>
      <h2>Qué cambió <span class="v">y por qué.</span></h2>
      <p class="lead">Cada regla está en código, con tests: el modelo redacta, no decide el H1 ni las keywords.</p>
    </div>
    <div class="ftable reveal"><div class="ftable-scroll"><table>
      <thead><tr><th></th><th>Lo que dijo Alex</th><th>Cómo quedó</th></tr></thead>
      <tbody>
        <tr><td><b>H1</b></td><td>Si el nombre ya se busca, nombre y marca («Club Sofa»). Si no, el rasgo más buscado («Marble» en Rock).</td><td>Nombre + marca desde 1.000 búsquedas/mes. Si no, el rasgo más buscado entre los materiales que tienen todas las versiones.</td></tr>
        <tr><td><b>Opciones</b></td><td>Rock: la tapa viene en mármol o en madera.</td><td>Si la parte principal viene en opciones, el H1 lleva la más buscada y la descripción cubre todas, con una keyword por opción («marble table», «wood table»). Si la opción es el tapizado, el H1 dice «Upholstered», como en Hermes.</td></tr>
        <tr><td><b>Dos materiales</b></td><td>Cleopatra: «Wood and Leather Dining Chair».</td><td>Si la ficha se define con dos materiales que no son opciones («Wooden chair with leather upholstery»), el H1 lleva los dos.</td></tr>
        <tr><td><b>Keywords</b></td><td>Lo que funciona: Search Console con impresiones y marca + tipo («nomon wall clock»).</td><td>Primero Search Console, después marca + tipo, y la genérica corta del material exacto del H1, como en sus fichas («glass table», «dining table in glass»).</td></tr>
        <tr><td><b>Cuántas y de dónde</b></td><td>Search Console y marca + tipo dejaban muchas fichas con una sola.</td><td>Mínimo 3 (más si son coherentes y entran natural, hasta 5), con los mismos tipos de keyword que usa Alex: búsquedas de Search Console, marca + tipo, el material del H1 con el tipo corto, el tipo de producto («wall sconce») e «italian + tipo» si la ficha lo dice. Si faltan, búsquedas reales con el nombre y el fabricante. Si una no entra natural en el texto, el redactor la deja afuera con el motivo.</td></tr>
        <tr><td><b>Genéricas que fallaban</b></td><td>«marble table» en Palatial y «leather table» en Dandy.</td><td>Nunca un material que la ficha no tiene (Palatial no tiene mármol) ni un tipo que, acortado, es otro producto (Dandy es una mesa de pool).</td></tr>
        <tr><td><b>Marca de otro fabricante</b></td><td>Steinway: el volumen es el de la marca, no el de esta pieza.</td><td>No cuenta como «el nombre ya se busca»: va el rasgo («Mother-of-Pearl»). La marca sí puede ser keyword («steinway and sons piano»).</td></tr>
      </tbody>
    </table></div></div>
  </div>
</section>

<section class="band paper" id="vs-seo">
  <div class="wrap">
    <div class="head">
      <span class="eyebrow">Prueba 1 · las 10 fichas que resolvió Alex</span>
      <h2>Agente vs Alex,<br><span class="v">en las mismas fichas.</span></h2>
      <p class="lead">Cada ficha se procesa viendo cómo Alex resolvió las otras nueve, nunca la propia: es la misma situación que una ficha nueva del catálogo.</p>
    </div>
    <div class="cmp reveal" id="cmp" role="table" aria-label="Parecido con Alex por fecha"></div>
    <p class="note" style="margin-top:22px;color:var(--paper-mute);border-color:var(--violet-deep)" id="nota-vs"></p>
    <p class="lead" style="margin:28px 0 22px">En verde, lo que eligieron los dos.</p>
    <div class="par" id="par"></div>
  </div>
</section>

<section class="band paper" id="nuevas" style="padding-top:0">
  <div class="wrap">
    <div class="head">
      <span class="eyebrow">Prueba 2 · fichas que nadie había mirado</span>
      <h2 id="nuevas-h2">Fichas nuevas,<br><span class="v">elegidas por código.</span></h2>
      <p class="lead" id="nuevas-lead"></p>
    </div>
    <div class="resumen" id="nuevas-stats"></div>
    <div class="fichas" id="fichas"></div>
  </div>
</section>

<section class="band" id="preguntas">
  <div class="wrap">
    <div class="head">
      <span class="eyebrow">Para confirmar con Alex</span>
      <h2>Tres lecturas<br><span class="v">que conviene confirmar.</span></h2>
    </div>
    <div class="pend">
      <div class="reveal"><b>Genéricas cortas</b><span>El 17-nov marcaste «marble table» en Palatial y «leather table» en Dandy. Lo leímos como «nunca una genérica falsa o de otro producto», no «nunca una genérica corta», porque en Rock y Bakkarat las usás. ¿Es así?</span></div>
      <div class="reveal"><b>Tapizado en el H1</b><span>Cuando el tapizado viene en tela o cuero, el H1 dice «Upholstered» y no elige uno, como en Hermes. ¿Vale para todas las camas, sofás y sillas?</span></div>
      <div class="reveal"><b>Códigos de catálogo</b><span>El H1 no lleva códigos («SC1019», «19800»), como en tus fichas, aunque alguno traiga impresiones en Search Console. La keyword con el código sí puede ir en la descripción.</span></div>
      <div class="reveal"><b>Nada escrito en la tienda</b><span>Todas las corridas son en seco. El primer lote real lo aprueba Alex.</span></div>
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
        <p>Inventar medidas, materiales, diseñadores o colecciones.</p>
        <p>Elegir una keyword que no esté en la lista de candidatas.</p>
        <p>Tocar la descripción corta, los metadatos o los ALT, que son de n8n.</p>
        <p>Escribir en Search Console.</p>
      </div>
      <div>
        <h3>Siempre</h3>
        <p>Corre en seco por defecto.</p>
        <p>Deja cada ficha con su estado, su motivo y lo que descartó.</p>
        <p>Controla en código cada número de la descripción contra la ficha.</p>
        <p>Escribe solo <code>name</code> y <code>description</code>.</p>
      </div>
    </div>
  </div>
</section>

<footer><div class="wrap"><span>Agente SEO Cassoni · v4</span><span id="pie"></span></div></footer>

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
  const A = D.vs.resumen, N = D.nuevas, n = N.fichas.length;
  const cols = D.historial.concat([{fecha: D.fecha, r: A}]);

  $("#eyebrow").textContent = `Agente SEO · fichas de producto · v4 · ${D.fecha}`;
  $("#btn-nuevas").textContent = `${n} fichas nuevas`;
  const aprob = N.fichas.filter(f => f.status === "processed").length;
  const conKw = N.fichas.filter(f => (f.keywords || []).length).length;
  const costo = ((N.meta.costos.usd || 0) + (N.meta.costos.dfs_usd || 0)) / Math.max(n, 1);
  $("#hero-stats").innerHTML = [
    [`${A.h1_iguales}/10`, "H1 idénticos al de Alex"],
    [`${A.keywords_en_comun}/${A.keywords_seo}`, "keywords en común con Alex"],
    [`${aprob}/${n}`, "fichas nuevas aprobadas"],
    [`US$ ${costo.toFixed(2)}`, "por ficha"]
  ].map(s => `<div class="stat"><b>${s[0]}</b><small>${s[1]}</small></div>`).join("");

  // prueba 1
  const filas = [
    ["H1 idéntico al de Alex", r => `${r.h1_iguales} de 10`],
    ["Palabras del H1 en común", r => pct(r.h1_parecido_promedio)],
    ["Keywords de Alex que eligió el agente", r => `${r.keywords_en_comun} de ${r.keywords_seo}`],
    [`Palabras de la descripción (Alex: ${A.palabras_seo_prom})`, r => r.palabras_agente_prom],
    ["Aprobadas por el validador", r => `${r.aprobadas} de 10`]
  ];
  const gc = `style="grid-template-columns:minmax(0,1.6fr) repeat(${cols.length},minmax(0,1fr))"`;
  $("#cmp").innerHTML = `<div class="cmp-row h" role="row" ${gc}><div>Medida</div>${cols.map(c => `<div>${esc(c.fecha)}</div>`).join("")}</div>` +
    filas.map(f => `<div class="cmp-row" role="row" ${gc}><div>${esc(f[0])}</div>${cols.map((c, i) => `<div class="n${i === cols.length - 1 ? " now" : ""}">${esc(f[1](c.r))}</div>`).join("")}</div>`).join("");
  $("#nota-vs").textContent = D.nota_vs;
  const foto = (url, alt, cls) => {
    const src = (D.fotos || {})[url] || "";
    return `<a class="${cls}" href="${esc(url)}" target="_blank" rel="noopener" title="Ver en cassoni.com">${src ? `<img src="${src}" alt="${esc(alt)}" loading="lazy">` : "<span>sin foto</span>"}</a>`;
  };
  const pills = (lista, otras) => { const c = new Set(otras.map(clave)); return lista.length ? lista.map(k => `<span class="pill ${c.has(clave(k)) ? "hit" : ""}">${esc(k)}</span>`).join("") : `<span class="pill">ninguna</span>`; };
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
  $("#par").innerHTML = D.vs.fichas.map(f => `
    <article class="par-item reveal">
      ${foto(f.url, f.nombre, "par-foto")}
      <div class="par-top"><h3>${esc(f.nombre)}</h3><span>${f.kw_en_comun.length}/${f.kw_seo.length} keywords en común · ${f.palabras_agente} vs ${f.palabras_seo} palabras</span></div>
      <div class="duo">
        <div><span class="who">Alex</span><div class="t">${esc(f.h1_seo)}</div><div>${pills(f.kw_seo, f.kw_agente)}</div>
          <div class="desc duo-desc">${limpio(textoSEO(f.descripcion_seo), f.kw_seo)}</div><span class="palabras">${f.palabras_seo} palabras</span></div>
        <div><span class="who ag">Agente · ${esc(D.fecha)}</span><div class="t">${esc(f.h1_agente)}${f.h1_igual ? '<span class="igual">igual</span>' : ""}</div><div>${pills(f.kw_agente, f.kw_seo)}</div>
          <div class="desc duo-desc">${limpio(f.descripcion_agente, f.kw_agente)}</div><span class="palabras">${f.palabras_agente} palabras</span></div>
      </div>
    </article>`).join("");

  // prueba 2
  $("#nuevas-h2").innerHTML = `${n} fichas nuevas,<br><span class="v">elegidas por código.</span>`;
  $("#nuevas-lead").textContent = `Elegidas al azar${D.semilla ? ` (semilla ${D.semilla})` : ""}${D.universo ? ` entre las ${fmt(D.universo)} fichas con al menos 50 impresiones en Google` : ""}, repartidas por familia, sin repetir ninguna de las que ya se usaron. Ninguna está entre las fichas de Alex: el agente las resolvió con sus 10 como ejemplo.` +
    (N.meta.simulada ? " Corrida fuera de la tienda: los datos de cada ficha se leyeron de la página publicada y, en lugar de Search Console, se usaron las búsquedas que DataForSEO estima para cada página. En la corrida real, con WooCommerce y Search Console, el resultado puede variar." : "");
  const kwN = N.fichas.reduce((a, f) => a + (f.keywords || []).length, 0);
  $("#nuevas-stats").innerHTML = [
    [`${aprob} de ${n}`, "aprobadas por el validador"],
    [`${conKw} de ${n}`, "con keywords"],
    [kwN, "keywords en total"],
    [`US$ ${costo.toFixed(3)}`, "costo por ficha"]
  ].map(s => `<div class="stat"><b>${s[0]}</b><small>${s[1]}</small></div>`).join("");
  const origen = k => k.origen === "gsc" ? ["ya aparece", fmt(k.impresiones || k.impressions) + " impr.", "gsc"]
    : k.origen === "opcion" ? ["opción de la ficha", fmt(k.volumen || k.volume) + "/mes", "gen"]
    : k.origen === "sugerencia" ? ["se busca con el nombre", fmt(k.volumen || k.volume) + "/mes", "gen"]
    : k.origen === "competidor" ? ["la usa la competencia", fmt(k.volumen || k.volume) + "/mes", "gen"]
    : ["genérica", fmt(k.volumen || k.volume) + "/mes", "gen"];
  $("#fichas").innerHTML = N.fichas.map(f => {
    const ok = f.status === "processed";
    const kws = f.keywords_detalle || [];
    const v = f.validacion || {};
    const kwHtml = kws.length ? kws.map(k => { const o = origen(k); return `<span class="kw"><span>${esc(k.keyword)}</span><small>${o[1]}</small><span class="org ${o[2]}">${o[0]}</span></span>`; }).join("")
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
  $("#pie").textContent = D.pie;

  if (!matchMedia("(prefers-reduced-motion: reduce)").matches && "IntersectionObserver" in window){
    const els = document.querySelectorAll(".reveal");
    const io = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting){ e.target.classList.remove("pre"); io.unobserve(e.target); } }), {rootMargin: "0px 0px -8% 0px"});
    els.forEach(el => { const r = el.getBoundingClientRect(); if (r.top > innerHeight) { el.classList.add("pre"); io.observe(el); } });
  }
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

CABEZA = f"""<meta charset="utf-8">
<title>{TITULO}</title>
<meta name="description" content="{DESC}">
<meta name="robots" content="noindex">
<meta name="theme-color" content="#111014">
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="icon" href="favicon.svg" type="image/svg+xml">
<meta property="og:type" content="website">
<meta property="og:site_name" content="cassoni · seo">
<meta property="og:url" content="{URL}">
<meta property="og:title" content="{TITULO}">
<meta property="og:description" content="{DESC}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{TITULO}">
<meta name="twitter:description" content="{DESC}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">"""

HISTORIAL = [("13-nov", "evidencia/2026-11-13-control-v41-vs-seo.json"),
             ("17-nov", "evidencia/2026-11-17-control-reglas3-vs-seo.json")]


def armar(vs_seo: str, nuevas: str, muestra: str, fecha: str, nota_vs: str,
          css_de: str = "docs/landing/index.html", fotos: str = "") -> str:
    leer = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))   # noqa: E731
    css = re.search(r"<style>(.*?)</style>", Path(css_de).read_text(encoding="utf-8"), re.S).group(1)
    lineas = Path(muestra).read_text(encoding="utf-8").splitlines() if muestra and Path(muestra).exists() else []
    m = re.search(r"semilla (\d+), (\d+) fichas", lineas[0]) if lineas else None
    lote = leer(nuevas)
    from cassoni.checklist import word_count
    for f in lote["fichas"]:
        f["palabras"] = word_count(f.get("descripcion") or "")
    meta = lote["meta"]
    datos = {"vs": leer(vs_seo), "fecha": fecha, "nota_vs": nota_vs,
             "historial": [{"fecha": f, "r": leer(p)["resumen"]} for f, p in HISTORIAL if Path(p).exists()],
             "nuevas": {"meta": meta, "fichas": lote["fichas"]},
             "fotos": leer(fotos) if fotos else {},
             "semilla": m.group(1) if m else str(meta.get("semilla") or ""),
             "universo": int(m.group(2)) if m else meta.get("universo"),
             "pie": f"Corridas en seco del {fecha} · código {(meta.get('commit') or '')[:7]} · {meta.get('llm', '')}"}
    seguro = (json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
              .replace("</", "<\\/").replace("<!--", "<\\!--"))
    return (f"<!doctype html>\n<html lang=\"es\">\n<head>\n{CABEZA}\n<style>{css}{CSS_EXTRA}</style>\n"
            f"</head>\n<body>\n" + BODY.replace("__DATOS__", seguro) + "\n</body>\n</html>\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vs-seo", required=True, help="evaluar_vs_seo.py de las 10 fichas de Alex")
    ap.add_argument("--nuevas", required=True, help="correr_lote.py de las fichas nuevas")
    ap.add_argument("--muestra", default="", help="la lista elegida (primera línea: semilla y universo)")
    ap.add_argument("--fecha", default="23-nov")
    ap.add_argument("--nota-vs", default="Medido con la ficha completa de WooCommerce (atributos y medidas), en seco.")
    ap.add_argument("--fotos", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    html = armar(a.vs_seo, a.nuevas, a.muestra, a.fecha, a.nota_vs, fotos=a.fotos)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"guardado en {out} ({len(html) // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
