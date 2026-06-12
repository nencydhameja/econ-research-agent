"""Shared HTTP client and feedparser helpers."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

import feedparser
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)

USER_AGENT = "econ-research-agent/0.1 (https://github.com/) python-httpx"

_client: httpx.Client | None = None


def http_client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
            timeout=30.0,
            follow_redirects=True,
        )
    return _client


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
def get_text(url: str) -> str:
    r = http_client().get(url)
    r.raise_for_status()
    return r.text


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
def get_json(url: str, params: dict[str, Any] | None = None) -> Any:
    r = http_client().get(url, params=params)
    r.raise_for_status()
    return r.json()


def parse_feed(url: str) -> Any:
    # feedparser handles its own HTTP, but it's slow on retries — wrap it.
    text = get_text(url)
    return feedparser.parse(text)


def parsed_to_date(struct_time: Any) -> date | None:
    if not struct_time:
        return None
    try:
        return datetime(*struct_time[:6], tzinfo=timezone.utc).date()
    except (TypeError, ValueError):
        return None


def clean_html(text: str) -> str:
    """Strip basic HTML tags from feed summaries without pulling in bs4."""
    import re

    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()
