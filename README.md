# Economics Research Agent

A literature-radar tool for economics. Pulls new working papers and journal
articles from six public sources, classifies each paper by **substantive field**
(JEL-based) and **method orientation** (DiD / RDD / IV / RCT / Structural /
Theory / …), optionally enriches with Claude summaries, and serves it all
through a **Streamlit dashboard**.

- **Live dashboard:** https://econ-research-agent.streamlit.app/
- **Repo:** https://github.com/nencydhameja/econ-research-agent
- **Refresh cadence:** twice daily (07:00 + 19:00 UTC) via GitHub Actions

Inspired by [Cynthia-Xinying/accounting-research-agent](https://github.com/Cynthia-Xinying/accounting-research-agent).

## Sources

| Source | What it covers | How we pull it |
|---|---|---|
| **NBER** | Working papers, the de-facto firehose for top US research | RSS feed at `back.nber.org/rss/new.xml` |
| **arXiv** | Preprints in `econ.EM`, `econ.GN`, `econ.TH`, `q-fin.EC` | arXiv Atom API |
| **IZA** | IZA Discussion Papers (labour econ) | IDEAS series page + per-paper `<META>` tags |
| **CEPR** | CEPR Discussion Papers | IDEAS series page + per-paper `<META>` tags |
| **SSRN** | SSRN-hosted economics preprints | OpenAlex `/works` filtered to SSRN source + Economics concept |
| **Top journals** | 17 curated AEA / Wiley / Elsevier / OUP RSS feeds | `feedparser` over `config/journal_feeds.yaml` |

**Disabled:** RePEc/NEP discontinued its RSS feeds and the HTML pages use
obfuscated CSS classes against scraping. The module is a no-op with a
docstring outlining re-enable paths (API key, OAI-PMH, NEP director email).

**Per-feed failure is tolerated.** A bad URL or 503 from one journal RSS
doesn't break the run; that source just contributes zero papers.

## What you get

- `data/processed/papers.jsonl` — the deduplicated paper library (~600 papers in steady state)
- `digests/monthly_latest.md` — top-30 papers grouped by field, with a Claude-written trend brief
- `digests/weekly_deep_latest.md` — 5-10 papers flagged for a careful PDF read this week
- Streamlit dashboard at `dashboard/app.py` (Filters, search, three-color chips, overview charts)

## Classification

Two orthogonal layers — every paper can carry **both**.

**Substantive field** (one of 15 JEL-derived labels: Labor & Demographic
Economics, Financial Economics, Macroeconomics, Public Economics, …). Picked
in this order: NEP tag → explicit JEL code → keyword match on title+abstract → Claude.

**Method orientation** (any of 13 specific methods: `DiD`, `RDD`, `IV`,
`Synthetic Control`, `RCT`, `Lab Experiment`, `Field Experiment`, `Survey
Experiment`, `Structural`, `Theory`, `Machine Learning`, `Propensity Score`,
`Natural Experiment`). Keyword matcher is case-aware — `DiD` doesn't fire on
every English "did", `IV` doesn't fire on Roman numerals, `RCT`/`TWFE`
require the all-caps form.

Edit `config/jel_taxonomy.yaml` to rename, split, merge, or add labels.
No code changes needed.

## Install

```bash
git clone https://github.com/nencydhameja/econ-research-agent
cd econ-research-agent
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Use it locally

```bash
# 1. Collect from all sources, classify, merge into the JSONL store
econ-agent -v collect

# Or restrict to specific sources
econ-agent collect --sources nber arxiv iza cepr

# 2. Optionally enrich with Claude summaries (needs ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY=sk-ant-...
econ-agent -v enrich --limit 50 --trend

# 3. Build digests
econ-agent digest monthly --limit 30 --window 30
econ-agent digest weekly  --limit 8  --window 14

# 4. Browse in the dashboard
streamlit run dashboard/app.py     # opens at localhost:8501

# Sanity check: counts by source and field
econ-agent stats
```

## Deploy the dashboard (free)

1. Push the repo to GitHub (if forking).
2. Go to [share.streamlit.io](https://share.streamlit.io) → connect the repo.
3. Main file path: `dashboard/app.py`.
4. Streamlit Cloud installs from `dashboard/requirements.txt` automatically. First build ~2 min.

`load_df()` keys its cache on the JSONL file mtime, so each new commit by
the cron invalidates the cache immediately — no 10-minute stale window.

## Automate refresh

`.github/workflows/refresh.yml` runs **twice daily**:
- **07:00 UTC** — catches NBER's overnight drops
- **19:00 UTC** — catches afternoon arXiv / SSRN postings

Each run: collect → (optional) enrich → build digests → commit `papers.jsonl`
+ digests back to the repo. Streamlit Cloud picks up the change on its
next request.

To enable Claude enrichment in the workflow, add a repo secret:

- **Settings → Secrets and variables → Actions → New repository secret**
- Name `ANTHROPIC_API_KEY`, value your key from console.anthropic.com.

The workflow is safe without the secret — it just skips the enrichment step.

## Configuration

- `config/journal_feeds.yaml` — top-journal RSS feeds. Edit to add, remove,
  or fix broken URLs. AEA & OUP feeds (AER, QJE, ReStud, AEJs, JEL, JEP, RFS)
  are currently dead/gated; the seven that work are JPE, Econometrica, JoF,
  JFE, JOLE, JPubE, JDE.
- `config/jel_taxonomy.yaml` — three blocks:
  - `fields:` — substantive labels with JEL prefix + keyword lists
  - `method_tags:` — orthogonal method labels with keyword lists
  - `nep_to_field:` — mapping from NEP report codes to field labels

## Architecture

```
src/econ_agent/
├── models.py            # Pydantic Paper, stable id (DOI or hash)
├── storage.py           # append-and-merge JSONL with enrichment preservation
├── cli.py               # econ-agent {collect, enrich, digest, stats}
├── sources/
│   ├── nber.py          # NBER RSS (falls back to today's date — RSS strips pubDate)
│   ├── arxiv.py         # arXiv Atom API
│   ├── _ideas.py        # shared IDEAS scraper (used by IZA, CEPR)
│   ├── iza.py           # 12-line wrapper around _ideas.fetch_series
│   ├── cepr.py          # 12-line wrapper around _ideas.fetch_series
│   ├── openalex_ssrn.py # OpenAlex /works filtered to SSRN + Economics
│   ├── journals.py      # publisher RSS, configured in YAML
│   └── repec_nep.py     # DISABLED — see docstring
├── pipeline/
│   ├── classify.py      # NEP → JEL → keyword (case-aware) → optional Claude
│   └── enrich.py        # Claude Sonnet 4.6 per paper + Opus 4.7 trend brief
└── digest/
    ├── monthly.py       # Top-30 grouped by field
    └── weekly_deep.py   # 5-10 flagged for PDF read
```

## Data model

One Pydantic `Paper` per record (see `src/econ_agent/models.py`). Stable id
prefers DOI; falls back to a hash of `(source, source_id)`. The JSONL store
is append-and-merge — re-running `collect` updates metadata in place but
preserves enrichment so you don't pay to re-summarize.

Field tags are stored in `Paper.fields` with prefixes that let the dashboard
split them visually:
- bare label → substantive field (e.g. `Labor & Demographic Economics`)
- `method:` prefix → method tag (e.g. `method:DiD`)
- `nep-` prefix → original NEP report tag (e.g. `nep-lab`)

## What's intentionally out of v1

- **SSRN direct scraping** — actively blocked. We use OpenAlex's SSRN mirror.
  Coverage is good but lags by 1-3 days.
- **PDF extraction** — easy to add later: `httpx.get(pdf_url)` + `pypdf` + a Claude pass.
- **BibTeX / Zotero export** — not built yet; the JSONL is the source of
  truth and `scripts/to_bibtex.py` would be ~30 lines.
- **Real-time polling** — twice-daily is enough given that the sources
  themselves publish in batches (NBER overnight, arXiv at submission cutoffs)
  and OpenAlex's own ingestion has a 1-3 day lag.

## Adding a new IDEAS-hosted series

Adding e.g. Bonn or Tinbergen DPs is a 12-line wrapper:

```python
# src/econ_agent/sources/bonn.py
from ..models import Paper
from . import _ideas

def fetch(limit: int = 20) -> list[Paper]:
    return _ideas.fetch_series(
        source_name="bonn",
        journal_label="Bonn DP",
        listing_url="https://ideas.repec.org/s/bon/bonedp.html",
        paper_url_tpl="https://ideas.repec.org/p/bon/bonedp/{n}.html",
        paper_id_pattern=r"/p/bon/bonedp/(\d+)\.html",
    )
```

Then register it in `sources/__init__.py`.

## License

MIT.
