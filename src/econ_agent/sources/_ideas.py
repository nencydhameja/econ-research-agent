"""Shared scraper for IDEAS/RePEc working-paper series.

IDEAS hosts a per-series listing page (`/s/{archive}/{series}.html`) with
links to per-paper pages (`/p/{archive}/{series}/<paper-id>.html`). Each
per-paper page exposes clean <META> tags (title, author, description,
jel_code, date) that we can read without scraping the body.

This handles two URL conventions seen in the wild:
  - IZA:  /p/iza/izadps/dp18710.html   (prefix "dp" + number)
  - CEPR: /p/cpr/ceprdp/21430.html     (bare number)
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime

from ..models import Paper, make_paper_id
from ._common import clean_html, get_text

log = logging.getLogger(__name__)

_META_RE = re.compile(r'<META\s+NAME="([^"]+)"\s+CONTENT="([^"]*)"', re.IGNORECASE)


def _fix_mojibake(s: str) -> str:
    """IDEAS ships double-encoded UTF-8 (cp1252 round-trip). Recover it."""
    if not s:
        return s
    try:
        return s.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def _parse_meta(html: str) -> dict[str, str]:
    return {k.lower(): _fix_mojibake(v) for k, v in _META_RE.findall(html)}


def _parse_authors(raw: str) -> list[str]:
    return [a.strip() for a in raw.split("&") if a.strip()]


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
    text = re.sub(r"^Downloadable[^!]*!\s*", "", raw)
    return clean_html(text)


def fetch_series(
    *,
    source_name: str,
    journal_label: str,
    listing_url: str,
    paper_url_tpl: str,
    paper_id_pattern: str,
    paper_id_prefix: str = "",
    limit: int = 20,
) -> list[Paper]:
    """Fetch the latest `limit` papers from a single IDEAS series.

    Args:
        source_name: short token stored in Paper.source (e.g. "iza", "cepr")
        journal_label: human-readable label for raw["journal"] (e.g. "IZA DP")
        listing_url: e.g. https://ideas.repec.org/s/iza/izadps.html
        paper_url_tpl: e.g. https://ideas.repec.org/p/iza/izadps/dp{n}.html
        paper_id_pattern: regex with one group capturing the numeric id from
                          per-paper hrefs in the listing
        paper_id_prefix: optional prefix prepended to the numeric id when
                         building the Paper.source_id (e.g. "dp" for IZA)
    """
    try:
        listing = get_text(listing_url)
    except Exception as e:
        log.warning("%s listing fetch failed: %s", source_name, e)
        return []

    nums = sorted({int(m) for m in re.findall(paper_id_pattern, listing)}, reverse=True)
    if not nums:
        log.warning("%s: no paper ids found in listing", source_name)
        return []
    targets = nums[:limit]

    papers: list[Paper] = []
    for n in targets:
        url = paper_url_tpl.format(n=n)
        try:
            html = get_text(url)
        except Exception as e:
            log.warning("%s id=%d fetch failed: %s", source_name, n, e)
            continue

        meta = _parse_meta(html)
        title = meta.get("title", "").strip()
        if not title:
            continue
        source_id = f"{paper_id_prefix}{n}"
        p = Paper(
            id=make_paper_id(source_name, source_id),
            source=source_name,
            source_id=source_id,
            title=title,
            abstract=_clean_abstract(meta.get("description", "")),
            authors=_parse_authors(meta.get("author", "")),
            url=url,
            published=(_parse_date(meta.get("date", ""))
                       or _parse_date(meta.get("citation_publication_date", ""))),
            jel_codes=_parse_jel(meta.get("jel_code", "")),
            raw={"repec_handle": meta.get("handle", ""), "journal": journal_label},
        )
        papers.append(p)

    log.info("%s: fetched %d papers (newest id=%d)",
             source_name, len(papers), targets[0] if targets else 0)
    return papers
