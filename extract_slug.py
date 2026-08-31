#!/usr/bin/env python3
"""
Cassoni Product Flow — URL → Slug Extractor blindado.
Detecta si una URL es producto, categoría, o etiqueta de WooCommerce
y extrae el slug correcto para consultar la API.

No falla. No adivina. Si no puede determinar el tipo, lo dice explícito.

Uso:
  python3 extract_slug.py https://cassoni.com/producto/sofa-elegante/
  python3 extract_slug.py "https://cassoni.com/categoria-producto/sofas/?page=2"
  python3 extract_slug.py https://cassoni.com/producto/silla-comedor/?variant=123&utm_source=ig
"""

import sys, re
from urllib.parse import urlparse, unquote

# ---------------------------------------------------------------------------
# Patrones conocidos de WooCommerce por idioma
# ---------------------------------------------------------------------------
PRODUCT_BASES = [
    "producto",     # español
    "product",      # inglés
    "produto",      # portugués
    "produit",      # francés
    "tienda",       # español (a veces)
    "shop",         # inglés (a veces)
]

CATEGORY_BASES = [
    "categoria-producto",  # español WooCommerce
    "product-category",    # inglés WooCommerce
    "categoria-produto",   # portugués
    "categorie-produit",   # francés
    "categoria",           # español genérico
    "category",            # inglés genérico
    "coleccion",           # tiendas de lujo a veces usan esto
    "collection",
]

TAG_BASES = [
    "etiqueta-producto",   # español WooCommerce
    "product-tag",         # inglés WooCommerce
    "etiqueta-produto",    # portugués
    "etiquette-produit",   # francés
    "etiqueta",            # español genérico
    "tag",                 # inglés genérico
]

# ---------------------------------------------------------------------------
# Lógica principal
# ---------------------------------------------------------------------------

def detect_woocommerce_entity(url):
    """
    Parsea una URL y determina qué tipo de entidad de WooCommerce representa.
    
    Retorna un dict:
      {
        "ok": True/False,
        "type": "product" | "category" | "tag" | "unknown",
        "slug": "el-slug-extraido",
        "domain": "cassoni.com",
        "api_endpoint": "/wp-json/wc/v3/products?slug=..." | null,
        "warning": "mensaje si hay algo raro" | null,
        "error": "mensaje si falló" | null,
      }
    """
    result = {
        "ok": False,
        "type": "unknown",
        "slug": None,
        "domain": None,
        "api_endpoint": None,
        "warning": None,
        "error": None,
        "raw_url": url,
    }

    # 1. Parsear URL
    try:
        parsed = urlparse(url.strip())
        if not parsed.scheme:
            # Intentar con https:// si no tiene esquema
            parsed = urlparse(f"https://{url.strip()}")
    except Exception as e:
        result["error"] = f"No se pudo parsear la URL: {e}"
        return result

    if not parsed.netloc:
        result["error"] = "URL inválida: no tiene dominio"
        return result

    result["domain"] = parsed.netloc

    # 2. Limpiar path: sacar trailing slash, decodificar %20, etc.
    path = unquote(parsed.path).rstrip("/")

    if not path or path == "/":
        result["error"] = "La URL no tiene path de producto/categoría (es la home)"
        return result

    # 3. Separar el path en segmentos
    segments = [s for s in path.split("/") if s]

    if not segments:
        result["error"] = "No se encontraron segmentos en la URL"
        return result

    # 4. Detectar tipo y extraer slug
    # Buscar el primer segmento que coincida con una base conocida
    for i, seg in enumerate(segments):
        seg_lower = seg.lower()

        # ¿Es una base de producto?
        if seg_lower in PRODUCT_BASES:
            result["type"] = "product"
            if i + 1 < len(segments):
                result["slug"] = segments[i + 1]
                result["api_endpoint"] = f"/wp-json/wc/v3/products?slug={result['slug']}"
                result["ok"] = True
            else:
                result["error"] = f"URL de producto incompleta: '{seg}' sin slug después"
            return result

        # ¿Es una base de categoría?
        if seg_lower in CATEGORY_BASES:
            result["type"] = "category"
            if i + 1 < len(segments):
                result["slug"] = segments[i + 1]
                result["api_endpoint"] = f"/wp-json/wc/v3/products/categories?slug={result['slug']}"
                result["ok"] = True
            else:
                result["error"] = f"URL de categoría incompleta: '{seg}' sin slug después"
            return result

        # ¿Es una base de etiqueta?
        if seg_lower in TAG_BASES:
            result["type"] = "tag"
            if i + 1 < len(segments):
                result["slug"] = segments[i + 1]
                result["api_endpoint"] = f"/wp-json/wc/v3/products/tags?slug={result['slug']}"
                result["ok"] = True
            else:
                result["error"] = f"URL de etiqueta incompleta: '{seg}' sin slug después"
            return result

    # 5. No se encontró ninguna base conocida — intentar heurística
    #
    # WooCommerce embeddeado en WordPress: a veces la URL es
    # https://cassoni.com/shop/producto/sofa/ → doble nivel
    # o https://cassoni.com/sofa/ → pretty permalink directo
    #
    # Si hay un solo segmento, podría ser un producto con permalink plano
    if len(segments) == 1:
        result["warning"] = (
            f"No se detectó base conocida ({', '.join(segments)}). "
            f"Asumiendo que '{segments[0]}' es un slug de producto con pretty permalink. "
            f"Verificar contra la API."
        )
        result["type"] = "product"
        result["slug"] = segments[0]
        result["api_endpoint"] = f"/wp-json/wc/v3/products?slug={result['slug']}"
        result["ok"] = True
        return result

    # Si hay 2 segmentos y el primero no es conocido, intentar con el último
    if len(segments) == 2:
        result["warning"] = (
            f"Base '{segments[0]}' no está en las listas conocidas. "
            f"Asumiendo que '{segments[1]}' es el slug y '{segments[0]}' es una base custom. "
            f"Si falla, agregar '{segments[0]}' a la lista de bases."
        )
        result["slug"] = segments[1]
        result["type"] = "unknown"
        result["api_endpoint"] = f"/wp-json/wc/v3/products?slug={result['slug']}"
        result["ok"] = True
        return result

    # 3+ segmentos sin base conocida: agarrar el último como slug probable
    result["warning"] = (
        f"Estructura no reconocida: {'/'.join(segments)}. "
        f"Tomando '{segments[-1]}' como slug probable. "
        f"Verificar manualmente."
    )
    result["slug"] = segments[-1]
    result["type"] = "unknown"
    result["api_endpoint"] = f"/wp-json/wc/v3/products?slug={result['slug']}"
    result["ok"] = True
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 extract_slug.py <url> [url2 url3 ...]")
        print()
        print("Ejemplos:")
        print("  python3 extract_slug.py https://cassoni.com/producto/sofa/")
        print("  python3 extract_slug.py https://cassoni.com/categoria-producto/sofas/")
        print("  python3 extract_slug.py https://cassoni.com/sofa/?utm=ig")
        sys.exit(1)

    for url in sys.argv[1:]:
        r = detect_woocommerce_entity(url)
        print("─" * 60)
        print(f"URL:  {r['raw_url']}")
        print(f"Dominio: {r['domain'] or '—'}")

        if r["error"]:
            print(f"❌ ERROR: {r['error']}")
            continue

        print(f"Tipo:     {r['type']}")
        print(f"Slug:     {r['slug']}")
        print(f"Endpoint: {r['api_endpoint']}")

        if r["warning"]:
            print(f"⚠️  {r['warning']}")

    print("─" * 60)


if __name__ == "__main__":
    main()
