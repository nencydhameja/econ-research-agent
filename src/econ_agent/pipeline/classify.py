"""Field classification: JEL codes first, then NEP tags, then keywords.

Cheap and deterministic. LLM-based classification is reserved for papers
that still have no field after this pass (handled in pipeline.enrich).
"""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path

import yaml

from ..models import Paper

log = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "jel_taxonomy.yaml"


@lru_cache(maxsize=1)
def _taxonomy() -> dict:
    with CONFIG_PATH.open() as f:
        return yaml.safe_load(f)


def _jel_to_label(jel: str) -> str | None:
    prefix = jel[0].upper() if jel else ""
    for entry in _taxonomy()["fields"]:
        if prefix in entry.get("jel_prefixes", []):
            return entry["label"]
    return None


def _keyword_labels(text: str) -> list[str]:
    text_lower = text.lower()
    hits: list[str] = []
    for entry in _taxonomy()["fields"]:
        for kw in entry.get("keywords", []):
            # Use word-boundary match for short keywords, substring for phrases
            if " " in kw:
                if kw.lower() in text_lower:
                    hits.append(entry["label"])
                    break
            else:
                if re.search(rf"\b{re.escape(kw.lower())}\b", text_lower):
                    hits.append(entry["label"])
                    break
    return sorted(set(hits))


def _nep_labels(nep_tags: list[str]) -> list[str]:
    mapping = _taxonomy().get("nep_to_field", {})
    return sorted({mapping[t] for t in nep_tags if t in mapping})


def classify(p: Paper) -> Paper:
    """Return a copy of p with `fields` populated."""
    labels: list[str] = []

    # 1. NEP tags (highest signal — human-classified by NEP editors)
    nep_tags = [t for t in p.fields if t.startswith("nep-")]
    labels.extend(_nep_labels(nep_tags))

    # 2. JEL codes (when source provided them)
    for jel in p.jel_codes:
        lbl = _jel_to_label(jel)
        if lbl:
            labels.append(lbl)

    # 3. Keyword fallback on title + abstract
    if not labels:
        text = f"{p.title} {p.abstract}"
        labels.extend(_keyword_labels(text))

    # Keep nep- tags as auxiliary metadata in fields too (for the dashboard)
    final = sorted(set(labels)) + nep_tags
    return p.model_copy(update={"fields": sorted(set(final))})


def classify_all(papers: list[Paper]) -> list[Paper]:
    out = [classify(p) for p in papers]
    unclassified = sum(1 for p in out if not any(f for f in p.fields if not f.startswith("nep-")))
    log.info("Classified %d papers (%d still without a field label)", len(out), unclassified)
    return out
