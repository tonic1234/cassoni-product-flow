#!/usr/bin/env python3
"""
Cassoni WooCommerce client (staging). 
Extrae la ficha completa de un producto y sus keywords target.
Solo LECTURA — nunca escribe en WooCommerce (regla de seguridad del proyecto).
Lee credenciales desde env: CASSONI_WC_KEY / CASSONI_WC_SECRET / CASSONI_WC_BASE.
"""
import os, sys, json, base64, urllib.request

def load_env(path="/root/cassoni-agent/creds/wc.env"):
    if not os.path.exists(path):
        return {}
    out = {}
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k] = v
    return out

def extract_slug(url):
    """Extrae el slug real (producto o categoría) desde una URL WooCommerce."""
    from urllib.parse import urlparse
    path = urlparse(url).path.rstrip("/")
    segs = [s for s in path.split("/") if s]
    # base conocida -> el slug es el segmento siguiente
    for base in ("product", "producto", "product-category", "categoria-producto"):
        if base in segs:
            i = segs.index(base)
            if i + 1 < len(segs):
                return segs[i + 1], base
    return segs[-1], "unknown"

def wc_get(base, key, secret, endpoint, params=None):
    url = f"{base.rstrip('/')}/wp-json/wc/v3/{endpoint}"
    if params:
        url += "?" + "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    auth = base64.b64encode(f"{key}:{secret}".encode()).decode()
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def main():
    env = load_env()
    base = os.environ.get("CASSONI_WC_BASE") or env.get("CASSONI_WC_BASE")
    key = os.environ.get("CASSONI_WC_KEY") or env.get("CASSONI_WC_KEY")
    secret = os.environ.get("CASSONI_WC_SECRET") or env.get("CASSONI_WC_SECRET")
    if not base or not key or not secret:
        print("FALTAN credenciales: CASSONI_WC_BASE, CASSONI_WC_KEY, CASSONI_WC_SECRET")
        sys.exit(1)
    if sys.argv[1:]:
        url = sys.argv[1]
    else:
        url = base
    slug, kind = extract_slug(url)
    print(f"Slug: {slug} ({kind})")

    if kind == "product-category":
        items = wc_get(base, key, secret, "products/categories", {"slug": slug})
        print(json.dumps(items, indent=2, ensure_ascii=False)[:800])
    else:
        items = wc_get(base, key, secret, "products", {"slug": slug})
        if not items:
            print(f"No se encontró producto con slug '{slug}'")
            sys.exit(1)
        p = items[0]
        if p.get("type") == "variable":
            p["_variations"] = wc_get(base, key, secret, f"products/{p['id']}/variations", {"per_page": 100})
        print("=== RESUMEN ===")
        print(f"ID:{p['id']}  {p['name']}")
        print(f"Tipo:{p['type']}  precio:{p.get('price')}  sku:{p.get('sku')}")
        print(f"Imágenes:{len(p.get('images',[]))}  cats:{[c['name'] for c in p.get('categories',[])]}")
        print(f"H1 actual (name): {p['name']}")
        desc = p.get('description','')
        print(f"Descripción: {len(desc)} chars | {desc[:80]}...")

if __name__ == "__main__":
    main()