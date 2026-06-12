"""arXiv econ.* categories via the public Atom API.

API docs: https://info.arxiv.org/help/api/user-manual.html
Econ categories: econ.EM (Econometrics), econ.GN (General), econ.TH (Theoretical)
We also include q-fin.EC (Economics within q-fin).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from ..models import Paper, make_paper_id
from ._common import clean_html, parse_feed, parsed_to_date

log = logging.getLogger(__name__)

API_URL = "http://export.arxiv.org/api/query"
DEFAULT_CATEGORIES = ["econ.EM", "econ.GN", "econ.TH", "q-fin.EC"]


def _build_query(categories: list[str], since: date | None, max_results: int) -> str:
    cat_q = "+OR+".join(f"cat:{c}" for c in categories)
    parts = [f"search_query={cat_q}"]
    parts.append("sortBy=submittedDate")
    parts.append("sortOrder=descending")
    parts.append(f"max_results={max_results}")
    return API_URL + "?" + "&".join(parts)


def fetch(
    categories: list[str] | None = None,
    since: date | None = None,
    max_results: int = 100,
) -> list[Paper]:
    cats = categories or DEFAULT_CATEGORIES
    url = _build_query(cats, since, max_results)
    feed = parse_feed(url)

    papers: list[Paper] = []
    for entry in feed.entries:
        arxiv_id = entry.get("id", "")
        # entry.id is like "http://arxiv.org/abs/2401.12345v2" — strip version
        short_id = arxiv_id.rsplit("/", 1)[-1]
        short_id = short_id.split("v")[0]

        published = parsed_to_date(entry.get("published_parsed"))
        if since and published and published < since:
            continue

        authors = [a.get("name", "") for a in entry.get("authors", [])]
        # arxiv tags include all categories the paper was cross-listed to
        tags = [t.get("term", "") for t in entry.get("tags", [])]
        pdf_url = ""
        for link in entry.get("links", []):
            if link.get("type") == "application/pdf":
                pdf_url = link.get("href", "")
                break

        p = Paper(
            id=make_paper_id("arxiv", short_id),
            source="arxiv",
            source_id=short_id,
            title=clean_html(entry.get("title", "")).strip(),
            abstract=clean_html(entry.get("summary", "")),
            authors=authors,
            url=entry.get("link", arxiv_id),
            pdf_url=pdf_url,
            published=published,
            raw={"arxiv_categories": tags},
        )
        papers.append(p)
    log.info("arXiv: fetched %d papers across %s", len(papers), cats)
    return papers
