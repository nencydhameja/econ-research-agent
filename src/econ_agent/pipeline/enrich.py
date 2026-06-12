"""Claude-powered enrichment: per-paper summaries + monthly trend writeup.

Uses prompt caching on the system prompt (which contains the editorial
voice + JEL taxonomy) so the per-paper marginal cost stays small.

Env: ANTHROPIC_API_KEY. If unset, enrichment is skipped (no-op).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import yaml

from ..models import Paper

log = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"  # cheap enough for thousands of papers; bump to opus for trend writeup
TAXONOMY_PATH = Path(__file__).resolve().parents[3] / "config" / "jel_taxonomy.yaml"

SYSTEM_PROMPT = """You are an editor for an economics research digest.
You read paper titles and abstracts and produce concise, accurate, fair summaries
in the voice of a careful field economist (NBT Reporter / JEL summary style).

Rules:
- Never invent findings, numbers, or methods that are not in the abstract.
- If a piece of structured info (method/data) is unclear from the abstract, write "not specified in abstract".
- Keep summaries terse and information-dense. No hype words. No emojis.
- "Why it matters" should connect the paper to an active debate or a policy/empirical question,
  in 1-2 sentences. If the abstract gives no hook, write a sober one-sentence framing.

Output format: strict JSON only, matching the requested schema.
"""


def _client():
    try:
        from anthropic import Anthropic
    except ImportError:
        raise RuntimeError("anthropic package not installed. `pip install anthropic`.")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return Anthropic(api_key=api_key)


def _taxonomy_block() -> str:
    with TAXONOMY_PATH.open() as f:
        tax = yaml.safe_load(f)
    labels = [e["label"] for e in tax["fields"]]
    return "Available field labels:\n" + "\n".join(f"- {l}" for l in labels)


def enrich_paper(client, paper: Paper) -> Paper:
    """Ask Claude for a structured summary. Returns paper with fields filled in.

    Caches the system prompt + taxonomy across calls so per-paper cost is small.
    """
    user_msg = (
        f"Title: {paper.title}\n\n"
        f"Authors: {', '.join(paper.authors) or 'unknown'}\n\n"
        f"Abstract:\n{paper.abstract[:3500]}\n\n"
        "Return JSON with these keys:\n"
        '  "summary": one paragraph (3-5 sentences) describing question, method (if stated),'
        ' main finding (if stated), in plain English.\n'
        '  "why_it_matters": 1-2 sentences placing the paper in context.\n'
        '  "method": short phrase (e.g., "diff-in-diff with IV", "structural model",'
        ' "RCT", "RDD") or "not specified in abstract".\n'
        '  "data": short phrase (e.g., "US linked employer-employee data 2005-2019")'
        ' or "not specified in abstract".\n'
        '  "fields": list of 1-3 labels from the taxonomy.\n'
    )

    resp = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT + "\n\n" + _taxonomy_block(),
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_msg}],
    )

    text = "".join(b.text for b in resp.content if hasattr(b, "text"))
    try:
        # Claude sometimes wraps JSON in ```json fences — strip them
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
        data = json.loads(text)
    except json.JSONDecodeError:
        log.warning("Claude returned non-JSON for %s; skipping", paper.id)
        return paper

    return paper.model_copy(update={
        "summary": data.get("summary", paper.summary),
        "why_it_matters": data.get("why_it_matters", paper.why_it_matters),
        "method": data.get("method", paper.method),
        "data": data.get("data", paper.data),
        "fields": sorted(set(list(paper.fields) + list(data.get("fields", [])))),
    })


def enrich_all(papers: list[Paper], limit: int | None = None,
               skip_already_enriched: bool = True) -> list[Paper]:
    """Enrich up to `limit` papers that don't yet have a summary."""
    client = _client()
    if client is None:
        log.info("ANTHROPIC_API_KEY not set; skipping enrichment.")
        return papers

    to_enrich = [p for p in papers if not (skip_already_enriched and p.summary)]
    if limit is not None:
        to_enrich = to_enrich[:limit]
    log.info("Enriching %d papers", len(to_enrich))

    by_id = {p.id: p for p in papers}
    for i, p in enumerate(to_enrich, 1):
        try:
            by_id[p.id] = enrich_paper(client, p)
        except Exception as e:
            log.warning("Enrichment failed for %s: %s", p.id, e)
        if i % 10 == 0:
            log.info("  ... %d/%d enriched", i, len(to_enrich))

    return list(by_id.values())


def write_trend_brief(papers: list[Paper], out_path: Path) -> None:
    """Ask Claude (Opus) for a 1-page trend brief over the last batch."""
    client = _client()
    if client is None:
        return

    # Cap input — we only need titles + fields + 1-line summaries
    cards = []
    for p in papers[:80]:
        line = f"- [{', '.join(p.fields[:2]) or 'unclassified'}] {p.title}"
        if p.summary:
            line += f" — {p.summary.split('.')[0]}."
        cards.append(line)
    block = "\n".join(cards)

    resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=1200,
        system=[
            {
                "type": "text",
                "text": (
                    "You are writing a monthly economics research trend brief for a PhD-level reader. "
                    "Identify 3-5 emergent themes across the listed papers. For each theme: a one-line "
                    "title, 2-3 sentences of synthesis, and 2-3 paper titles in parentheses. No hype, "
                    "no invented findings. If a theme is too thin, drop it."
                ),
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": f"Papers this period:\n\n{block}"}],
    )
    text = "".join(b.text for b in resp.content if hasattr(b, "text"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text)
    log.info("Trend brief written to %s", out_path)
