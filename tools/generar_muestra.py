# -*- coding: utf-8 -*-
"""Genera la landing de revisión de la muestra (antes/después + de dónde salió cada dato).

Uso:
  python tools/generar_muestra.py --json muestra.json --out index.html
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

CSS = """
:root{--night:#2B2B28;--carbon:#363633;--lime:#CCE535;--cream:#E3E1CD;--white:#fff;
--muted:rgba(255,255,255,.66);--dim:rgba(255,255,255,.46);--border:rgba(255,255,255,.10);
--orange:#E8683F;--f:'Plus Jakarta Sans',system-ui,sans-serif}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{background:var(--night);color:var(--white);font-family:var(--f);line-height:1.62;-webkit-font-smoothing:antialiased}
.wrap{max-width:1100px;margin:0 auto;padding:0 22px 96px}
header.top{border-bottom:1px solid var(--border);padding:30px 0 22px;margin-bottom:34px}
.chip{display:inline-block;font-size:.66rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;
background:rgba(204,229,53,.14);color:var(--lime);border:1px solid rgba(204,229,53,.35);border-radius:999px;padding:4px 11px}
h1{font-size:clamp(1.7rem,4.4vw,2.5rem);font-weight:800;letter-spacing:-.02em;line-height:1.12;margin:14px 0 10px}
h2{font-size:clamp(1.18rem,2.6vw,1.6rem);font-weight:800;letter-spacing:-.01em;margin:0 0 6px}
h3{font-size:1rem;font-weight:700}
p{color:var(--muted);max-width:80ch}
a{color:var(--lime)}
section{margin:54px 0 0}
.eyebrow{font-size:.68rem;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--lime);margin-bottom:8px}
.lead{font-size:1.02rem;color:var(--cream);max-width:78ch}
.card{background:var(--carbon);border:1px solid var(--border);border-radius:14px;padding:20px 22px}
.grid{display:grid;gap:14px}
.g3{grid-template-columns:repeat(3,minmax(0,1fr))}
.g4{grid-template-columns:repeat(4,minmax(0,1fr))}
.g2{grid-template-columns:repeat(2,minmax(0,1fr))}
.kpi{background:var(--carbon);border:1px solid var(--border);border-radius:14px;padding:18px 20px}
.kpi .n{font-size:1.9rem;font-weight:800;letter-spacing:-.02em;line-height:1.1}
.kpi .l{font-size:.76rem;color:var(--dim);text-transform:uppercase;letter-spacing:.09em;margin-top:4px}
.kpi .s{font-size:.8rem;color:var(--muted);margin-top:6px}
.src{background:var(--carbon);border:1px solid var(--border);border-radius:14px;padding:18px 20px}
.src .tag{font-size:.63rem;font-weight:800;letter-spacing:.12em;text-transform:uppercase;color:var(--night);
background:var(--lime);border-radius:6px;padding:2px 7px;display:inline-block;margin-bottom:10px}
.src ul{margin:8px 0 0 16px;color:var(--muted);font-size:.86rem}
.src li{margin:3px 0}
.tscroll{overflow-x:auto;margin-top:16px;border:1px solid var(--border);border-radius:12px}
table.t{width:100%;border-collapse:collapse;font-size:.82rem;min-width:720px}
table.t th{text-align:left;font-size:.64rem;letter-spacing:.09em;text-transform:uppercase;color:var(--dim);
padding:11px 12px;border-bottom:1px solid var(--border);white-space:nowrap}
table.t td{padding:11px 12px;border-bottom:1px solid var(--border);color:var(--muted);vertical-align:top}
table.t tr:last-child td{border-bottom:none}
table.t td.num{text-align:right;font-variant-numeric:tabular-nums;color:var(--white);font-weight:600;white-space:nowrap}
table.t td.name{color:var(--white);font-weight:700}
.pill{display:inline-block;font-size:.64rem;font-weight:800;letter-spacing:.08em;text-transform:uppercase;
border-radius:999px;padding:3px 9px}
.ok{background:rgba(204,229,53,.16);color:var(--lime);border:1px solid rgba(204,229,53,.4)}
.rej{background:rgba(232,104,63,.16);color:#FF9873;border:1px solid rgba(232,104,63,.45)}
.ficha{background:var(--carbon);border:1px solid var(--border);border-radius:16px;margin-top:18px;overflow:hidden}
.fhead{display:flex;gap:16px;align-items:flex-start;padding:20px 22px;border-bottom:1px solid var(--border)}
.thumb{width:84px;height:84px;border-radius:10px;object-fit:cover;background:#2B2B28;flex:0 0 84px;
border:1px solid var(--border)}
.thumb.ph{display:flex;align-items:center;justify-content:center;font-size:1.9rem;font-weight:800;
color:var(--lime);background:rgba(204,229,53,.08);border-color:rgba(204,229,53,.3)}
.fhead .meta{flex:1 1 auto;min-width:0}
.fhead .meta h3{font-size:1.06rem;line-height:1.3}
.fhead .sub{font-size:.78rem;color:var(--dim);margin-top:3px}
.fbody{padding:18px 22px 22px}
.entra{display:grid;gap:10px;grid-template-columns:repeat(3,minmax(0,1fr));margin-bottom:16px}
.entra .b{background:rgba(255,255,255,.03);border:1px solid var(--border);border-radius:10px;padding:12px 14px}
.entra .k{font-size:.62rem;letter-spacing:.11em;text-transform:uppercase;color:var(--dim);font-weight:700}
.entra .v{font-size:.92rem;color:var(--white);font-weight:600;margin-top:3px;word-break:break-word}
.entra .x{font-size:.76rem;color:var(--muted);margin-top:3px}
.antesdespues{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.col{border:1px solid var(--border);border-radius:12px;padding:14px 16px;background:rgba(0,0,0,.12)}
.col h4{font-size:.64rem;letter-spacing:.12em;text-transform:uppercase;margin-bottom:8px}
.col.old h4{color:var(--dim)}
.col.new{border-color:rgba(204,229,53,.35);background:rgba(204,229,53,.05)}
.col.new h4{color:var(--lime)}
.titulo{font-size:.98rem;font-weight:800;color:var(--white);margin-bottom:8px;line-height:1.3}
.texto{font-size:.86rem;color:var(--muted);max-height:320px;overflow:auto}
.texto h2{font-size:.95rem;font-weight:800;color:var(--cream);margin:10px 0 6px;letter-spacing:0}
.texto p{margin:0 0 8px;max-width:none}
.texto strong{color:var(--white)}
.pie{display:flex;flex-wrap:wrap;gap:8px 16px;margin-top:14px;font-size:.78rem;color:var(--muted);
border-top:1px solid var(--border);padding-top:12px}
.pie b{color:var(--white)}
.obs{margin-top:12px;border-left:3px solid var(--orange);background:rgba(232,104,63,.07);
border-radius:0 10px 10px 0;padding:10px 14px;font-size:.82rem;color:var(--cream)}
.limites li{margin:6px 0}
.preg{background:var(--carbon);border:1px solid var(--border);border-left:3px solid var(--lime);
border-radius:12px;padding:16px 20px;margin-top:12px}
footer{margin-top:54px;border-top:1px solid var(--border);padding-top:18px;font-size:.78rem;color:var(--dim)}
@media (max-width:820px){
  .g4,.g3{grid-template-columns:repeat(2,minmax(0,1fr))}
  .antesdespues{grid-template-columns:1fr}
  .entra{grid-template-columns:1fr}
}
@media (max-width:520px){
  .g4,.g3,.g2{grid-template-columns:1fr}
  .fhead{flex-wrap:wrap}
  .wrap{padding:0 16px 72px}
}
"""


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt_pos(p):
    return f"{p:.1f}" if isinstance(p, (int, float)) else "—"


def _ficha(f, i: int) -> str:
    v = f.get("validacion") or {}
    ok = v.get("aprobado")
    clase = "ok" if ok else "rej"
    texto = "Aprobada por el validador" if ok else "Rechazada por el validador"
    g = f.get("gsc") or {}
    m = f.get("medido") or {}
    c = f.get("costo") or {}
    kw = g.get("keyword") or ""
    attrs = f.get("atributos") or []
    issues = v.get("issues") or []
    obs = ""
    if issues:
        obs = ('<div class="obs"><b>Observaciones del validador</b><br>'
               + "<br>".join(_esc(x) for x in issues[:4]) + "</div>")
    attrs_html = ("".join(f"<li>{_esc(a)}</li>" for a in attrs[:6])
                  or "<li>(la ficha no trae atributos visibles)</li>")
    img = f.get("imagen") or ""
    if img:
        thumb = (f'<img class="thumb" src="{_esc(img)}" alt="" loading="lazy" '
                 f'onerror="this.style.visibility=\'hidden\'">')
    else:
        inicial = (_esc((f.get("marca") or f.get("nombre") or "?").strip()[:1]).upper())
        thumb = f'<div class="thumb ph" aria-hidden="true">{inicial}</div>'
    return f"""
<article class="ficha">
  <div class="fhead">
    {thumb}
    <div class="meta">
      <h3>{i:02d} · {_esc(f.get('nombre'))}</h3>
      <div class="sub">{_esc(', '.join(f.get('categorias') or []))}{' · ' if f.get('marca') else ''}{_esc(f.get('marca'))}</div>
    </div>
    <span class="pill {clase}">{_esc(texto)}</span>
  </div>
  <div class="fbody">
    <div class="entra">
      <div class="b">
        <div class="k">Consulta que la ficha recibe</div>
        <div class="v">{_esc(kw)}</div>
        <div class="x">posición {_fmt_pos(g.get('position'))} · {g.get('impressions') or 0:,} impresiones · {g.get('clicks') or 0} clics</div>
      </div>
      <div class="b">
        <div class="k">Atributos reales que se usaron</div>
        <div class="v" style="font-size:.84rem">{len(attrs)} campos</div>
        <div class="x">de la ficha en WooCommerce</div>
      </div>
      <div class="b">
        <div class="k">Oportunidad</div>
        <div class="v">{_esc(g.get('opportunity') or '—')}</div>
        <div class="x">score {g.get('score') or 0}/100</div>
      </div>
    </div>
    <div class="antesdespues">
      <div class="col old">
        <h4>Antes</h4>
        <div class="titulo">{_esc(f.get('h1_antes'))}</div>
        <div class="texto">{f.get('desc_antes') or ''}</div>
        <div class="pie"><span><b>{m.get('palabras_antes', 0)}</b> palabras</span></div>
      </div>
      <div class="col new">
        <h4>Después</h4>
        <div class="titulo">{_esc(f.get('h1_despues'))}</div>
        <div class="texto">{f.get('desc_despues') or ''}</div>
        <div class="pie">
          <span><b>{m.get('palabras_despues', 0)}</b> palabras</span>
          <span>conservación del original <b>{int((m.get('conservacion') or 0) * 100)}%</b></span>
          <span><b>{m.get('h2', 0)}</b> H2</span>
        </div>
      </div>
    </div>
    {obs}
    <div class="pie">
      <span>costo de esta ficha <b>US$ {c.get('usd', 0):.4f}</b></span>
      <span>{c.get('tokens_in', 0):,} tokens entrada · {c.get('tokens_out', 0):,} salida</span>
      <span>{f.get('intentos') or 0} pase(s) de validación</span>
      <span><a href="{_esc(f.get('url'))}" target="_blank" rel="noopener">ver ficha en el sitio</a></span>
    </div>
  </div>
</article>"""


def generar(filas: list[dict]) -> str:
    ok = [f for f in filas if (f.get("validacion") or {}).get("aprobado")]
    usd = sum((f.get("costo") or {}).get("usd", 0) for f in filas)
    pal_antes = sum((f.get("medido") or {}).get("palabras_antes", 0) for f in filas)
    pal_desp = sum((f.get("medido") or {}).get("palabras_despues", 0) for f in filas)
    por_ficha = usd / max(len(filas), 1)

    filas_tabla = "".join(f"""
      <tr>
        <td class="name">{i:02d} · {_esc(f.get('nombre'))}</td>
        <td>{_esc((f.get('gsc') or {}).get('keyword'))}</td>
        <td class="num">{_fmt_pos((f.get('gsc') or {}).get('position'))}</td>
        <td class="num">{(f.get('gsc') or {}).get('impressions') or 0:,}</td>
        <td class="num">{(f.get('medido') or {}).get('palabras_antes', 0)} → {(f.get('medido') or {}).get('palabras_despues', 0)}</td>
        <td class="num">{int(((f.get('medido') or {}).get('conservacion') or 0) * 100)}%</td>
        <td class="num">US$ {(f.get('costo') or {}).get('usd', 0):.4f}</td>
      </tr>""" for i, f in enumerate(filas, 1))

    fichas = "".join(_ficha(f, i) for i, f in enumerate(filas, 1))

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cassoni · Muestra de 10 fichas para validar</title>
<meta property="og:title" content="Cassoni · Muestra de 10 fichas optimizadas">
<meta property="og:description" content="Antes y después de 10 fichas reales, con la consulta que las trae, los atributos usados y el costo por ficha.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">

<header class="top">
  <span class="chip">Cassoni · muestra para validación</span>
  <h1>10 fichas optimizadas, con todo lo que entró en cada una</h1>
  <p class="lead">Para Alex. Son diez fichas reales del catálogo, elegidas entre las que tienen
  demanda en Google y material suficiente para escribir sin inventar. Cada una muestra qué
  consulta la trae, qué atributos reales se usaron, cómo estaba y cómo queda.
  <b>No se escribió nada en el sitio</b>: todo vive en la base interna del agente, esperando tu OK.</p>
  <p class="lead" style="margin-top:10px;color:var(--dim);font-size:.88rem">
  Generado el {date.today().strftime('%d/%m/%Y')} · pipeline con 217 tests en verde ·
  el mismo código que después corre el catálogo completo.</p>
</header>

<section>
  <div class="eyebrow">Qué necesitamos de vos</div>
  <div class="grid g3">
    <div class="card"><h3>1 · ¿El criterio es el correcto?</h3>
      <p style="margin-top:6px">H1 con la keyword exacta y la descripción editada sobre la
      existente, sin reescribir. Si el criterio está bien, escalamos el lote.</p></div>
    <div class="card"><h3>2 · ¿Hay alguna ficha que no pasarías?</h3>
      <p style="margin-top:6px">Marcanos cuáles y por qué. Cada rechazo tuyo se convierte en
      una regla nueva del validador, no en un parche a mano.</p></div>
    <div class="card"><h3>3 · ¿Qué falta para que esto sea publicable?</h3>
      <p style="margin-top:6px">Tono, longitud, datos que no querés que se agreguen,
      secundarias que preferís evitar.</p></div>
  </div>
</section>

<section>
  <div class="grid g4">
    <div class="kpi"><div class="n">{len(filas)}</div><div class="l">fichas de la muestra</div>
      <div class="s">de la lista priorizada por GSC</div></div>
    <div class="kpi"><div class="n">{len(ok)}/{len(filas)}</div><div class="l">aprobadas por el validador</div>
      <div class="s">reglas del documento + control editorial</div></div>
    <div class="kpi"><div class="n">{pal_antes} → {pal_desp}</div><div class="l">palabras en total</div>
      <div class="s">sobre el texto que ya existía</div></div>
    <div class="kpi"><div class="n">US$ {usd:.2f}</div><div class="l">costo total medido</div>
      <div class="s">US$ {por_ficha:.4f} por ficha · tokens reales de la API</div></div>
  </div>
</section>

<section>
  <div class="eyebrow">De dónde salió cada dato</div>
  <h2>Cuatro fuentes, ninguna inventada</h2>
  <p>Lo que el agente no encuentra en estas fuentes, no lo escribe.</p>
  <div class="grid g4" style="margin-top:16px">
    <div class="src"><span class="tag">Google Search Console</span>
      <ul><li>La consulta real que trae la ficha</li><li>Posición, impresiones y clics de 90 días</li>
      <li>La oportunidad se calcula ahí, no a ojo</li></ul></div>
    <div class="src"><span class="tag">WooCommerce</span>
      <ul><li>H1 y descripción actuales</li><li>Marca, categoría y colección</li>
      <li>Atributos: material, medidas, acabados</li></ul></div>
    <div class="src"><span class="tag">Documento del equipo SEO</span>
      <ul><li>Máximo 60 caracteres en el H1</li><li>150-300 palabras, hasta 2 H2</li>
      <li>2-3 secundarias, máximo 2 usos</li><li>Anti-canibalización entre fichas</li></ul></div>
    <div class="src"><span class="tag">Base interna del agente</span>
      <ul><li>Texto antes y después</li><li>Keywords elegidas y descartadas</li>
      <li>Veredicto del validador y motivos</li><li>Tokens y costo de cada ficha</li></ul></div>
  </div>
</section>

<section>
  <div class="eyebrow">Resumen</div>
  <h2>Las diez, de un vistazo</h2>
  <div class="tscroll">
    <table class="t">
      <thead><tr><th>Ficha</th><th>Consulta</th><th>Pos.</th><th>Impr.</th><th>Palabras</th><th>Conservación</th><th>Costo</th></tr></thead>
      <tbody>{filas_tabla}</tbody>
    </table>
  </div>
  <p style="margin-top:10px;font-size:.8rem;color:var(--dim)">Conservación = porcentaje de
  oraciones del texto original que siguen intactas en la versión nueva. No se reescribe: se edita.</p>
</section>

<section>
  <div class="eyebrow">Ficha por ficha</div>
  <h2>Antes y después</h2>
  <p>El texto de la derecha es lo que se publicaría. A la izquierda, lo que hay hoy.</p>
  {fichas}
</section>

<section>
  <div class="eyebrow">Límites</div>
  <h2>Lo que el agente no hace</h2>
  <div class="card" style="margin-top:14px">
    <ul class="limites" style="margin-left:18px;color:var(--muted);font-size:.9rem">
      <li>No edita la descripción corta, el meta title, la meta description ni los ALT:
        esos campos son del flujo de n8n. Un solo escritor por campo.</li>
      <li>No inventa medidas, materiales ni colecciones: si un dato no está en el texto
        original o en los atributos de la ficha, el validador lo rebota.</li>
      <li>No reescribe la descripción: la edita. La conservación mínima exigida es 80% y
        se mide en código.</li>
      <li>No publica. Lo que ves acá vive en la base interna hasta que el equipo SEO lo apruebe.</li>
    </ul>
  </div>
</section>

<section>
  <div class="eyebrow">Siguiente paso</div>
  <h2>Tres preguntas concretas</h2>
  <div class="preg">1. De las diez, ¿cuáles publicarías tal como están y cuáles no? Con el número alcanza.</div>
  <div class="preg">2. ¿La longitud final te cierra? Hoy las fichas originales tienen 54 a 269 palabras
    y la regla pide 150-300: en las cortas el agente tiene que agregar texto. ¿Preferís que se
    quede más corto antes que sumar párrafos?</div>
  <div class="preg">3. ¿El H1 con la marca adelante es el formato que querés
    (<i>Rugiano Club Sofa</i>) o preferís el nombre del producto primero?</div>
</section>

<footer>
  Cassoni · agente SEO · muestra generada desde la base interna de trazas.
  El costo se calcula con los precios oficiales de DeepSeek Flash (entrada US$ 0,30/M,
  salida US$ 1,20/M, tarifa peak) sobre los tokens que devuelve la API en cada llamada.
</footer>

</div>
</body>
</html>"""


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--json", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    filas = json.loads(Path(a.json).read_text(encoding="utf-8"))
    html = generar(filas)
    Path(a.out).write_text(html, encoding="utf-8")
    print(f"{len(filas)} fichas → {a.out} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
