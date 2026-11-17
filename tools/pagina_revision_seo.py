# -*- coding: utf-8 -*-
"""Arma la página de revisión para el equipo SEO desde corridas en seco
(tools/correr_lote.py). Por ficha: H1 antes/después, keywords elegidas con su
volumen y origen, las descartadas con el motivo, la descripción antes/después con
las keywords marcadas y el veredicto del validador. Cada ficha tiene una nota
(Bien / Aceptable / Mal / Crítico) y un comentario; la página arma el texto de la
devolución para copiar y pegar.

    python tools/pagina_revision_seo.py \\
        --lote "Tanda nueva=evidencia/2026-11-13-tanda-nueva-v32.json" \\
        --lote "Control (evaluadas el 6-nov)=evidencia/2026-11-13-control-v32.json" \\
        --out docs/revision-seo/index.html
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PLANTILLA = r"""<title>Revisión SEO Cassoni</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: una columna de lectura; cada ficha es un bloque con antes/después en dos columnas que se apilan en el teléfono */
:root{
  --bg:#F5F5F1; --surface:#FFFFFF; --ink:#1E2321; --muted:#5E6661; --line:#DDDFD8;
  --accent:#1E6B62; --accent-soft:#E2EFEC; --mark:#FFE9A8; --mark-ink:#3A2E00;
  --ok:#2F7A3E; --ok-soft:#E3F1E5; --bad:#B4412F; --bad-soft:#F7E4DF; --warn:#946200; --warn-soft:#FBF0D6;
  --f-sans:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  --f-mono:"IBM Plex Mono",ui-monospace,"SFMono-Regular",Consolas,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#141716; --surface:#1C201E; --ink:#E7EAE6; --muted:#9BA39E; --line:#2E3431;
  --accent:#6CC3B6; --accent-soft:#1D3330; --mark:#5A4A12; --mark-ink:#FFF3CC;
  --ok:#7CCB8A; --ok-soft:#1E3324; --bad:#F09A88; --bad-soft:#3A221D; --warn:#E6BE5C; --warn-soft:#382E14; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#141716; --surface:#1C201E; --ink:#E7EAE6; --muted:#9BA39E; --line:#2E3431;
  --accent:#6CC3B6; --accent-soft:#1D3330; --mark:#5A4A12; --mark-ink:#FFF3CC;
  --ok:#7CCB8A; --ok-soft:#1E3324; --bad:#F09A88; --bad-soft:#3A221D; --warn:#E6BE5C; --warn-soft:#382E14; color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font-family:var(--f-sans);font-size:15px;line-height:1.55;
  padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:28px 80px}
.wrap{max-width:1080px;margin:0 auto;display:grid;gap:28px}
h1,h2,h3{text-wrap:balance;margin:0;line-height:1.2}
h1{font-size:1.9rem;font-weight:700;letter-spacing:-.01em}
h2{font-size:1.25rem;font-weight:600}
p{margin:0;max-width:70ch}
a{color:var(--accent)}
a:focus-visible,button:focus-visible,select:focus-visible,textarea:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.eyebrow{font-size:.72rem;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.mono{font-family:var(--f-mono);font-variant-numeric:tabular-nums}
header.top{display:grid;gap:10px}
.lead{color:var(--muted)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.stat{background:var(--surface);padding:14px 16px;display:grid;gap:2px}
.stat b{font-family:var(--f-mono);font-size:1.35rem;font-weight:500;font-variant-numeric:tabular-nums}
.stat span{font-size:.82rem;color:var(--muted)}
.como{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:18px 20px}
.como ol{margin:6px 0 0;padding-left:20px;display:grid;gap:4px;font-size:.92rem}
.tabs{display:flex;flex-wrap:wrap;gap:8px;position:sticky;top:env(safe-area-inset-top,0px);background:var(--bg);padding-block:10px;z-index:5;border-bottom:1px solid var(--line)}
body::before{content:"";position:fixed;inset:0 0 auto;height:env(safe-area-inset-top,0px);z-index:10;background:var(--bg)}
.tab{font:inherit;font-size:.9rem;font-weight:500;border:1px solid var(--line);background:var(--surface);color:var(--ink);border-radius:999px;padding:6px 14px;cursor:pointer}
.tab[aria-selected="true"]{background:var(--accent);border-color:var(--accent);color:var(--surface)}
.tab .n{font-family:var(--f-mono);opacity:.75;margin-left:6px}
.lista{display:grid;gap:22px}
.ficha{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:20px;display:grid;gap:16px;min-width:0}
.ficha-head{display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px 16px;align-items:baseline}
.ficha-head h2 a{color:inherit;text-decoration:none}
.ficha-head h2 a:hover{text-decoration:underline}
.pill{display:inline-flex;align-items:center;gap:6px;font-size:.78rem;font-weight:600;border-radius:999px;padding:3px 10px}
.pill.ok{background:var(--ok-soft);color:var(--ok)}
.pill.bad{background:var(--bad-soft);color:var(--bad)}
.pill.warn{background:var(--warn-soft);color:var(--warn)}
.h1row{display:grid;grid-template-columns:auto 1fr;gap:6px 14px;align-items:baseline;font-size:.95rem}
.h1row dt{font-size:.75rem;color:var(--muted);letter-spacing:.06em;text-transform:uppercase}
.h1row dd{margin:0;min-width:0}
.h1row .nuevo{font-weight:600;font-size:1.05rem}
.kws{display:flex;flex-wrap:wrap;gap:8px}
.kw{display:inline-grid;grid-auto-flow:column;gap:8px;align-items:baseline;border:1px solid var(--line);border-radius:8px;padding:6px 10px;background:var(--accent-soft)}
.kw b{font-weight:600}
.kw small{font-family:var(--f-mono);font-size:.75rem;color:var(--muted);font-variant-numeric:tabular-nums}
.vacio{font-size:.92rem;color:var(--muted)}
details{border-top:1px solid var(--line);padding-top:10px}
summary{cursor:pointer;font-size:.88rem;color:var(--muted);font-weight:500}
.desc-list{margin:8px 0 0;padding:0;list-style:none;display:grid;gap:4px;font-size:.86rem}
.desc-list li{display:grid;grid-template-columns:minmax(120px,220px) 1fr;gap:10px}
.desc-list li span:first-child{font-family:var(--f-mono);font-size:.8rem}
.desc-list li span:last-child{color:var(--muted)}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.col{min-width:0;display:grid;gap:6px;align-content:start}
.texto{font-size:.92rem;border:1px solid var(--line);border-radius:8px;padding:12px 14px;max-height:520px;overflow:auto}
.texto.antes{color:var(--muted)}
.texto h2{font-size:.95rem;margin:12px 0 4px;letter-spacing:.02em}
.texto p{margin:0 0 8px}
.texto ul{margin:0 0 8px;padding-left:18px}
mark{background:var(--mark);color:var(--mark-ink);border-radius:3px;padding:0 2px}
.validador{font-size:.88rem;color:var(--muted)}
.validador.bad{color:var(--bad)}
.nota{display:grid;grid-template-columns:auto 1fr;gap:10px 14px;align-items:start;background:var(--bg);border-radius:8px;padding:12px 14px}
.nota label{font-size:.82rem;font-weight:600;color:var(--muted);padding-top:6px}
select,textarea{font:inherit;font-size:.92rem;color:var(--ink);background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:6px 8px;width:100%;min-width:0}
select{max-width:240px}
textarea{min-height:56px;resize:vertical}
.salida{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:20px;display:grid;gap:12px}
.salida textarea{min-height:200px;font-family:var(--f-mono);font-size:.82rem}
.btn{font:inherit;font-weight:600;font-size:.9rem;background:var(--accent);color:var(--surface);border:0;border-radius:8px;padding:9px 16px;cursor:pointer;justify-self:start}
.pie{font-size:.82rem;color:var(--muted)}
@media (max-width:720px){
  .cols{grid-template-columns:1fr}
  .desc-list li{grid-template-columns:1fr;gap:0}
  .nota{grid-template-columns:1fr}
  .h1row{grid-template-columns:1fr}
}
@media (prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
</style>

<div class="wrap">
  <header class="top">
    <span class="eyebrow">Agente SEO · fichas de producto · corrida en seco</span>
    <h1>Revisión de fichas para el equipo SEO</h1>
    <p class="lead">Nada de esto está publicado en cassoni.com. Son corridas en seco del agente sobre fichas reales: H1 nuevo, keywords que la ficha todavía no tiene y descripción reescrita. Les pedimos una nota por ficha antes de escribir el primer lote en la tienda.</p>
  </header>

  <section class="stats" id="stats" aria-label="Resumen"></section>

  <section class="como">
    <div>
      <span class="eyebrow">Cómo revisar</span>
      <ol>
        <li>Lean el H1 nuevo y las keywords elegidas.</li>
        <li>Comparen la descripción original con la nueva. Las keywords están <mark>resaltadas</mark>.</li>
        <li>Pongan una nota y, si hace falta, un comentario.</li>
        <li>Al final, copien la devolución y mándenla por el canal de siempre.</li>
      </ol>
    </div>
    <div>
      <span class="eyebrow">Criterios (los de su devolución del 6-nov)</span>
      <ol id="criterios"></ol>
    </div>
    <div>
      <span class="eyebrow">Por qué hay fichas sin keywords</span>
      <p style="font-size:.92rem;margin-top:6px">Cada keyword candidata se busca en Google. Si la mayoría de los resultados son colecciones o categorías ("brass chandeliers"), se descarta: esa búsqueda la tiene que ganar la página de categoría, no la ficha. Cuando nada pasa, la ficha queda con el H1 y la descripción reescrita. Las búsquedas que están justo en el límite pueden cambiar de una corrida a otra porque Google cambia sus resultados.</p>
    </div>
  </section>

  <nav class="tabs" id="tabs" role="tablist" aria-label="Lotes"></nav>
  <section class="lista" id="lista"></section>

  <section class="salida">
    <h2>Devolución</h2>
    <p class="lead">Se arma sola con las notas y comentarios de arriba. Las notas quedan guardadas en este navegador.</p>
    <textarea id="devolucion" readonly aria-label="Texto de la devolución"></textarea>
    <button class="btn" id="copiar" type="button">Copiar devolución</button>
  </section>

  <p class="pie" id="pie"></p>
</div>

<script type="application/json" id="datos">__DATOS__</script>
<script>
(function(){
  const D = JSON.parse(document.getElementById('datos').textContent);
  const CRITERIOS = [
    "El H1 dice qué es (tipo, en inglés de EE. UU.)",
    "El H1 lleva un rasgo real y distintivo (material, forma, técnica)",
    "El H1 no tiene códigos ni se confunde con otra ficha",
    "Ninguna keyword es de categoría, de otro tema o de otro producto",
    "Ninguna keyword está forzada ni repite lo que ya dice el texto",
    "Nada inventado (todo dato está en la ficha)",
    "La descripción ayuda a decidir la compra"
  ];
  const NOTAS = ["", "Bien", "Aceptable", "Mal", "Crítico"];
  const ORIGEN = {gsc:"ya aparece en Google", investigacion:"investigación", competidor:"competencia"};
  const $ = s => document.querySelector(s);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const fmt = n => n == null ? "s/d" : Number(n).toLocaleString("es-AR");

  let guardado = {};
  try { guardado = JSON.parse(localStorage.getItem("revision-seo-notas") || "{}"); } catch (e) {}
  const guardar = () => { try { localStorage.setItem("revision-seo-notas", JSON.stringify(guardado)); } catch (e) {} };

  $("#criterios").innerHTML = CRITERIOS.map(c => `<li>${esc(c)}</li>`).join("");

  // limpia el HTML de la ficha: solo estructura de texto
  function limpio(html){
    const t = document.createElement("template");
    t.innerHTML = html || "";
    const OK = new Set(["P","H2","H3","UL","OL","LI","STRONG","B","EM","I","BR","A"]);
    (function rec(n){
      [...n.childNodes].forEach(c => {
        if (c.nodeType === 1){
          if (!OK.has(c.tagName)){ rec(c); c.replaceWith(...c.childNodes); return; }
          [...c.attributes].forEach(a => { if (!(c.tagName === "A" && a.name === "href")) c.removeAttribute(a.name); });
          if (c.tagName === "A"){
            const h = c.getAttribute("href") || "";
            if (!/^https:\/\//.test(h)) c.removeAttribute("href");
            else { c.setAttribute("target","_blank"); c.setAttribute("rel","noopener"); }
          }
          rec(c);
        } else if (c.nodeType !== 3) c.remove();
      });
    })(t.content);
    return t;
  }
  function marcar(tpl, kws){
    if (!kws.length) return tpl;
    const rx = new RegExp("(" + kws.map(k => k.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")).sort((a,b)=>b.length-a.length).join("|") + ")", "gi");
    const w = document.createTreeWalker(tpl.content, NodeFilter.SHOW_TEXT);
    const nodos = []; while (w.nextNode()) nodos.push(w.currentNode);
    nodos.forEach(n => {
      if (!rx.test(n.nodeValue)) return; rx.lastIndex = 0;
      const span = document.createElement("span");
      span.innerHTML = esc(n.nodeValue).replace(rx, "<mark>$1</mark>");
      n.replaceWith(...span.childNodes);
    });
    return tpl;
  }
  function descartadas(sel){
    const i = (sel || "").indexOf("descartadas:");
    if (i < 0) return [];
    return sel.slice(i + 12).split(/;\s(?=[^()]*(?:\(|$))/).map(s => s.trim()).filter(Boolean).map(s => {
      const m = s.match(/^(.*?)\s\((.*)\)$/);
      return m ? [m[1], m[2]] : [s, ""];
    });
  }

  function tarjeta(f, idLote, i){
    const id = `${idLote}-${i}`;
    const kws = (f.keywords_detalle || []);
    const v = f.validacion || {};
    const aprobada = f.status === "processed" && v.aprobado !== false;
    const nombre = f.h1_original || f.url;
    const desc = descartadas(f.seleccion);
    const nota = (guardado[f.url] || {}).nota || "";
    const com = (guardado[f.url] || {}).comentario || "";
    const kwHtml = kws.length ? kws.map(k => `<span class="kw"><b>${esc(k.keyword)}</b><small>${fmt(k.volume)}/mes · ${esc(ORIGEN[k.origen || "gsc"] || k.origen)}</small></span>`).join("")
      : `<p class="vacio">Ninguna keyword pasó los filtros. La ficha queda con el H1 y la descripción reescrita.</p>`;
    const el = document.createElement("article");
    el.className = "ficha"; el.dataset.url = f.url;
    el.innerHTML = `
      <div class="ficha-head">
        <h2><a href="${esc(f.url)}" target="_blank" rel="noopener">${esc(nombre)}</a></h2>
        ${aprobada ? `<span class="pill ok">Aprobada por el validador</span>` : `<span class="pill bad">Rechazada por el validador</span>`}
      </div>
      <dl class="h1row">
        <dt>H1 actual</dt><dd>${esc(f.h1_original)}</dd>
        <dt>H1 nuevo</dt><dd class="nuevo">${esc(f.h1)}</dd>
      </dl>
      <div class="col"><span class="eyebrow">Keywords elegidas</span><div class="kws">${kwHtml}</div></div>
      ${desc.length ? `<details><summary>Ver las ${desc.length} descartadas y por qué</summary><ul class="desc-list">${desc.map(d => `<li><span>${esc(d[0])}</span><span>${esc(d[1])}</span></li>`).join("")}</ul></details>` : ""}
      <div class="cols">
        <div class="col"><span class="eyebrow">Descripción actual</span><div class="texto antes"></div></div>
        <div class="col"><span class="eyebrow">Descripción nueva</span><div class="texto nueva"></div></div>
      </div>
      <p class="validador ${aprobada ? "" : "bad"}"><b>Validador:</b> ${esc((v.issues && v.issues.length ? v.issues.join(" ") : v.razon) || f.reason || "")}</p>
      <div class="nota">
        <label for="nota-${id}">Nota</label>
        <select id="nota-${id}">${NOTAS.map(n => `<option value="${n}" ${n === nota ? "selected" : ""}>${n || "Elegir…"}</option>`).join("")}</select>
        <label for="com-${id}">Comentario</label>
        <textarea id="com-${id}" placeholder="Qué cambiarían (opcional)">${esc(com)}</textarea>
      </div>`;
    el.querySelector(".texto.antes").append(limpio(f.descripcion_original).content);
    el.querySelector(".texto.nueva").append(marcar(limpio(f.descripcion || f.descripcion_original), kws.map(k => k.keyword)).content);
    const upd = () => {
      guardado[f.url] = {nota: el.querySelector("select").value, comentario: el.querySelector("textarea").value};
      guardar(); devolucion();
    };
    el.querySelector("select").addEventListener("change", upd);
    el.querySelector("textarea").addEventListener("input", upd);
    return el;
  }

  function devolucion(){
    const lineas = ["Devolución SEO · revisión de fichas del agente", ""];
    D.lotes.forEach(l => {
      lineas.push(`## ${l.nombre}`);
      l.fichas.forEach(f => {
        const g = guardado[f.url] || {};
        lineas.push(`- ${f.h1_original} → ${f.h1}`);
        lineas.push(`  Nota: ${g.nota || "(sin nota)"}${g.comentario ? " · " + g.comentario.replace(/\s+/g, " ") : ""}`);
      });
      lineas.push("");
    });
    $("#devolucion").value = lineas.join("\n");
  }

  // pestañas
  const tabs = $("#tabs"), lista = $("#lista");
  function mostrar(i){
    [...tabs.children].forEach((b, j) => b.setAttribute("aria-selected", String(i === j)));
    lista.replaceChildren(...D.lotes[i].fichas.map((f, k) => tarjeta(f, i, k)));
    stats(i);
  }
  D.lotes.forEach((l, i) => {
    const b = document.createElement("button");
    b.className = "tab"; b.type = "button"; b.setAttribute("role", "tab");
    b.innerHTML = `${esc(l.nombre)}<span class="n">${l.fichas.length}</span>`;
    b.addEventListener("click", () => mostrar(i));
    tabs.append(b);
  });

  function stats(i){
    const l = D.lotes[i], fs = l.fichas;
    const ok = fs.filter(f => f.status === "processed" && (f.validacion || {}).aprobado !== false).length;
    const conKw = fs.filter(f => (f.keywords || []).length).length;
    const nKw = fs.reduce((a, f) => a + (f.keywords || []).length, 0);
    const vol = fs.reduce((a, f) => a + (f.keywords_detalle || []).reduce((b, k) => b + (k.volume || 0), 0), 0);
    const c = l.costos || {};
    const usd = ((c.usd || 0) + (c.dfs_usd || 0)) / Math.max(fs.length, 1);
    $("#stats").innerHTML = [
      [`${ok} de ${fs.length}`, "aprobadas por el validador"],
      [`${conKw} de ${fs.length}`, "con keywords nuevas"],
      [nKw, "keywords en total"],
      [fmt(vol), "búsquedas/mes que suman"],
      [`US$ ${usd.toFixed(3)}`, "costo por ficha (datos + redacción)"]
    ].map(s => `<div class="stat"><b>${s[0]}</b><span>${s[1]}</span></div>`).join("");
  }

  $("#copiar").addEventListener("click", () => {
    const t = $("#devolucion");
    const listo = () => { const b = $("#copiar"); b.textContent = "Copiada"; setTimeout(() => b.textContent = "Copiar devolución", 1600); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(t.value).then(listo, () => { t.select(); });
    else t.select();
  });

  $("#pie").textContent = `Generada el ${D.fecha} · código ${D.commit.slice(0, 7)} · modelo ${D.llm}. Las fichas de cada lote se eligieron al azar entre las que tienen al menos 50 impresiones en Google.`;
  mostrar(0); devolucion();
})();
</script>
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lote", action="append", required=True,
                    help='"Nombre visible=ruta/al/lote.json" (se puede repetir)')
    ap.add_argument("--out", required=True)
    ap.add_argument("--fecha", default="")
    a = ap.parse_args(argv)
    lotes, meta = [], {}
    for item in a.lote:
        nombre, _, ruta = item.partition("=")
        d = json.loads(Path(ruta).read_text(encoding="utf-8"))
        meta = meta or d.get("meta", {})
        lotes.append({"nombre": nombre.strip(), "costos": d.get("meta", {}).get("costos", {}),
                      "fichas": [{k: f.get(k) for k in (
                          "url", "status", "reason", "h1_original", "h1", "descripcion",
                          "descripcion_original", "keywords", "keywords_detalle", "seleccion",
                          "validacion")} for f in d["fichas"]]})
    datos = {"lotes": lotes, "commit": meta.get("commit", ""), "llm": meta.get("llm", ""),
             "fecha": a.fecha}
    seguro = (json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
              .replace("</", "<\\/").replace("<!--", "<\\!--"))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(PLANTILLA.replace("__DATOS__", seguro), encoding="utf-8")
    print(f"guardado en {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
