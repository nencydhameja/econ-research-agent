"""Command-line entry point.

Subcommands:
  econ-agent collect              # fetch from all sources, classify, merge to JSONL
  econ-agent collect --sources nber arxiv
  econ-agent enrich --limit 50    # run Claude enrichment on un-enriched papers
  econ-agent digest monthly       # write monthly digest markdown
  econ-agent digest weekly        # write weekly deep-reading queue
  econ-agent stats                # show counts by source/field
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .digest import monthly as monthly_digest
from .digest import weekly_deep
from .pipeline import classify, enrich
from .sources import ALL_SOURCES
from .storage import DATA_ROOT, load_papers, merge_new, save_papers

log = logging.getLogger("econ_agent")

DIGEST_DIR = Path(__file__).resolve().parents[2] / "digests"


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_collect(args: argparse.Namespace) -> None:
    sources = args.sources or list(ALL_SOURCES.keys())
    all_new = []
    for name in sources:
        mod = ALL_SOURCES.get(name)
        if mod is None:
            log.warning("Unknown source: %s", name)
            continue
        log.info("Fetching from %s...", name)
        try:
            all_new.extend(mod.fetch())
        except Exception as e:
            log.error("Source %s failed: %s", name, e)

    log.info("Classifying %d new papers", len(all_new))
    classified = classify.classify_all(all_new)
    added, updated = merge_new(classified)
    log.info("Merge: +%d new, ~%d updated", added, updated)


def cmd_enrich(args: argparse.Namespace) -> None:
    papers = load_papers()
    enriched = enrich.enrich_all(papers, limit=args.limit)
    save_papers(enriched)
    if args.trend:
        out = DIGEST_DIR / "trend_brief.md"
        enrich.write_trend_brief(enriched, out)


def cmd_digest(args: argparse.Namespace) -> None:
    papers = load_papers()
    if args.kind == "monthly":
        trend = ""
        trend_path = DIGEST_DIR / "trend_brief.md"
        if trend_path.exists():
            trend = trend_path.read_text()
        out = monthly_digest.write(
            papers,
            DIGEST_DIR / "monthly_latest.md",
            limit=args.limit,
            window_days=args.window,
            trend_brief=trend,
        )
        log.info("Wrote %s", out)
    elif args.kind == "weekly":
        out = weekly_deep.write(
            papers,
            DIGEST_DIR / "weekly_deep_latest.md",
            limit=args.limit,
            window_days=args.window,
        )
        log.info("Wrote %s", out)


def cmd_stats(args: argparse.Namespace) -> None:
    papers = load_papers()
    print(f"Total papers: {len(papers)}")
    by_src: dict[str, int] = {}
    by_field: dict[str, int] = {}
    enriched = 0
    for p in papers:
        by_src[p.source] = by_src.get(p.source, 0) + 1
        for f in p.fields:
            if not f.startswith("nep-"):
                by_field[f] = by_field.get(f, 0) + 1
        if p.summary:
            enriched += 1
    print(f"Enriched: {enriched}/{len(papers)}")
    print("\nBy source:")
    for k, v in sorted(by_src.items(), key=lambda x: -x[1]):
        print(f"  {k:20s} {v}")
    print("\nBy field:")
    for k, v in sorted(by_field.items(), key=lambda x: -x[1]):
        print(f"  {k:40s} {v}")


def main() -> None:
    p = argparse.ArgumentParser(prog="econ-agent")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_collect = sub.add_parser("collect", help="Fetch from sources and merge into the store")
    p_collect.add_argument("--sources", nargs="*",
                           help=f"Subset of: {', '.join(ALL_SOURCES)}")
    p_collect.set_defaults(func=cmd_collect)

    p_enrich = sub.add_parser("enrich", help="Run Claude enrichment on un-enriched papers")
    p_enrich.add_argument("--limit", type=int, default=50)
    p_enrich.add_argument("--trend", action="store_true",
                          help="Also write a monthly trend brief")
    p_enrich.set_defaults(func=cmd_enrich)

    p_digest = sub.add_parser("digest", help="Write digest markdown")
    p_digest.add_argument("kind", choices=["monthly", "weekly"])
    p_digest.add_argument("--limit", type=int, default=30)
    p_digest.add_argument("--window", type=int, default=30, help="Days back to consider")
    p_digest.set_defaults(func=cmd_digest)

    p_stats = sub.add_parser("stats", help="Print store summary")
    p_stats.set_defaults(func=cmd_stats)

    args = p.parse_args()
    _setup_logging(args.verbose)
    args.func(args)


if __name__ == "__main__":
    main()
