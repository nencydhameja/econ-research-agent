"""RePEc NEP (New Economic Papers) reports via RSS.

NEP is a free email/RSS service that distributes new working papers,
hand-classified by volunteer editors into ~100 field reports (nep-lab,
nep-dev, nep-iue, etc.). The NEP field tag is itself a high-quality
field label — we use it as a primary classification signal.

Each NEP RSS feed contains the papers from the most recent report.
"""

from __future__ import annotations

import logging

from ..models import Paper, make_paper_id
from ._common import clean_html, parse_feed, parsed_to_date

log = logging.getLogger(__name__)

# A curated subset of NEP fields. Full list: http://nep.repec.org/
# Each becomes a feed at https://nep.repec.org/rss/<code>.xml
DEFAULT_NEP_FIELDS = [
    "lab",  # Labour
    "dev",  # Development
    "ure",  # Urban & Real Estate
    "law",  # Law & Economics
    "iue",  # Informal & Underground Economics
    "pub",  # Public Economics
    "mac",  # Macroeconomics
    "mon",  # Monetary Economics
    "fin",  # Finance
    "hea",  # Health Economics
    "edu",  # Education
    "env",  # Environmental Economics
    "ene",  # Energy
    "exp",  # Experimental Economics
    "cbe",  # Cognitive & Behavioural Economics
    "ecm",  # Econometrics
    "mic",  # Microeconomics
    "ind",  # Industrial Organization
    "int",  # International Trade
    "ifn",  # International Finance
    "his",  # Economic History
    "pol",  # Positive Political Economics
    "ger",  # Gender
    "tid",  # Technology & Industrial Dynamics
    "cna",  # China
]


def _feed_url(nep_code: str) -> str:
    return f"https://nep.repec.org/rss/{nep_code}.xml"


def fetch(nep_fields: list[str] | None = None, per_field_limit: int = 30) -> list[Paper]:
    fields = nep_fields or DEFAULT_NEP_FIELDS
    out: dict[str, Paper] = {}  # paper_id -> Paper, accumulating NEP tags

    for code in fields:
        url = _feed_url(code)
        try:
            feed = parse_feed(url)
        except Exception as e:
            log.warning("NEP %s: fetch failed: %s", code, e)
            continue

        for entry in feed.entries[:per_field_limit]:
            entry_url = entry.get("link", "")
            # NEP entries are RePEc handles like RePEc:nbr:nberwo:33145
            handle = entry.get("id", "") or entry_url
            source_id = handle.split("/")[-1] if "/" in handle else handle

            pid = make_paper_id("repec_nep", source_id)
            if pid in out:
                # Same paper appeared in another NEP report — accumulate the tag
                out[pid].fields = sorted(set(out[pid].fields + [f"nep-{code}"]))
                continue

            p = Paper(
                id=pid,
                source="repec_nep",
                source_id=source_id,
                title=clean_html(entry.get("title", "")).strip(),
                abstract=clean_html(entry.get("summary", entry.get("description", ""))),
                url=entry_url,
                published=parsed_to_date(
                    entry.get("published_parsed") or entry.get("updated_parsed")
                ),
                fields=[f"nep-{code}"],
                raw={"repec_handle": handle},
            )
            out[pid] = p

    papers = list(out.values())
    log.info("RePEc NEP: fetched %d unique papers across %d fields", len(papers), len(fields))
    return papers
