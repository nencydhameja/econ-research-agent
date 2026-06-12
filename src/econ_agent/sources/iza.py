"""IZA Discussion Papers via IDEAS/RePEc.

Why this route: IZA's own RSS endpoints all 404 as of 2026-06; OpenAlex
indexes IZA articles but not the DP series (0 DPs in last 30d). The IDEAS
series page lists every DP with a stable URL pattern, and each per-paper
page exposes clean <META> tags with title / authors / abstract / JEL / date.

Cost: 1 HTTP for the listing + N HTTPs for per-paper meta. Default N=20.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime

from ..models import Paper, make_paper_id
from ._common import clean_html, get_text

log = logging.getLogger(__name__)

LISTING_URL = "https://ideas.repec.org/s/iza/izadps.html"
PAPER_URL_TPL = "https://ideas.repec.org/p/iza/izadps/dp{n}.html"

# IDEAS' "popular" / "editor's pick" slots always show the same low-numbered
# DPs at the top of every listing page (e.g. dp1240, dp13004). We sort by DP
# number desc and take top N, which naturally drops them.
_DP_RE = re.compile(r"/p/iza/izadps/dp(\d+)\.html", re.IGNORECASE)
_META_RE = re.compile(
    r'<META\s+NAME="([^"]+)"\s+CONTENT="([^"]*)"', re.IGNORECASE
)


def _fix_mojibake(s: str) -> str:
    """IDEAS meta tags ship double-encoded UTF-8: original UTF-8 bytes were
    interpreted as Windows-1252 and re-encoded as UTF-8 (note: cp1252, NOT
    latin-1 — the euro sign and curly quotes that appear in the mojibake
    are cp1252-only code points). Reverse the round-trip to recover."""
    if not s:
        return s
    try:
        return s.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def _parse_meta(html: str) -> dict[str, str]:
    return {k.lower(): _fix_mojibake(v) for k, v in _META_RE.findall(html)}


def _parse_authors(raw: str) -> list[str]:
    # IZA meta lists authors as "Last, First & Last, First & ..."
    parts = [a.strip() for a in raw.split("&") if a.strip()]
    return parts


def _parse_jel(raw: str) -> list[str]:
    return [c.strip() for c in raw.replace(",", ";").split(";") if c.strip()]


def _parse_date(raw: str) -> date | None:
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m", "%Y-%m"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _clean_abstract(raw: str) -> str:
    # IDEAS prefixes abstracts with "Downloadable! " or "Downloadable (with restrictions)! "
    text = re.sub(r"^Downloadable[^!]*!\s*", "", raw)
    return clean_html(text)


def fetch(limit: int = 20) -> list[Paper]:
    try:
        listing = get_text(LISTING_URL)
    except Exception as e:
        log.warning("IZA listing fetch failed: %s", e)
        return []

    # Sort discovered DP numbers desc, dedupe
    dp_nums = sorted({int(m) for m in _DP_RE.findall(listing)}, reverse=True)
    if not dp_nums:
        log.warning("IZA: no DP numbers found in listing")
        return []
    targets = dp_nums[:limit]

    papers: list[Paper] = []
    for n in targets:
        url = PAPER_URL_TPL.format(n=n)
        try:
            html = get_text(url)
        except Exception as e:
            log.warning("IZA dp%d fetch failed: %s", n, e)
            continue

        meta = _parse_meta(html)
        title = meta.get("title", "").strip()
        if not title:
            continue
        abstract = _clean_abstract(meta.get("description", ""))
        authors = _parse_authors(meta.get("author", ""))
        jel = _parse_jel(meta.get("jel_code", ""))
        # Prefer the explicit MS-style date; fall back to the citation_publication_date
        pub = _parse_date(meta.get("date", "")) or _parse_date(
            meta.get("citation_publication_date", "")
        )

        source_id = f"dp{n}"
        p = Paper(
            id=make_paper_id("iza", source_id),
            source="iza",
            source_id=source_id,
            title=title,
            abstract=abstract,
            authors=authors,
            url=url,
            published=pub,
            jel_codes=jel,
            raw={"repec_handle": meta.get("handle", ""), "journal": "IZA DP"},
        )
        papers.append(p)

    log.info("IZA: fetched %d DPs (newest dp%d)", len(papers), targets[0] if targets else 0)
    return papers
