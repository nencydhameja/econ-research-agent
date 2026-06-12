"""Monthly digest: top-N papers grouped by field, with an optional trend brief."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from ..models import Paper

# Source quality weights — used to rank papers when many candidates compete.
SOURCE_WEIGHT = {
    "journal_rss": 3.0,   # published in a peer-reviewed journal
    "nber": 2.0,          # NBER working papers
    "repec_nep": 1.5,     # NEP-classified (human editor signal)
    "openalex_ssrn": 1.0,
    "arxiv": 1.0,
}


def score(p: Paper, today: date) -> float:
    s = SOURCE_WEIGHT.get(p.source, 0.5)
    if p.published:
        age = (today - p.published).days
        s += max(0.0, 3.0 - age / 14.0)  # decays over ~6 weeks
    if p.summary:
        s += 0.5  # enriched papers preferred — we have something to say about them
    if p.jel_codes:
        s += 0.2
    return s


def render_card(p: Paper) -> str:
    field_str = ", ".join(f for f in p.fields if not f.startswith("nep-")) or "Unclassified"
    authors = ", ".join(p.authors[:4])
    if len(p.authors) > 4:
        authors += " et al."
    src = p.raw.get("journal") or p.source.replace("_", " ")
    date_str = p.published.isoformat() if p.published else ""
    pieces = [
        f"### [{p.title}]({p.url})",
        f"*{authors}* — **{src}**, {date_str} — _{field_str}_",
        "",
    ]
    if p.summary:
        pieces.append(p.summary)
        if p.why_it_matters:
            pieces.append("")
            pieces.append(f"**Why it matters:** {p.why_it_matters}")
    elif p.abstract:
        pieces.append(p.abstract[:600] + ("..." if len(p.abstract) > 600 else ""))
    return "\n".join(pieces)


def build(papers: list[Paper], limit: int = 30,
          window_days: int = 30, trend_brief: str = "") -> str:
    today = date.today()
    cutoff = today - timedelta(days=window_days)

    candidates = [p for p in papers if not p.published or p.published >= cutoff]
    candidates.sort(key=lambda p: score(p, today), reverse=True)
    top = candidates[:limit]

    by_field: dict[str, list[Paper]] = defaultdict(list)
    for p in top:
        main_field = next((f for f in p.fields if not f.startswith("nep-")), "Unclassified")
        by_field[main_field].append(p)

    lines = [
        f"# Economics Research Digest — {today.isoformat()}",
        "",
        f"Window: last **{window_days} days** · {len(top)} papers across "
        f"{len(by_field)} fields · drawn from {len({p.source for p in top})} sources.",
        "",
    ]
    if trend_brief:
        lines += ["## What's moving this month", "", trend_brief, ""]

    for field in sorted(by_field.keys()):
        lines.append(f"## {field}")
        lines.append("")
        for p in by_field[field]:
            lines.append(render_card(p))
            lines.append("")
            lines.append("---")
            lines.append("")
    return "\n".join(lines)


def write(papers: list[Paper], out_path: Path, **kwargs) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build(papers, **kwargs))
    return out_path
