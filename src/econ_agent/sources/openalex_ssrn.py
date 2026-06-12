"""SSRN-indexed preprints via OpenAlex.

SSRN has no open API and resists scraping. OpenAlex indexes SSRN preprints
with DOIs, abstracts (often), and author lists. We filter by:
  - source = SSRN (OpenAlex source id S4306400194)
  - concept = Economics (OpenAlex concept id C162324750)
  - from_publication_date = last N days

OpenAlex docs: https://docs.openalex.org/
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from ..models import Paper, make_paper_id
from ._common import clean_html, get_json

log = logging.getLogger(__name__)

OPENALEX_WORKS = "https://api.openalex.org/works"
SSRN_SOURCE_ID = "S4306400194"
ECONOMICS_CONCEPT = "C162324750"


def _reconstruct_abstract(inv_index: dict | None) -> str:
    """OpenAlex returns abstracts as an inverted index for licensing reasons."""
    if not inv_index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, indices in inv_index.items():
        for idx in indices:
            positions.append((idx, word))
    positions.sort()
    return " ".join(w for _, w in positions)


def fetch(days: int = 30, per_page: int = 50, max_pages: int = 4) -> list[Paper]:
    since = (date.today() - timedelta(days=days)).isoformat()
    params = {
        "filter": f"primary_location.source.id:{SSRN_SOURCE_ID},"
                  f"concepts.id:{ECONOMICS_CONCEPT},"
                  f"from_publication_date:{since}",
        "per-page": per_page,
        "sort": "publication_date:desc",
    }

    papers: list[Paper] = []
    for page in range(1, max_pages + 1):
        params["page"] = page
        try:
            data = get_json(OPENALEX_WORKS, params=params)
        except Exception as e:
            log.warning("OpenAlex page %d failed: %s", page, e)
            break

        results = data.get("results", [])
        if not results:
            break

        for w in results:
            doi = (w.get("doi") or "").replace("https://doi.org/", "")
            source_id = w.get("id", "").rsplit("/", 1)[-1]
            authors = [a.get("author", {}).get("display_name", "")
                       for a in w.get("authorships", [])]
            abstract = _reconstruct_abstract(w.get("abstract_inverted_index"))

            # Concepts → field tags
            fields = []
            for c in w.get("concepts", [])[:5]:
                name = c.get("display_name", "")
                if name and c.get("score", 0) > 0.3:
                    fields.append(f"oa:{name}")

            p = Paper(
                id=make_paper_id("openalex_ssrn", source_id, doi=doi),
                source="openalex_ssrn",
                source_id=source_id,
                title=clean_html(w.get("title", "") or ""),
                abstract=abstract,
                authors=authors,
                doi=doi,
                url=w.get("primary_location", {}).get("landing_page_url", "")
                    or w.get("doi", ""),
                published=date.fromisoformat(w["publication_date"])
                          if w.get("publication_date") else None,
                fields=fields,
                raw={"openalex_id": w.get("id", "")},
            )
            papers.append(p)

        if len(results) < per_page:
            break

    log.info("OpenAlex/SSRN: fetched %d papers (last %dd)", len(papers), days)
    return papers
