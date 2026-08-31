# -*- coding: utf-8 -*-
import pytest

from cassoni.extract import ExtractionError, extract_slug, is_product_url


@pytest.mark.parametrize("url,slug,kind", [
    ("https://cassoni.test/product/cas-cprn-pedro-sofa-01/", "cas-cprn-pedro-sofa-01", "product"),
    ("https://cassoni.test/producto/sillon-cuero/", "sillon-cuero", "product"),
    ("https://cassoni.test/produit/chaise/", "chaise", "product"),
    ("https://cassoni.test/products/chair?lang=en", "chair", "product"),
    ("https://cassoni.test/product-category/sofas/", "sofas", "category"),
    ("https://cassoni.test/categoria-producto/mesas/", "mesas", "category"),
    ("https://cassoni.test/product-tag/outdoor/", "outdoor", "tag"),
    ("https://cassoni.test/cas-cprn-pedro-sofa-01/", "cas-cprn-pedro-sofa-01", "unknown"),
])
def test_extract(url, slug, kind):
    assert extract_slug(url) == (slug, kind)


def test_extract_home_raises():
    with pytest.raises(ExtractionError):
        extract_slug("https://cassoni.test/")


def test_extract_multi_nested():
    # base anidada: /shop/product/x
    assert extract_slug("https://a.test/shop/product/x/") == ("x", "product")


def test_is_product_url():
    assert is_product_url("https://a.test/product/p1/") is True
    # permalink suelto sin base = unknown -> no se procesa como producto
    assert is_product_url("https://a.test/cas-pedro-sofa/") is False
    assert is_product_url("https://a.test/product-category/sofas/") is False
    assert is_product_url("https://a.test/home/") is False