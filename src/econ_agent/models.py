"""Canonical paper data model."""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Paper(BaseModel):
    """One paper, normalized across sources."""

    id: str  # stable hash of (source, source_id) or (doi)
    source: str  # "nber" | "arxiv" | "repec_nep" | "journal_rss" | "openalex"
    source_id: str  # native id from source (NBER w-number, arXiv id, DOI, etc.)
    title: str
    abstract: str = ""
    authors: list[str] = Field(default_factory=list)
    published: date | None = None
    url: str = ""
    pdf_url: str = ""
    doi: str = ""

    # classification
    jel_codes: list[str] = Field(default_factory=list)
    fields: list[str] = Field(default_factory=list)  # our taxonomy labels

    # enrichment (filled later by Claude)
    summary: str = ""  # one-paragraph editor-style summary
    why_it_matters: str = ""
    method: str = ""
    data: str = ""

    # provenance
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    raw: dict[str, Any] = Field(default_factory=dict)  # source-specific extras

    @field_validator("authors", mode="before")
    @classmethod
    def _coerce_authors(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return list(v)


def make_paper_id(source: str, source_id: str, doi: str = "") -> str:
    """Stable id: prefer DOI when present, else hash(source+source_id)."""
    if doi:
        return "doi:" + doi.lower().strip()
    key = f"{source}:{source_id}".lower().strip()
    return hashlib.sha1(key.encode()).hexdigest()[:16]
