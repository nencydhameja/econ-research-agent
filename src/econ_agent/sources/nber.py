"""NBER Working Papers via RSS.

NBER publishes a public RSS feed of new working papers. Entries include
a w-number, title, authors (in the summary), and JEL codes (sometimes).
"""

from __future__ import annotations

import logging
import re

from ..models import Paper, make_paper_id
from ._common import clean_html, parse_feed, parsed_to_date

log = logging.getLogger(__name__)

# NBER's new working papers feed (papers from the last week)
FEED_URL = "https://www.nber.org/rss/new.xml"

_W_NUMBER = re.compile(r"\b(w\d{4,6})\b", re.IGNORECASE)
_JEL = re.compile(r"\b([A-Q]\d{1,2})\b")  # rough JEL code match


def fetch(limit: int | None = None) -> list[Paper]:
    feed = parse_feed(FEED_URL)
    papers: list[Paper] = []
    for entry in feed.entries[: limit or len(feed.entries)]:
        url = entry.get("link", "")
        title = clean_html(entry.get("title", "")).strip()
        summary = clean_html(entry.get("summary", entry.get("description", "")))

        # Try to pull the w-number from the link or guid
        m = _W_NUMBER.search(url) or _W_NUMBER.search(entry.get("id", ""))
        source_id = (m.group(1) if m else url).lower()

        # NBER summaries include the abstract; authors usually in a separate line
        # We keep both — classification can use them, enrichment can clean up.
        jel = sorted(set(_JEL.findall(summary)))

        p = Paper(
            id=make_paper_id("nber", source_id),
            source="nber",
            source_id=source_id,
            title=title,
            abstract=summary,
            url=url,
            published=parsed_to_date(entry.get("published_parsed") or entry.get("updated_parsed")),
            jel_codes=jel,
            raw={"feed_entry_id": entry.get("id", "")},
        )
        papers.append(p)
    log.info("NBER: fetched %d papers", len(papers))
    return papers
