#!/usr/bin/env python3
"""
Cassoni Product Flow — WooCommerce API demo.
Extrae la ficha completa de un producto desde su URL.

Uso:
  python3 fetch_product.py https://cassoni.com/producto/sofa-elegante/

Requiere variables de entorno:
  CASSONI_API_KEY    — WooCommerce Consumer Key
  CASSONI_API_SECRET — WooCommerce Consumer Secret
  CASSONI_BASE_URL   — (opcional) base de la tienda, default: https://cassoni.com
"""

import sys, os, json, re
import urllib.request
from base64 import b64encode

def extract_slug(url):
    """Extrae el slug del producto desde una URL de WordPress/WooCommerce."""
    # Saca protocolo y dominio, toma el último segmento de path
    path = url.split("//")[-1].split("/", 1)[-1]
    slug = [seg for seg in path.rstrip("/").split("/") if seg][-1]
    return slug

def wc_request(base_url, key, secret, endpoint, params=None):
    """Hace un GET autenticado a la WooCommerce REST API v3."""
    url = f"{base_url}/wp-json/wc/v3/{endpoint}"
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())

    auth = b64encode(f"{key}:{secret}".encode()).decode()
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Basic {auth}")
    req.add_header("Content-Type", "application/json")

    print(f"→ GET {url}")
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read().decode())

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 fetch_product.py <url-del-producto>")
        print("  Ej: python3 fetch_product.py https://cassoni.com/producto/sofa/")
        sys.exit(1)

    url = sys.argv[1]
    key = os.environ.get("CASSONI_API_KEY")
    secret = os.environ.get("CASSONI_API_SECRET")
    base = os.environ.get("CASSONI_BASE_URL", "https://cassoni.com")

    if not key or not secret:
        print("Error: setear CASSONI_API_KEY y CASSONI_API_SECRET en el entorno")
        sys.exit(1)

    slug = extract_slug(url)
    print(f"Slug extraído: {slug}\n")

    # 1. Buscar producto por slug
    data = wc_request(base, key, secret, "products", {"slug": slug})
    if not data:
        print(f"No se encontró producto con slug '{slug}'")
        sys.exit(1)

    product = data[0]
    pid = product["id"]

    # 2. Si es variable, traer variaciones
    variations = []
    if product.get("type") == "variable":
        variations = wc_request(base, key, secret, f"products/{pid}/variations", {"per_page": 100})
        product["_variations"] = variations

    print(json.dumps(product, indent=2, ensure_ascii=False))

    # Resumen
    print(f"\n--- Resumen ---")
    print(f"ID: {pid}")
    print(f"Nombre: {product['name']}")
    print(f"Tipo: {product['type']}")
    print(f"Precio: {product.get('price')}")
    print(f"SKU: {product.get('sku')}")
    print(f"Imágenes: {len(product.get('images', []))}")
    print(f"Categorías: {[c['name'] for c in product.get('categories', [])]}")
    print(f"Variaciones: {len(variations)}")

if __name__ == "__main__":
    main()
