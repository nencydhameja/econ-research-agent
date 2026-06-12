"""Top economics & finance journals via publisher RSS feeds.

Feeds are configured in config/journal_feeds.yaml so the user can edit
without touching code.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from ..models import Paper, make_paper_id
from ._common import clean_html, parse_feed, parsed_to_date

log = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "journal_feeds.yaml"


def _load_feeds() -> list[dict]:
    if not CONFIG_PATH.exists():
        log.warning("journal_feeds.yaml not found at %s", CONFIG_PATH)
        return []
    with CONFIG_PATH.open() as f:
        data = yaml.safe_load(f) or {}
    return data.get("feeds", [])


def fetch(feeds: list[dict] | None = None, per_feed_limit: int = 25) -> list[Paper]:
    feeds = feeds if feeds is not None else _load_feeds()
    papers: list[Paper] = []
    for feed_cfg in feeds:
        name = feed_cfg["name"]
        url = feed_cfg["url"]
        try:
            feed = parse_feed(url)
        except Exception as e:
            log.warning("Journal %s: fetch failed: %s", name, e)
            continue

        for entry in feed.entries[:per_feed_limit]:
            entry_url = entry.get("link", "")
            source_id = entry.get("id", "") or entry_url
            doi = ""
            # Many publisher feeds include the DOI in <prism:doi> or in the id
            for key in ("prism_doi", "dc_identifier", "id"):
                v = entry.get(key, "")
                if v and "10." in v:
                    # Crude extract
                    idx = v.find("10.")
                    doi = v[idx:].strip()
                    break

            authors = []
            if "authors" in entry:
                authors = [a.get("name", "") for a in entry.get("authors", [])]
            elif "author" in entry:
                authors = [entry["author"]]

            p = Paper(
                id=make_paper_id("journal_rss", source_id, doi=doi),
                source="journal_rss",
                source_id=source_id,
                title=clean_html(entry.get("title", "")).strip(),
                abstract=clean_html(entry.get("summary", entry.get("description", ""))),
                authors=authors,
                doi=doi,
                url=entry_url,
                published=parsed_to_date(
                    entry.get("published_parsed") or entry.get("updated_parsed")
                ),
                raw={"journal": name},
            )
            papers.append(p)
    log.info("Journals: fetched %d papers across %d feeds", len(papers), len(feeds))
    return papers
