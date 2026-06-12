"""Append-only JSONL storage with dedupe-on-write by paper id."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Iterator

from .models import Paper

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "processed"
PAPERS_PATH = DATA_ROOT / "papers.jsonl"


def load_papers(path: Path = PAPERS_PATH) -> list[Paper]:
    if not path.exists():
        return []
    out: list[Paper] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(Paper.model_validate_json(line))
    return out


def iter_papers(path: Path = PAPERS_PATH) -> Iterator[Paper]:
    if not path.exists():
        return
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield Paper.model_validate_json(line)


def save_papers(papers: Iterable[Paper], path: Path = PAPERS_PATH) -> None:
    """Overwrite the file with the given papers. Caller handles dedupe."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for p in papers:
            f.write(p.model_dump_json() + "\n")


def merge_new(new_papers: Iterable[Paper], path: Path = PAPERS_PATH) -> tuple[int, int]:
    """Merge new papers into the store. Returns (added, updated).

    On conflict (same id), the existing record wins for *enrichment* fields
    (summary/why_it_matters/method/data) but the new record wins for *raw*
    metadata (title/abstract/authors/url) — sources sometimes correct typos.
    """
    existing = {p.id: p for p in load_papers(path)}
    added = 0
    updated = 0
    for p in new_papers:
        prev = existing.get(p.id)
        if prev is None:
            existing[p.id] = p
            added += 1
        else:
            # Keep enrichment from prev, take fresh metadata from p
            merged = p.model_copy(update={
                "summary": prev.summary or p.summary,
                "why_it_matters": prev.why_it_matters or p.why_it_matters,
                "method": prev.method or p.method,
                "data": prev.data or p.data,
                "jel_codes": prev.jel_codes or p.jel_codes,
                "fields": prev.fields or p.fields,
                "fetched_at": prev.fetched_at,
            })
            if merged != prev:
                existing[p.id] = merged
                updated += 1
    save_papers(existing.values(), path)
    return added, updated
