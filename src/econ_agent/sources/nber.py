"""NBER Working Papers via RSS.

NBER publishes a public RSS feed of new working papers. Entries include
a w-number, title, authors (in the summary), and JEL codes (sometimes).
"""

from __future__ import annotations

import logging
import re
from datetime import date

from ..models import Paper, make_paper_id
from ._common import clean_html, parse_feed, parsed_to_date

log = logging.getLogger(__name__)

# NBER's new working papers feed (papers from the last week)
FEED_URL = "https://www.nber.org/rss/new.xml"

_W_NUMBER = re.compile(r"\b(w\d{4,6})\b", re.IGNORECASE)
_JEL = re.compile(r"\b([A-Q]\d{1,2})\b")
# NBER titles end with " -- by Author One, Author Two, ..."
_TITLE_AUTHORS = re.compile(r"^(.*?)\s*--\s*by\s+(.+)$", re.IGNORECASE)


def _split_title_authors(raw_title: str) -> tuple[str, list[str]]:
    m = _TITLE_AUTHORS.match(raw_title)
    if not m:
        return raw_title, []
    title = m.group(1).strip()
    # Author list separator can be ",", " and ", or " ⓡ " (random-order symbol NBER uses)
    raw_authors = re.split(r",|\s+and\s+|\s+ⓡ\s+", m.group(2))
    authors = [a.strip() for a in raw_authors if a.strip()]
    return title, authors


def fetch(limit: int | None = None) -> list[Paper]:
    feed = parse_feed(FEED_URL)
    today = date.today()
    papers: list[Paper] = []
    for entry in feed.entries[: limit or len(feed.entries)]:
        url = entry.get("link", "")
        raw_title = clean_html(entry.get("title", "")).strip()
        title, authors = _split_title_authors(raw_title)
        summary = clean_html(entry.get("summary", entry.get("description", "")))

        m = _W_NUMBER.search(url) or _W_NUMBER.search(entry.get("id", ""))
        source_id = (m.group(1) if m else url).lower()

        jel = sorted(set(_JEL.findall(summary)))

        # NBER RSS strips <pubDate> entirely. The feed is titled "Latest" so
        # falling back to today's date is accurate to within a week.
        published = (parsed_to_date(entry.get("published_parsed")
                                    or entry.get("updated_parsed"))
                     or today)

        p = Paper(
            id=make_paper_id("nber", source_id),
            source="nber",
            source_id=source_id,
            title=title,
            abstract=summary,
            authors=authors,
            url=url,
            published=published,
            jel_codes=jel,
            raw={"feed_entry_id": entry.get("id", ""), "journal": "NBER WP"},
        )
        papers.append(p)
    log.info("NBER: fetched %d papers", len(papers))
    return papers
