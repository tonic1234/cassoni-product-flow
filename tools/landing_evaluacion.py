# -*- coding: utf-8 -*-
"""Página de evaluación de una tanda en seco (identidad Soma, con pestañas).

Lee el JSON de `tools/correr_lote.py` y arma una página autocontenida con cinco
pestañas: Resumen, Fichas, Rechazadas, Cómo funciona y Medición.

    ./venv/bin/python tools/landing_evaluacion.py \
        --json /root/cassoni-eval/2026-11-18/lote-30.json \
        --out  /root/cassoni-eval/2026-11-18/index.html \
        --titulo "Tanda de 30 fichas · 18-nov-2026" --fotos

`--fotos` pide a WooCommerce la imagen principal de cada ficha (lectura, sin costo)
y la usa como miniatura. Sin ese flag la página se arma igual, sin imágenes.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

LOGO = Path("/root/soma-vault/brand/logo-tight.svg")

CSS = """
:root{
  --violet:#782AC2; --violet-600:#8E3FE0; --violet-300:#C99BFF; --violet-50:#F3E9FF;
  --paper:#FAF9F7; --surface:#FFFFFF; --ink:#16121D; --muted:#5B5568; --line:#E6E2EC;
  --ok:#1E6B47; --ok-bg:#E2F3E9; --bad:#9B2C1E; --bad-bg:#FBE7E2; --warn:#7A5300; --warn-bg:#FBF0D6;
  --f-sans:"Manrope",system-ui,-apple-system,"Segoe UI",sans-serif;
  --f-mono:"IBM Plex Mono",ui-monospace,Consolas,monospace;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--f-sans);font-size:15px;line-height:1.6}
a{color:var(--violet);text-decoration:none}
a:hover{text-decoration:underline}
img{display:block;max-width:100%}
.wrap{max-width:1120px;margin:0 auto;padding:0 22px}
header.top{padding:26px 0 0}
.brand{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.brand img{height:26px;width:auto}
.brand .sep{width:1px;height:20px;background:var(--line)}
.brand .ctx{font-size:.78rem;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:600}
.hero{padding:26px 0 18px;display:grid;gap:12px;max-width:74ch}
.hero h1{font-size:clamp(1.7rem,3.4vw,2.5rem);line-height:1.12;margin:0;letter-spacing:-.02em;text-wrap:balance}
.hero p{margin:0;color:var(--muted);font-size:1.02rem}
.tag{display:inline-flex;align-items:center;gap:7px;background:var(--violet-50);color:var(--violet);
  border:1px solid #E2D2F7;border-radius:999px;padding:4px 11px;font-size:.76rem;font-weight:700;letter-spacing:.04em}
.tabs{position:sticky;top:0;z-index:9;background:color-mix(in srgb,var(--paper) 92%,transparent);
  backdrop-filter:blur(8px);border-bottom:1px solid var(--line);margin-top:8px}
.tabs .inner{display:flex;gap:6px;overflow-x:auto;padding:10px 0;scrollbar-width:none}
.tabs .inner::-webkit-scrollbar{display:none}
.tabs button{appearance:none;border:1px solid transparent;background:transparent;color:var(--muted);
  font:600 .88rem/1 var(--f-sans);padding:10px 14px;border-radius:999px;cursor:pointer;white-space:nowrap}
.tabs button:hover{color:var(--ink);background:#F1EDF7}
.tabs button[aria-selected="true"]{background:var(--violet);color:#fff}
main{padding:26px 0 90px}
section[hidden]{display:none}
.grid{display:grid;gap:18px}
.kpis{display:grid;grid-template-columns:repeat(2,1fr);gap:1px;background:var(--line);
  border:1px solid var(--line);border-radius:14px;overflow:hidden}
@media (min-width:760px){.kpis{grid-template-columns:repeat(3,1fr)}}
.kpi{background:var(--surface);padding:16px 18px;display:grid;gap:3px}
.kpi b{font-family:var(--f-mono);font-size:1.5rem;font-weight:500;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.kpi span{font-size:.8rem;color:var(--muted)}
.kpi.acento{background:var(--violet-50)}
.card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:20px 22px}
.card h2{font-size:1.12rem;margin:0 0 10px;letter-spacing:-.01em}
.card p{margin:0 0 10px;max-width:74ch}
.card p:last-child{margin-bottom:0}
ul.limpia{margin:8px 0 0;padding-left:20px;display:grid;gap:6px;max-width:78ch}
.mono{font-family:var(--f-mono);font-variant-numeric:tabular-nums}
.ficha{background:var(--surface);border:1px solid var(--line);border-radius:16px;overflow:hidden;display:grid}
.ficha .cab{display:grid;grid-template-columns:104px 1fr;gap:16px;align-items:start;padding:16px 18px 0}
.foto-caja{position:relative;width:104px;height:104px;border-radius:12px;overflow:hidden;
  background:linear-gradient(135deg,#F3E9FF,#E4D5F9);border:1px solid var(--line);display:grid;place-items:center}
.foto-caja .inicial{font-weight:800;font-size:1.35rem;letter-spacing:.02em;color:#5B2E8F}
.foto-caja img.foto{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;background:#F1EDF7}
.ficha h3{margin:0 0 4px;font-size:1.04rem;line-height:1.3}
.meta-linea{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:6px}
.pill{font-size:.72rem;font-weight:700;padding:3px 9px;border-radius:999px;border:1px solid transparent;letter-spacing:.02em}
.pill.ok{background:var(--ok-bg);color:var(--ok)}
.pill.bad{background:var(--bad-bg);color:var(--bad)}
.pill.gris{background:#F1EDF7;color:var(--muted)}
.h1{display:grid;gap:2px;padding:12px 18px 0}
.h1 .l{font-size:.7rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:700}
.h1 del{color:var(--muted);text-decoration-color:#C9C2D6}
.h1 ins{text-decoration:none;font-weight:700}
.h1 ins em{font-style:normal;color:var(--violet)}
.kws{display:flex;gap:8px;flex-wrap:wrap;padding:12px 18px 0}
.kw{display:inline-flex;flex-direction:column;gap:1px;background:var(--violet-50);border:1px solid #E2D2F7;
  border-radius:10px;padding:6px 10px}
.kw b{font-size:.84rem;font-weight:700;color:#3A1670}
.kw small{font-size:.7rem;color:#6B4A96}
.texto{padding:12px 18px 16px;font-size:.92rem;color:#2C2537;display:grid;gap:8px}
.texto p{margin:0}
.texto h4{margin:6px 0 0;font-size:.9rem;letter-spacing:.02em}
mark{background:#FFE9A8;color:#3A2E00;padding:0 2px;border-radius:3px}
.val{padding:0 18px 18px;font-size:.84rem;color:var(--muted)}
.val b{color:var(--ink)}
details.desc{padding:0 18px 16px}
details.desc summary{cursor:pointer;font-size:.83rem;color:var(--violet);font-weight:600}
details.desc ul{margin:8px 0 0;padding-left:18px;font-size:.82rem;color:var(--muted);display:grid;gap:4px}
.pasos{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.paso{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px 18px}
.paso .n{font-family:var(--f-mono);font-size:.74rem;color:var(--violet);font-weight:600;letter-spacing:.08em}
.paso h3{margin:6px 0 6px;font-size:.98rem}
.paso p{margin:0;font-size:.88rem;color:var(--muted)}
table{width:100%;border-collapse:collapse;font-size:.88rem}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:.72rem;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
td.num{text-align:right;font-family:var(--f-mono);font-variant-numeric:tabular-nums}
.aviso{background:var(--warn-bg);border:1px solid #EFDCA6;color:#4A3300;border-radius:12px;padding:12px 16px;font-size:.88rem}
footer{border-top:1px solid var(--line);padding:18px 0 40px;color:var(--muted);font-size:.8rem}
@media (max-width:620px){
  .ficha .cab{grid-template-columns:1fr}
  .ficha .foto{width:100%;height:170px}
  .hero h1{font-size:1.6rem}
}
@media (prefers-reduced-motion:no-preference){.tabs button{transition:background .15s,color .15s}}
"""

JS = """
const tabs = [...document.querySelectorAll('.tabs button')];
function show(id){
  tabs.forEach(b => b.setAttribute('aria-selected', String(b.dataset.tab === id)));
  document.querySelectorAll('main > section').forEach(s => s.hidden = (s.id !== id));
  if (location.hash !== '#' + id) history.replaceState(null, '', '#' + id);
}
tabs.forEach(b => b.addEventListener('click', () => show(b.dataset.tab)));
show((location.hash || '').slice(1) && document.getElementById(location.hash.slice(1)) ? location.hash.slice(1) : 'resumen');
"""


def esc(t) -> str:
    return html.escape(str(t or ""))


def marcar(texto_html: str, kws: list[str]) -> str:
    """Envuelve las keywords en <mark> sin tocar el HTML ya escapado."""
    if not kws:
        return texto_html
    patron = "|".join(sorted((re.escape(k) for k in kws if k), key=len, reverse=True))
    if not patron:
        return texto_html
    return re.sub(f"({patron})", r"<mark>\1</mark>", texto_html, flags=re.IGNORECASE)


def texto_de_desc(desc: str, kws: list[str]) -> str:
    """Convierte la descripción (HTML o texto) en párrafos con las keywords marcadas."""
    crudo = desc or ""
    if "<" in crudo:
        bloques = re.split(r"</(?:p|h2|h3|li|div)>", crudo, flags=re.IGNORECASE)
        partes = []
        for b in bloques:
            es_h2 = bool(re.search(r"<h2", b, re.IGNORECASE))
            limpio = re.sub(r"<[^>]+>", "", b).strip()
            if not limpio:
                continue
            marca = esc(limpio)
            marca = marcar(marca, kws)
            partes.append(f"<h4>{marca}</h4>" if es_h2 else f"<p>{marca}</p>")
        return "".join(partes)
    parrafos = [p.strip() for p in re.split(r"\n{1,}", crudo) if p.strip()]
    return "".join(f"<p>{marcar(esc(p), kws)}</p>" for p in parrafos)


def descartadas(sel: str) -> list[tuple[str, str]]:
    i = (sel or "").find("descartadas:")
    if i < 0:
        return []
    crudo = sel[i + len("descartadas:"):]
    out = []
    for trozo in re.split(r";\s(?=[^()]*(?:\(|$))", crudo):
        t = trozo.strip().rstrip(".")
        if not t:
            continue
        m = re.match(r"^(.*?)\s*\((.*)\)$", t)
        out.append((m.group(1), m.group(2)) if m else (t, ""))
    return out


def resaltar_agregado(h1_nuevo: str, h1_original: str) -> str:
    """Marca en el H1 propuesto las palabras que no estaban en el nombre original."""
    if not h1_nuevo:
        return ""
    previas = {w.lower() for w in re.findall(r"[\w\u00c0-\u024f]+", h1_original or "")}
    piezas = re.findall(r"\s+|[^\s]+", h1_nuevo)
    salida, buffer = [], []
    for pieza in piezas:
        if pieza.isspace():
            if buffer:
                buffer.append(pieza)
            else:
                salida.append(esc(pieza))
            continue
        limpia = re.sub(r"[^\w\u00c0-\u024f]+", "", pieza).lower()
        if limpia and limpia not in previas:
            buffer.append(pieza)
        else:
            if buffer:
                salida.append(f"<em>{esc(''.join(buffer).strip())}</em>")
                buffer = []
            salida.append(esc(pieza))
    if buffer:
        salida.append(f"<em>{esc(''.join(buffer).strip())}</em>")
    return "".join(salida)


def logo_data_uri() -> str:
    if not LOGO.exists():
        return ""
    import base64
    return "data:image/svg+xml;base64," + base64.b64encode(LOGO.read_bytes()).decode()


def fichas_con_foto(fichas: list[dict], env: str) -> None:
    """Agrega la imagen principal de cada ficha (lectura a WooCommerce)."""
    from cassoni.config import Config
    from cassoni.extract import extract_slug
    from cassoni.woo import WooCommerce

    cfg = Config.load(env, dry_run=True)
    woo = WooCommerce(cfg)
    for f in fichas:
        try:
            slug = extract_slug(f["url"])[0]
            p = woo.get_product_by_slug(slug)
            imagenes = p.get("images") or []
            f["imagen"] = imagenes[0].get("src") if imagenes else ""
            f["precio"] = p.get("price") or ""
            f["marca_woo"] = ((p.get("brands") or [{}])[0].get("name")
                              if p.get("brands") else "")
        except Exception as exc:                      # la página se arma igual
            f["imagen"] = ""
            print(f"  sin foto: {f['url']} ({exc})", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--titulo", default="Evaluación de una tanda en seco")
    ap.add_argument("--env", default="prod")
    ap.add_argument("--fotos", action="store_true")
    a = ap.parse_args()

    datos = json.loads(Path(a.json).read_text(encoding="utf-8"))
    meta = datos.get("meta") or {}
    fichas = datos.get("fichas") or []
    if a.fotos:
        fichas_con_foto(fichas, a.env)

    aprobadas = [f for f in fichas if f.get("status") == "processed"
                 and (f.get("validacion") or {}).get("aprobado") is not False]
    rechazadas = [f for f in fichas if f.get("status") == "rejected"
                  or (f.get("validacion") or {}).get("aprobado") is False]
    fallidas = [f for f in fichas if f.get("status") not in ("processed", "rejected")]
    costos = meta.get("costos") or {}
    usd_llm = float(costos.get("usd") or 0)
    usd_dfs = float(costos.get("dfs_usd") or 0)
    total_usd = usd_llm + usd_dfs
    por_ficha = total_usd / len(fichas) if fichas else 0
    segundos = sum(float(f.get("segundos") or 0) for f in fichas)

    def palabras(html_txt: str) -> int:
        plano = re.sub(r"<[^>]+>", " ", html_txt or "")
        return len([w for w in html.unescape(plano).split() if w.strip()])

    pal_antes = [palabras(f.get("descripcion_original")) for f in fichas]
    pal_desp = [palabras(f.get("descripcion")) for f in fichas if f.get("descripcion")]
    med_antes = int(sum(pal_antes) / len(pal_antes)) if pal_antes else 0
    med_desp = int(sum(pal_desp) / len(pal_desp)) if pal_desp else 0
    kws_total = sum(len(f.get("keywords") or []) for f in fichas)
    sin_kw = sum(1 for f in fichas if not f.get("keywords"))
    pierden = [f for f in fichas if f.get("perdidas_h1")]

    E = []
    E.append(f"""<header class="top"><div class="wrap">
  <div class="brand">
    <img src="{logo_data_uri()}" alt="Soma">
    <span class="sep"></span><span class="ctx">Cassoni · Agente SEO</span>
  </div>
  <div class="hero">
    <span class="tag">Corrida en seco · nada se escribió en la tienda</span>
    <h1>{esc(a.titulo)}</h1>
    <p>Treinta fichas reales procesadas por el agente: elige el trabajo desde Search Console, decide el H1 y las
    keywords en código, redacta con DeepSeek y un segundo modelo lo juzga. Todo lo de abajo salió de esta corrida,
    incluidos los rechazos.</p>
  </div>
</div></header>""")

    E.append("""<nav class="tabs"><div class="wrap inner" role="tablist">""" +
             "".join(f'<button role="tab" data-tab="{i}" aria-selected="false">{t}</button>'
                     for i, t in [("resumen", "Resumen"), ("fichas", "Las fichas"),
                                  ("rechazadas", "Rechazadas"), ("como", "Cómo funciona"),
                                  ("medicion", "Medición")]) +
             "</div></nav>")

    E.append('<main class="wrap">')

    # --- Resumen
    E.append(f"""<section id="resumen"><div class="grid">
  <div class="kpis">
    <div class="kpi"><b>{len(fichas)}</b><span>fichas procesadas</span></div>
    <div class="kpi acento"><b>{len(aprobadas)}</b><span>aprobadas por el validador</span></div>
    <div class="kpi"><b>{len(rechazadas)}</b><span>rechazadas, con el motivo escrito</span></div>
    <div class="kpi"><b>{kws_total}</b><span>keywords elegidas</span></div>
    <div class="kpi"><b>{sin_kw}</b><span>fichas sin keyword objetivo</span></div>
    <div class="kpi"><b>{len(pierden)}</b><span>H1 que pierden un término del nombre</span></div>
    <div class="kpi"><b>US$ {total_usd:.2f}</b><span>costo total de la tanda</span></div>
    <div class="kpi"><b>US$ {por_ficha:.4f}</b><span>por ficha</span></div>
    <div class="kpi"><b>{segundos/60:.0f} min</b><span>de corrida</span></div>
  </div>
  <div class="card">
    <h2>Qué se corrió</h2>
    <table>
      <tr><th>Modo</th><td>{esc(meta.get('modo'))} · código <span class="mono">{esc((meta.get('commit') or '')[:8])}</span></td></tr>
      <tr><th>Modelo</th><td>{esc(meta.get('llm'))}</td></tr>
      <tr><th>Escritura en la tienda</th><td>{'ninguna (dry-run)' if meta.get('dry_run') else 'ESCRITURA HABILITADA'}</td></tr>
      <tr><th>LLM</th><td class="num">US$ {usd_llm:.4f} · {int(costos.get('llamadas') or 0)} llamadas · {(int(costos.get('tokens_in') or 0)):,} tokens in / {(int(costos.get('tokens_out') or 0)):,} out</td></tr>
      <tr><th>DataForSEO</th><td class="num">US$ {usd_dfs:.4f}</td></tr>
      <tr><th>Descripción</th><td class="num">{med_antes} → {med_desp} palabras (promedio)</td></tr>
    </table>
  </div>
  <div class="aviso"><b>Nada de esto está publicado.</b> Las fichas se leyeron de cassoni.com y no se escribió un solo campo.
  Para pasar a la tienda hace falta el OK del equipo SEO y una corrida de una ficha verificada desde afuera.</div>
</div></section>""")

    # --- Fichas
    cuerpo = []
    for i, f in enumerate(fichas, 1):
        kws = f.get("keywords_detalle") or []
        val = f.get("validacion") or {}
        ok = f.get("status") == "processed" and val.get("aprobado") is not False
        foto = (f'<img class="foto" src="{esc(f.get("imagen"))}" alt="" loading="lazy" '
                f'onerror="this.remove()">' if f.get("imagen") else "")
        iniciales = "".join(w[0] for w in re.findall(r"[A-Za-zÁÉÍÓÚÑ]+",
                                                    f.get("h1_original") or "")[:2]).upper() or "·"
        foto = f'<div class="foto-caja"><span class="inicial">{esc(iniciales)}</span>{foto}</div>'
        chips = "".join(
            f'<span class="kw"><b>{esc(k.get("keyword"))}</b><small>'
            f'{int(k.get("volume") or k.get("volumen") or 0):,}/mes · {esc(k.get("origen"))}'
            f'{(" · pos " + format(float(k["posicion"]), ".1f")) if k.get("posicion") else ""}</small></span>'
            for k in kws) or '<span class="pill gris">ninguna keyword pasó los filtros</span>'
        desc = descartadas(f.get("seleccion") or "")
        det = (f'<details class="desc"><summary>Las {len(desc)} descartadas y por qué</summary><ul>' +
               "".join(f"<li><b>{esc(d[0])}</b> — {esc(d[1])}</li>" for d in desc) + "</ul></details>") if desc else ""
        motivo = " ".join(val.get("issues") or []) or val.get("razon") or f.get("reason") or ""
        perdidas = f.get("perdidas_h1") or []
        aviso = (f'<p class="val"><b>Ojo:</b> el H1 propuesto no conserva '
                 f'{", ".join("«" + esc(p) + "»" for p in perdidas)} del nombre original. '
                 f'Es un término de búsqueda que se pierde.</p>') if perdidas else ""
        cuerpo.append(f"""<article class="ficha">
  <div class="cab">{foto}<div>
    <h3><a href="{esc(f.get('url'))}" target="_blank" rel="noopener">{esc(f.get('h1_original') or f.get('url'))}</a></h3>
    <div class="meta-linea">
      <span class="pill {'ok' if ok else 'bad'}">{'Aprobada' if ok else 'Rechazada'}</span>
      <span class="pill gris">{esc(f.get('intentos') or 1)} intento(s)</span>
      <span class="pill gris">{float(f.get('segundos') or 0):.0f} s</span>
    </div>
  </div></div>
  <div class="h1"><span class="l">H1 en la tienda</span><del>{esc(f.get('h1_original'))}</del>
    <span class="l">H1 propuesto</span><ins>{resaltar_agregado(f.get('h1') or '', f.get('h1_original') or '')}</ins></div>
  <div class="kws">{chips}</div>
  <div class="texto">{texto_de_desc(f.get('descripcion') or f.get('descripcion_original') or '', [k.get('keyword') or '' for k in kws])}</div>
  {det}
  {aviso}
  <p class="val"><b>Validador:</b> {esc(motivo) if not ok else 'sin observaciones'}</p>
</article>""")
    E.append(f"""<section id="fichas" hidden><div class="grid">
  <div class="card"><h2>Las {len(fichas)} fichas</h2>
  <p>El H1 nuevo se escribe en WooCommerce <b>sin la marca</b>: la tienda agrega «by + marca» con el logo del
  fabricante. Lo resaltado en violeta son las palabras que el agente agrega al nombre original; en la descripción,
  lo amarillo son las keywords objetivo. Las miniaturas son las iniciales del producto: cassoni.com bloquea
  (Cloudflare) que sus fotos se muestren desde otro dominio.</p></div>
  {''.join(cuerpo)}
</div></section>""")

    # --- Rechazadas
    if rechazadas:
        filas = []
        for f in rechazadas:
            val = f.get("validacion") or {}
            motivo = " ".join(val.get("issues") or []) or val.get("razon") or f.get("reason") or ""
            filas.append(f"""<article class="ficha"><div class="cab"><div>
  <h3><a href="{esc(f.get('url'))}" target="_blank" rel="noopener">{esc(f.get('h1_original'))}</a></h3>
  <div class="meta-linea"><span class="pill bad">Rechazada</span>
  <span class="pill gris">{esc(f.get('h1'))}</span></div></div></div>
  <p class="val">{esc(motivo)}</p></article>""")
        E.append(f"""<section id="rechazadas" hidden><div class="grid">
  <div class="card"><h2>Por qué se rechazan</h2>
  <p>Un rechazo honesto vale más que una tanda toda verde. El validador frena datos que no están en la ficha,
  keywords forzadas y oraciones armadas sólo para meter una palabra. Estas fichas quedan sin escribir.</p></div>
  {''.join(filas)}
</div></section>""")
    else:
        E.append("""<section id="rechazadas" hidden><div class="card"><h2>Sin rechazos</h2>
  <p>En esta tanda el validador aprobó todas las fichas.</p></div></section>""")

    # --- Cómo funciona
    E.append("""<section id="como" hidden><div class="grid">
  <div class="card"><h2>Cómo decide, paso a paso</h2>
  <p>Nada de esto lo decide el modelo: el modelo sólo redacta. Las reglas están en código y cualquiera puede leerlas
  en el repo.</p></div>
  <div class="pasos">
    <div class="paso"><span class="n">01 · QUÉ FICHA</span><h3>Search Console</h3>
      <p>Toma las fichas con demanda real (≥ 50 impresiones en 90 días) y descarta la cola sin clics. Ordena por
      oportunidad, no por volumen: la consulta con 5.000 impresiones en posición 2 no tiene nada que ganar.</p></div>
    <div class="paso"><span class="n">02 · QUÉ ES</span><h3>Tipo en inglés</h3>
      <p>Del nombre y la categoría: <i>wall sconce</i>, <i>bar stool</i>, <i>coffee table</i>. En inglés de EE. UU.,
      porque es como se busca.</p></div>
    <div class="paso"><span class="n">03 · H1</span><h3>Lo que la gente busca</h3>
      <p>Si el nombre ya se busca (≥ 1.000/mes) va nombre + marca. Si no, nombre + rasgo + tipo + marca. El rasgo es
      el material que comparten todas las versiones, y entre esos el más buscado.</p></div>
    <div class="paso"><span class="n">04 · KEYWORDS</span><h3>Tres fuentes, en código</h3>
      <p>Consultas que la ficha ya atrae en Search Console, marca + tipo con volumen, y una genérica sólo si nombra
      el material del H1. Se descartan las de categoría y las de otro producto.</p></div>
    <div class="paso"><span class="n">05 · TEXTO</span><h3>DeepSeek con los ejemplos del SEO</h3>
      <p>Las diez fichas que escribió el equipo SEO son el ejemplo del prompt. Apertura, dos secciones, un dato para
      decidir la compra, medidas en pulgadas, enlace a la categoría, 60-110 palabras.</p></div>
    <div class="paso"><span class="n">06 · CONTROL</span><h3>Reglas y un segundo modelo</h3>
      <p>Los números se controlan en código contra los atributos reales de la ficha. Después un segundo modelo juzga
      tono, datos inventados y keywords forzadas. Hasta tres intentos con los motivos; si no aprueba, no se escribe.</p></div>
  </div>
</div></section>""")

    # --- Medición
    E.append(f"""<section id="medicion" hidden><div class="grid">
  <div class="card"><h2>Qué mide esto y qué no</h2>
  <p>Esta tanda mide <b>calidad</b>: si el H1, las keywords y el texto están bien. Todavía no mide <b>resultado</b>:
  si la ficha posiciona y recibe clics. Para eso hay que escribir en la tienda y esperar, y eso no se hizo.</p>
  <ul class="limpia">
    <li><b>Lo que sí dice esta página:</b> {len(aprobadas)} de {len(fichas)} fichas pasaron el validador, a
    US$ {por_ficha:.4f} por ficha, con el motivo de cada rechazo escrito.</li>
    <li><b>Lo que no dice:</b> nada sobre posiciones ni clics. Y no prueba conversión: no hay acceso a pedidos.</li>
    <li><b>El resorte que falta:</b> las fichas con más oportunidad ya están en posición 4-15 y reciben pocos clics.
    Lo que destraba eso es el título y la meta descripción del resultado de Google, que hoy escribe el n8n.</li>
  </ul></div>
  <div class="card"><h2>El test de resultado, cuando se autorice</h2>
  <table>
    <tr><th>Diseño</th><td><b>40 fichas escritas + 40 testigo</b>, apareadas por posición e impresiones (diferencia de diferencias)</td></tr>
    <tr><th>Métrica primaria</th><td>clics de la consulta objetivo</td></tr>
    <tr><th>Poder</th><td>con 432 clics de base el ruido es ±21 (1 desvío): un efecto del 20% se ve a 4 desvíos; con 10 fichas no se ve nada</td></tr>
    <tr><th>Lecturas</th><td>28 y 56 días después de escribir, con los 3 días de demora de Search Console descontados</td></tr>
    <tr><th>Control negativo</th><td>el mismo análisis con 40 pares no tratados: si ese también «mejora», lo que se mide es la estación</td></tr>
    <tr><th>Antes de escribir</th><td>botón de volver atrás probado (<span class="mono">tools/restaurar.py</span>) y una ficha escrita verificada desde afuera</td></tr>
  </table></div>
</div></section>""")

    E.append("</main>")
    E.append("""<footer><div class="wrap">Soma · agente SEO para Cassoni · página generada por
<span class="mono">tools/landing_evaluacion.py</span> a partir del JSON de la corrida. Sin datos de clientes:
todo sale de fichas públicas de cassoni.com.</div></footer>""")

    html_out = f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>{esc(a.titulo)}</title>
<meta property="og:type" content="website">
<meta property="og:site_name" content="Soma">
<meta property="og:title" content="{esc(a.titulo)}">
<meta property="og:description" content="30 fichas reales de cassoni.com procesadas en seco: H1, keywords y descripción, con el veredicto del validador.">
<meta property="og:image" content="og.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>{CSS}</style></head><body>
{''.join(E)}
<script>{JS}</script></body></html>"""

    salida = Path(a.out)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(html_out, encoding="utf-8")
    print(f"{salida} · {len(fichas)} fichas · {len(aprobadas)} aprobadas · {len(rechazadas)} rechazadas · "
          f"{len(html_out)/1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
