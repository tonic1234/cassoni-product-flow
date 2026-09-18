# Cassoni SEO Agent — pipeline

Pipeline de optimización SEO sobre el catálogo WooCommerce de Cassoni (muebles de
lujo, ~11.000 productos). **Un solo código, agnóstico al entorno**: corre contra
staging o producción; la única diferencia es la config (`env`). Validando en
staging usás exactamente el mismo código que corre en producción.

## Arquitectura (cadena del informe)

```
INPUT(lista URLs) → 01 extract → 02 woo ficha → 03 GSC top-10 kw (+ etiqueta de
oportunidades) → 04 DataForSEO (volumen, dedup+bulk+remapeo) → 05 editor LLM (H1+desc)
→ 06 validador → 07 DB trazabilidad, y cron supervisor 9-18 con pausas aleatorias anti-bot.
```

## Oportunidades de GSC (`cassoni/opportunities.py`)
Cada keyword de GSC se etiqueta (campo `opportunity` + `opportunity_score` en la traza) según
su potencial de optimización: `materialize_demand` (posición 4-20 con demanda, el mayor valor),
`lift_ctr` (mucho aparecer, nadie entra), `hold_top` (ya rankea), `long_tail` (no prioritario).
Es información **aditiva** para reportar/priorizar: no cambia la selección por volumen de
DataForSEO ni toca el schema de la DB.

## Seguridad
- **GSC = SOLO LECTURA** (scope `webmasters.readonly`). No hay función de escritura.
- **WooCommerce se edita (H1 + long description) en STAGING** con **gate**:
  `update_product()` solo actúa si `dry_run=False` Y el validador pasó. En
  `dry_run` (default) el pipeline corre completo y deja el texto listo sin tocar nada.
- Producción: solo migra lo aprobado por el equipo SEO (gate humano).

## Uso

```bash
# Dry-run (default): corre completo, NO toca WooCommerce
venv/bin/python -m cassoni.cli --env staging --dry-run --urls urls.txt --batch 5

# Habilitar escritura en staging (requiere gate validador OK)
venv/bin/python -m cassoni.cli --env staging --write --urls urls.txt --scheduler

# Pre-flight de producción (siempre dry-run hasta validar)
venv/bin/python -m cassoni.cli --env prod --dry-run --urls urls.txt --batch 5
```

## Entorno
Config selectora de entorno lee `.env.staging` / `.env.prod` (`env` → nombre).
Ver `cassoni/config.py`. Credenciales reales NUNCA en git (`creds/`, `.gitignore`).

## Tests
```bash
venv/bin/python -m pytest tests/ -q   # red mockeada, sin llamadas en vivo
```

## Notas de ejecución
- Correr en vivo desde CASE/Contabo (WooCommerce y DataForSEO responden). TARS
  está bloqueado por Cloudflare en cassoni.com.
- Muchos productos staging están en `draft` → el pipeline filtra `status=publish`.
- DataForSEO: máx 12 req/min, retry ante `result=null` intermitente.