# Landing v4 para Alex — correrla en el VPS

Todo **en seco**: nada se escribe en WooCommerce (`tools/correr_lote.py` usa `dry_run=True`
siempre). Tarda ~1 h y cuesta ~US$ 3 (DataForSEO + DeepSeek).

## Con git (si el VPS tiene el repo)

```bash
cd /root/wt-cassoni-v5 && git fetch origin flujo-seo-v2 && git checkout -B flujo-seo-v2 origin/flujo-seo-v2
bash scripts/landing_v4_vps.sh
```

## Con el paquete (sin git)

```bash
mkdir -p /root/cassoni-v4 && tar -xzf cassoni-v4.tar.gz -C /root/cassoni-v4 && cd /root/cassoni-v4
python3 -m venv venv && ./venv/bin/pip install -q -r requirements.txt
ln -sfn /root/cassoni-agent/.env.prod .env.prod && ln -sfn /root/cassoni-agent/creds creds
bash scripts/landing_v4_vps.sh
```

## Qué hace

1. `--preflight`: Search Console, WooCommerce, LLM y DataForSEO responden.
2. Las 10 fichas de Alex con la ficha completa (atributos y medidas) y la comparación con
   su referencia (`evaluar_vs_seo.py`).
3. 30 fichas nuevas al azar por código (semilla = fecha), sin repetir ninguna ya usada:
   las de `evidencia/` y `docs/`, y la lista de TARS del 18-nov
   (`/root/wt-cassoni-v5/elegidas.txt`, se cambia con `EXCLUIR=`). Se rehacen las que se
   queden sin presupuesto de DataForSEO.
4. `docs/landing-v4/index.html`, con el mismo diseño de la v3.

Al final imprime el resumen, cómo subir la evidencia al repo y cómo publicar en la misma
URL de la v3 (`https://tarsterminal.duckdns.org/cassoni-agente-seo/`), guardando la v3
como `index-v3.html`. Antes de publicar conviene mirarla.
