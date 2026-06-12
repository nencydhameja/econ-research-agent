"""CEPR Discussion Papers via IDEAS/RePEc.

CEPR's own DPs are behind a paywall and there's no public API. IDEAS
indexes them with the same structure as IZA — title/authors/abstract/JEL
in per-paper <META> tags.
"""

from __future__ import annotations

from ..models import Paper
from . import _ideas


def fetch(limit: int = 20) -> list[Paper]:
    return _ideas.fetch_series(
        source_name="cepr",
        journal_label="CEPR DP",
        listing_url="https://ideas.repec.org/s/cpr/ceprdp.html",
        paper_url_tpl="https://ideas.repec.org/p/cpr/ceprdp/{n}.html",
        paper_id_pattern=r"/p/cpr/ceprdp/(\d+)\.html",
        paper_id_prefix="",
        limit=limit,
    )
