# -*- coding: utf-8 -*-
"""Cassoni SEO Agent — pipeline de optimización SEO (agnóstico al entorno).

Un solo código corre contra staging o producción; la única diferencia es la
configuración (base + credenciales de WooCommerce). `dry_run` es True por
defecto: el pipeline corre completo y deja el texto editado listo, pero NO
toca WooCommerce (registra el update que haría).
"""
__version__ = "0.1.0"