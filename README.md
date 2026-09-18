# Cassoni SEO Agent — pipeline

Pipeline de optimización SEO sobre el catálogo WooCommerce de Cassoni (muebles de
lujo, ~11.000 productos). **Un solo código, agnóstico al entorno**: corre contra
staging o producción; la única diferencia es la config (`env`). Validando en
staging usás exactamente el mismo código que corre en producción.

## Arquitectura (cadena del informe)

```
INPUT(lista URLs) → 01 extract → 02 woo ficha → 03 GSC top-10 kw (+ etiqueta de
oportunidades) → 04 DataForSEO (volumen, dedup+bulk+remapeo) → 05 editor LLM
(ficha completa: H1 + desc corta + desc larga + secundarias/descartadas)
→ 06 validador (reglas mecánicas en código + LLM) → 07 DB trazabilidad,
y cron supervisor 9-18 con pausas aleatorias anti-bot.
```

## Agente según "Reglas de contenido SEO para fichas de producto"

La spec del cliente es `docs/REGLA-SEO-FICHAS.md`; sus límites viven en
`cassoni/reglas.py` (fuente única de constantes y textos de prompt):

- **H1** ≤ 60 caracteres, keyword principal EXACTA (el pipeline la define como la
  candidata de mayor volumen).
- **Alcance**: el agente SOLO edita H1 (`name`) y descripción larga (`description`).
  La descripción corta (`short_description`) NO se toca: entra como contexto al
  editor y WooCommerce queda intacto en ese campo (un solo escritor por campo).
- **Descripción larga**: 150–300 palabras, máx 2 H2, 2–3 secundarias, cada una
  máx 2 veces, **y se EDITA sobre el texto actual, nunca se reescribe desde cero**:
  el gate mide la *conservación* (porcentaje de oraciones del original que
  sobreviven intactas, mínimo 60% — `checklist.conservacion()`) y rebota la
  edición si el LLM reescribió todo aunque suene bien.
- **Anti-canibalización** (`cassoni/checklist.py`, determinista): descarta
  candidatas que ya son principal de otra ficha, compiten con la página de
  categoría o responden mejor a un blog/guía, y registra su destino. El input de
  "keywords ya usadas" son los H1 de las demás fichas publicadas de la misma
  categoría (`woo.products_by_category()`, con caché).
- **Gate duro en código**: el validador corre `check_reglas()` ANTES del LLM; el
  LLM queda con lo cualitativo (tono, naturalidad, HTML, datos inventados).
- El output del editor es estructurado: H1 / desc corta / desc larga con H2 /
  secundarias con su porqué / descartadas con su destino, y se guarda como traza
  en la DB (`edited_short_description` incluida).

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