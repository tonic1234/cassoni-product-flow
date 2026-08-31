# -*- coding: utf-8 -*-
"""Cliente Google Search Console — SOLO LECTURA (scope webmasters.readonly).

No existe ninguna función de escritura en este módulo: regla de seguridad del
proyecto (GSC nunca se borra/modifica). Sólo lee search analytics por URL.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build

from .config import Config


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

    def top_keywords_for_url(self, url: str, *, days: int = 365,
                             row_limit: Optional[int] = 10) -> list[dict]:
        """Top keywords por URL en los últimos `days` días. Sólo lectura."""
        end = dt.date.today()
        start = end - dt.timedelta(days=days)
        body = {
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": ["query"],
            "dimensionFilterGroups": [{
                "filters": [{"dimension": "page", "operator": "equals",
                             "expression": url}],
            }],
            "rowLimit": row_limit or 10,
        }
        resp = self.service.searchanalytics().query(siteUrl=self.site,
                                                    body=body).execute()
        rows = resp.get("rows", [])
        return [{
            "keyword": r["keys"][0],
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "position": r.get("position", 0),
            "ctr": r.get("ctr", 0),
        } for r in rows]