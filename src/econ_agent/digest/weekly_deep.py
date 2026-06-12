"""Weekly deep-reading queue: 5-10 papers worth a PDF read this week."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from ..models import Paper
from .monthly import SOURCE_WEIGHT, render_card


def _deep_score(p: Paper, today: date) -> float:
    # Heavier weight on top venues + recent + abstract length (a proxy for substance)
    s = SOURCE_WEIGHT.get(p.source, 0.5) * 2.0
    if p.published:
        age = (today - p.published).days
        s += max(0.0, 4.0 - age / 7.0)  # decays over ~4 weeks
    s += min(2.0, len(p.abstract) / 800.0)  # longer abstract = more substance, up to 2.0
    if any(j in (p.raw.get("journal") or "") for j in
           ["American Economic Review", "Quarterly Journal",
            "Journal of Political Economy", "Econometrica", "Review of Economic Studies"]):
        s += 2.0  # top-5 bonus
    return s


def build(papers: list[Paper], limit: int = 8, window_days: int = 14) -> str:
    today = date.today()
    cutoff = today - timedelta(days=window_days)
    candidates = [p for p in papers if not p.published or p.published >= cutoff]
    candidates.sort(key=lambda p: _deep_score(p, today), reverse=True)
    picks = candidates[:limit]

    lines = [
        f"# Weekly Deep-Reading Queue — week of {today.isoformat()}",
        "",
        f"{len(picks)} papers selected from the last {window_days} days. "
        "Read these carefully and decide which deserve a structured extraction.",
        "",
    ]
    for i, p in enumerate(picks, 1):
        lines.append(f"## {i}. {p.title}")
        lines.append("")
        lines.append(render_card(p))
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def write(papers: list[Paper], out_path: Path, **kwargs) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build(papers, **kwargs))
    return out_path
