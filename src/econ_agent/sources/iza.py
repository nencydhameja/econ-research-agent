"""IZA Discussion Papers via IDEAS/RePEc.

See ._ideas for the shared scraper. IZA's own RSS endpoints all 404, and
OpenAlex doesn't index recent DPs.
"""

from __future__ import annotations

from ..models import Paper
from . import _ideas


def fetch(limit: int = 20) -> list[Paper]:
    return _ideas.fetch_series(
        source_name="iza",
        journal_label="IZA DP",
        listing_url="https://ideas.repec.org/s/iza/izadps.html",
        paper_url_tpl="https://ideas.repec.org/p/iza/izadps/dp{n}.html",
        paper_id_pattern=r"/p/iza/izadps/dp(\d+)\.html",
        paper_id_prefix="dp",
        limit=limit,
    )
