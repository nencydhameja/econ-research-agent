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


def _keyword_match_block(entries: list[dict], text: str) -> list[str]:
    """Generic keyword matcher used for both field labels and method tags.

    Keywords containing at least one uppercase letter match case-sensitively
    (so "DiD" doesn't fire on every English "did", "IV" doesn't fire on
    Roman-numeral chapter headings, "RCT"/"TWFE" require the all-caps form).
    Fully-lowercase keywords match case-insensitively.
    """
    text_lower = text.lower()
    hits: list[str] = []
    for entry in entries:
        for kw in entry.get("keywords", []):
            case_sensitive = any(c.isupper() for c in kw)
            haystack = text if case_sensitive else text_lower
            needle = kw if case_sensitive else kw.lower()
            if " " in needle or "-" in needle:
                if needle in haystack:
                    hits.append(entry["label"])
                    break
            else:
                if re.search(rf"\b{re.escape(needle)}\b", haystack):
                    hits.append(entry["label"])
                    break
    return sorted(set(hits))


def _keyword_labels(text: str) -> list[str]:
    return _keyword_match_block(_taxonomy()["fields"], text)


def _method_labels(text: str) -> list[str]:
    """Apply method-orientation tags (Applied Micro / Theory / Structural /
    Experimental). Orthogonal to field labels — runs in addition, not instead."""
    return _keyword_match_block(_taxonomy().get("method_tags", []), text)


def _nep_labels(nep_tags: list[str]) -> list[str]:
    mapping = _taxonomy().get("nep_to_field", {})
    return sorted({mapping[t] for t in nep_tags if t in mapping})


def classify(p: Paper) -> Paper:
    """Return a copy of p with `fields` populated.

    Fields are *substantive* JEL-based labels (Labor / Public / Finance / ...).
    Method tags are *orthogonal* method-orientation labels (Applied Micro /
    Theory / Structural / Experimental) stored alongside with a "method:"
    prefix so the dashboard can render them in a separate chip color.
    """
    labels: list[str] = []
    nep_tags = [t for t in p.fields if t.startswith("nep-")]
    method_existing = [t for t in p.fields if t.startswith("method:")]

    # 1. NEP tags (highest signal — human-classified by NEP editors)
    labels.extend(_nep_labels(nep_tags))

    # 2. JEL codes (when source provided them)
    for jel in p.jel_codes:
        lbl = _jel_to_label(jel)
        if lbl:
            labels.append(lbl)

    # 3. Keyword fallback on title + abstract for fields
    if not labels:
        labels.extend(_keyword_labels(f"{p.title} {p.abstract}"))

    # 4. Method tags — always run, orthogonal to fields
    method_new = [f"method:{m}" for m in _method_labels(f"{p.title} {p.abstract}")]

    final = sorted(set(labels + nep_tags + method_existing + method_new))
    return p.model_copy(update={"fields": final})


def classify_all(papers: list[Paper]) -> list[Paper]:
    out = [classify(p) for p in papers]
    unclassified = sum(
        1 for p in out
        if not any(not f.startswith(("nep-", "method:")) for f in p.fields)
    )
    tagged_method = sum(
        1 for p in out if any(f.startswith("method:") for f in p.fields)
    )
    log.info(
        "Classified %d papers (%d still without a field label; %d with a method tag)",
        len(out), unclassified, tagged_method,
    )
    return out
