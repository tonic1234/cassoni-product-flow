# -*- coding: utf-8 -*-
"""Cliente Google Search Console — SOLO LECTURA (scope webmasters.readonly).

No existe ninguna función de escritura en este módulo: regla de seguridad del
proyecto (GSC nunca se borra/modifica). Sólo lee search analytics.

Corrección del 2-nov-2026 (auditoría 13-oct): la consulta por ficha pedía 365 días y
10 filas, y la API devuelve ordenado por CLICS. Las consultas con muchas impresiones
y cero clics —las oportunidades— quedaban afuera. Ahora: 90 días, 200 filas y orden
explícito por impresiones.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build

from .config import Config

DIAS_DEFAULT = 90
FILAS_POR_FICHA = 200
TAM_PAGINA = 25000


def ventana_texto(days: int = DIAS_DEFAULT) -> str:
    """'2026-08-04..2026-11-02' — la ventana que se midió, para la traza."""
    end = dt.date.today()
    start = end - dt.timedelta(days=days)
    return f"{start.isoformat()}..{end.isoformat()}"


class GSCClient:
    SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

    def __init__(self, config: Config):
        self.cfg = config
        creds = service_account.Credentials.from_service_account_file(
            config.gsc_service_account_file, scopes=self.SCOPES)
        self.service = build("searchconsole", "v1", credentials=creds,
                             cache_discovery=False)

    @property
    def site(self) -> str:
        return self.cfg.gsc_site

    def list_sites(self) -> list[str]:
        res = self.service.sites().list().execute()
        return [s.get("siteUrl") for s in res.get("siteEntry", [])]

    # --- helpers ---
    @staticmethod
    def _ventana(days: int) -> tuple[str, str]:
        end = dt.date.today()
        start = end - dt.timedelta(days=days)
        return start.isoformat(), end.isoformat()

    @classmethod
    def ventana_texto(cls, days: int = DIAS_DEFAULT) -> str:
        return ventana_texto(days)

    def _query(self, body: dict) -> list[dict]:
        resp = self.service.searchanalytics().query(siteUrl=self.site,
                                                    body=body).execute()
        return resp.get("rows", [])

    def pages(self, *, days: int = DIAS_DEFAULT, page_size: int = TAM_PAGINA) -> list[dict]:
        """Una fila por página del sitio (agregada), paginando hasta agotar."""
        start, end = self._ventana(days)
        out: list[dict] = []
        start_row = 0
        while True:
            rows = self._query({
                "startDate": start, "endDate": end,
                "dimensions": ["page"],
                "rowLimit": page_size, "startRow": start_row,
            })
            out.extend([{
                "url": r["keys"][0],
                "impressions": r.get("impressions", 0),
                "clicks": r.get("clicks", 0),
                "ctr": r.get("ctr", 0),
                "position": r.get("position", 0),
            } for r in rows])
            if len(rows) < page_size:
                break
            start_row += page_size
        return out

    def queries_for_page(self, url: str, *, days: int = DIAS_DEFAULT,
                         row_limit: int = FILAS_POR_FICHA) -> list[dict]:
        """Consultas de UNA página, ordenadas por impresiones desc (no por clics)."""
        start, end = self._ventana(days)
        rows = self._query({
            "startDate": start, "endDate": end,
            "dimensions": ["query"],
            "dimensionFilterGroups": [{
                "filters": [{"dimension": "page", "operator": "equals",
                             "expression": url}],
            }],
            "rowLimit": row_limit,
        })
        out = [{
            "keyword": r["keys"][0],
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "position": r.get("position", 0),
            "ctr": r.get("ctr", 0),
        } for r in rows]
        out.sort(key=lambda r: (r["impressions"], r["clicks"]), reverse=True)
        return out

    def top_keywords_for_url(self, url: str, *, days: int = DIAS_DEFAULT,
                             row_limit: Optional[int] = FILAS_POR_FICHA) -> list[dict]:
        """Compatibilidad con el contrato viejo: mismas claves, mejor lectura."""
        return self.queries_for_page(url, days=days, row_limit=row_limit or FILAS_POR_FICHA)
