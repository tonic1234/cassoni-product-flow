# -*- coding: utf-8 -*-
"""Página lado a lado: lo que escribió el SEO y lo que escribe el agente en las
mismas fichas (salida de tools/evaluar_vs_seo.py).

    python tools/pagina_agente_vs_seo.py --eval evidencia/X-vs-seo.json \\
        --base evidencia/Y-vs-seo.json --out docs/agente-vs-seo/index.html
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PLANTILLA = r"""<title>Agente vs SEO</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: resumen arriba; cada ficha con SEO (izquierda) y agente (derecha), apilado en el teléfono */
:root{
  --bg:#F5F5F1; --surface:#FFFFFF; --ink:#1E2321; --muted:#5E6661; --line:#DDDFD8;
  --seo:#6B4FA0; --seo-soft:#EFEAF7; --agent:#1E6B62; --agent-soft:#E2EFEC;
  --hit:#2F7A3E; --hit-soft:#E3F1E5; --miss:#8A8F8B;
  --f-sans:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  --f-mono:"IBM Plex Mono",ui-monospace,Consolas,monospace;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#141716; --surface:#1C201E; --ink:#E7EAE6; --muted:#9BA39E; --line:#2E3431;
  --seo:#B9A2E6; --seo-soft:#2B2340; --agent:#6CC3B6; --agent-soft:#1D3330;
  --hit:#7CCB8A; --hit-soft:#1E3324; --miss:#7C837F; color-scheme:dark}}
:root[data-theme="dark"]{
  --bg:#141716; --surface:#1C201E; --ink:#E7EAE6; --muted:#9BA39E; --line:#2E3431;
  --seo:#B9A2E6; --seo-soft:#2B2340; --agent:#6CC3B6; --agent-soft:#1D3330;
  --hit:#7CCB8A; --hit-soft:#1E3324; --miss:#7C837F; color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--bg);color:var(--ink);font-family:var(--f-sans);font-size:15px;line-height:1.55;
  padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:28px 80px}
.wrap{max-width:1080px;margin:0 auto;display:grid;gap:26px}
h1,h2{margin:0;line-height:1.2;text-wrap:balance}
h1{font-size:1.85rem;font-weight:700}
h2{font-size:1.15rem;font-weight:600}
p{margin:0;max-width:72ch}
.eyebrow{font-size:.72rem;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.lead{color:var(--muted)}
.tabla{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--surface)}
table{border-collapse:collapse;width:100%;min-width:520px;font-variant-numeric:tabular-nums}
th,td{padding:10px 14px;text-align:left;border-bottom:1px solid var(--line);font-size:.92rem}
th{font-size:.75rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:600}
tr:last-child td{border-bottom:0}
td.num{font-family:var(--f-mono)}
td.mejor{font-weight:600;color:var(--agent)}
.nota{font-size:.9rem;color:var(--muted);background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:14px 16px;display:grid;gap:6px}
.ficha{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:20px;display:grid;gap:14px;min-width:0}
.head{display:flex;flex-wrap:wrap;justify-content:space-between;gap:6px 14px;align-items:baseline}
.score{font-family:var(--f-mono);font-size:.82rem;color:var(--muted)}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.col{min-width:0;display:grid;gap:10px;align-content:start;border-radius:10px;padding:14px;border:1px solid var(--line)}
.col.seo{border-top:3px solid var(--seo)}
.col.agente{border-top:3px solid var(--agent)}
.quien{font-size:.75rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase}
.seo .quien{color:var(--seo)} .agente .quien{color:var(--agent)}
.h1{font-weight:600;font-size:1rem}
.h1 .igual{font-size:.75rem;font-weight:600;color:var(--hit);background:var(--hit-soft);border-radius:999px;padding:2px 8px;margin-left:6px;white-space:nowrap}
.kws{display:flex;flex-wrap:wrap;gap:6px}
.kw{font-size:.85rem;border-radius:6px;padding:3px 8px;border:1px solid var(--line);color:var(--miss)}
.kw.hit{color:var(--hit);background:var(--hit-soft);border-color:transparent;font-weight:600}
.texto{font-size:.9rem;display:grid;gap:6px}
.texto h3{font-size:.85rem;letter-spacing:.04em;margin:6px 0 0}
.texto ul{margin:0;padding-left:18px}
.texto p{margin:0}
.meta{font-family:var(--f-mono);font-size:.78rem;color:var(--muted)}
.pie{font-size:.82rem;color:var(--muted)}
@media (max-width:720px){.cols{grid-template-columns:1fr}}
</style>

<div class="wrap">
  <header style="display:grid;gap:10px">
    <span class="eyebrow">Agente SEO Cassoni · prueba contra el documento del SEO (6-nov)</span>
    <h1>¿El agente hace lo mismo que el SEO?</h1>
    <p class="lead">Las 10 fichas que el SEO resolvió a mano, procesadas por el agente. Cada ficha se procesa mostrándole como ejemplo las <b>otras nueve</b> del SEO, nunca la propia: es la misma situación que una ficha nueva del catálogo. Nada se escribió en la tienda.</p>
  </header>
  <div class="tabla"><table id="resumen"></table></div>
  <div class="nota" id="lectura"></div>
  <section id="fichas" style="display:grid;gap:20px"></section>
  <p class="pie" id="pie"></p>
</div>

<script type="application/json" id="datos">__DATOS__</script>
<script>
(function(){
  const D = JSON.parse(document.getElementById("datos").textContent);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const clave = k => k.toLowerCase().replace(/&/g," and ").replace(/['’]s\b/g,"").replace(/[^a-z0-9 ]/g," ").split(/\s+/).filter(Boolean).map(w => w.length>3 && w.endsWith("s") && !w.endsWith("ss") ? w.slice(0,-1) : w).join(" ");
  const pct = x => Math.round(x*100) + "%";
  const A = D.actual.resumen, B = D.base && D.base.resumen;
  const filas = [
    ["H1 idénticos al del SEO", B && `${B.h1_iguales} de ${B.fichas}`, `${A.h1_iguales} de ${A.fichas}`],
    ["Palabras del H1 en común", B && pct(B.h1_parecido_promedio), pct(A.h1_parecido_promedio)],
    ["Keywords del SEO que eligió el agente", B && `${B.keywords_en_comun} de ${B.keywords_seo}`, `${A.keywords_en_comun} de ${A.keywords_seo}`],
    ["Keywords del agente que también eligió el SEO", B && `${B.keywords_en_comun} de ${B.keywords_agente}`, `${A.keywords_en_comun} de ${A.keywords_agente}`],
    ["Palabras de la descripción (SEO: " + A.palabras_seo_prom + ")", B && B.palabras_agente_prom, A.palabras_agente_prom],
    ["Aprobadas por el validador", B && `${B.aprobadas} de ${B.fichas}`, `${A.aprobadas} de ${A.fichas}`],
  ];
  document.getElementById("resumen").innerHTML =
    `<thead><tr><th>Medida</th>${B ? "<th>Antes (v3.2)</th>" : ""}<th>Ahora (v4.1)</th></tr></thead><tbody>` +
    filas.map(f => `<tr><td>${esc(f[0])}</td>${B ? `<td class="num">${esc(f[1])}</td>` : ""}<td class="num mejor">${esc(f[2])}</td></tr>`).join("") + "</tbody>";
  document.getElementById("lectura").innerHTML = D.lectura.map(l => `<p>${l}</p>`).join("");

  function textoSEO(t){
    const out = []; let lista = [];
    const cerrar = () => { if (lista.length){ out.push("<ul>" + lista.map(x => `<li>${esc(x)}</li>`).join("") + "</ul>"); lista = []; } };
    (t || "").split("\n").map(l => l.trim()).filter(Boolean).forEach(l => {
      if (l.startsWith("•")) { lista.push(l.replace(/^•\s*/, "")); return; }
      cerrar();
      if (l === l.toUpperCase() && /[A-Z]/.test(l)) out.push(`<h3>${esc(l)}</h3>`); else out.push(`<p>${esc(l)}</p>`);
    });
    cerrar(); return out.join("");
  }
  function textoAgente(html){
    const t = document.createElement("template"); t.innerHTML = html || "";
    t.content.querySelectorAll("*").forEach(el => {
      if (!["P","H2","UL","LI","STRONG","EM","A","BR"].includes(el.tagName)) { el.replaceWith(...el.childNodes); return; }
      [...el.attributes].forEach(a => el.removeAttribute(a.name));
    });
    t.content.querySelectorAll("h2").forEach(h => { const n = document.createElement("h3"); n.textContent = h.textContent; h.replaceWith(n); });
    const d = document.createElement("div"); d.append(t.content); return d.innerHTML;
  }
  const kwChips = (lista, otras) => {
    const c = new Set(otras.map(clave));
    return lista.length ? lista.map(k => `<span class="kw ${c.has(clave(k)) ? "hit" : ""}">${esc(k)}</span>`).join("") : `<span class="kw">ninguna</span>`;
  };
  document.getElementById("fichas").innerHTML = D.actual.fichas.map(f => `
    <article class="ficha">
      <div class="head"><h2>${esc(f.nombre)}</h2>
        <span class="score">keywords en común ${f.kw_en_comun.length}/${f.kw_seo.length} · H1 ${f.h1_igual ? "igual" : pct(f.h1_parecido) + " parecido"}</span></div>
      <div class="cols">
        <div class="col seo"><span class="quien">SEO</span>
          <div class="h1">${esc(f.h1_seo)}</div>
          <div class="kws">${kwChips(f.kw_seo, f.kw_agente)}</div>
          <div class="texto">${textoSEO(f.descripcion_seo)}</div>
          <span class="meta">${f.palabras_seo} palabras</span></div>
        <div class="col agente"><span class="quien">Agente</span>
          <div class="h1">${esc(f.h1_agente)}${f.h1_igual ? '<span class="igual">igual</span>' : ""}</div>
          <div class="kws">${kwChips(f.kw_agente, f.kw_seo)}</div>
          <div class="texto">${textoAgente(f.descripcion_agente)}</div>
          <span class="meta">${f.palabras_agente} palabras</span></div>
      </div>
    </article>`).join("");
  document.getElementById("pie").textContent = D.pie;
})();
</script>
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", required=True)
    ap.add_argument("--base", default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--lectura", action="append", default=[])
    ap.add_argument("--pie", default="")
    a = ap.parse_args(argv)
    datos = {"actual": json.loads(Path(a.eval).read_text(encoding="utf-8")),
             "base": json.loads(Path(a.base).read_text(encoding="utf-8")) if a.base else None,
             "lectura": a.lectura, "pie": a.pie}
    seguro = (json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
              .replace("</", "<\\/").replace("<!--", "<\\!--"))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(PLANTILLA.replace("__DATOS__", seguro), encoding="utf-8")
    print(f"guardado en {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
