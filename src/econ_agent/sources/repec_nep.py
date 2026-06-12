"""RePEc NEP (New Economic Papers) reports.

DISABLED in v1: NEP discontinued its public RSS feeds (all /rss/{code}.xml
return 404 as of 2026-06). The HTML report pages at nep.repec.org/nep-{code}/
use obfuscated CSS classes that resist scraping. The RePEc API at
api.repec.org requires registration and has no NEP-listing method.

Future options to re-enable:
  - Apply for a RePEc API key and request a NEP method
  - Parse RePEc's OAI-PMH endpoint at oai.repec.org and re-classify against
    our own taxonomy (loses NEP editor signal)
  - Email contact NEP director for a stable bibliographic export

For now this module is a no-op; the other four sources cover ~90% of new
econ working papers anyway.
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
    log.info("RePEc NEP: disabled (no public listing API; see module docstring)")
    return []
