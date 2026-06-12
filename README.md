# Economics Research Agent

A literature-radar tool for economics. Pulls new working papers and journal
articles from **NBER**, **arXiv (econ.\*)**, **RePEc / NEP**, **SSRN (via
OpenAlex)**, and a curated set of **top-journal RSS feeds**; classifies them
by field (JEL + NEP + keywords + optional Claude); produces a monthly digest
and a weekly deep-reading queue; serves it all in a **Streamlit** dashboard.

Inspired by [Cynthia-Xinying/accounting-research-agent](https://github.com/Cynthia-Xinying/accounting-research-agent).

## What you get

- `data/processed/papers.jsonl` — the deduplicated paper library
- `digests/monthly_latest.md` — top-30 papers grouped by field, with a Claude-written trend brief
- `digests/weekly_deep_latest.md` — 5-10 papers flagged for a careful PDF read this week
- A Streamlit dashboard at `dashboard/app.py` (deploys free on Streamlit Community Cloud)

## Install

```bash
git clone <your fork> econ-research-agent
cd econ-research-agent
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Use it locally

```bash
# 1. Collect from all sources, classify, merge into the JSONL store
econ-agent -v collect

# Or restrict to specific sources
econ-agent collect --sources nber arxiv repec_nep

# 2. Optionally enrich with Claude summaries (needs ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY=sk-ant-...
econ-agent -v enrich --limit 50 --trend

# 3. Build digests
econ-agent digest monthly --limit 30 --window 30
econ-agent digest weekly  --limit 8  --window 14

# 4. Browse in the dashboard
streamlit run dashboard/app.py

# Quick sanity check
econ-agent stats
```

## Deploy the dashboard (free)

1. Push this repo to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io), connect the repo,
   set main file path to `dashboard/app.py`.
3. Streamlit Cloud installs from `dashboard/requirements.txt` automatically.

## Automate weekly refresh

`.github/workflows/weekly-refresh.yml` runs every Monday at 09:00 UTC:
collect → enrich → build digests → commit back to the repo. Streamlit Cloud
re-reads on its next request.

To enable Claude enrichment in the workflow, add a repo secret:

- **Settings → Secrets and variables → Actions → New repository secret**
- Name `ANTHROPIC_API_KEY`, value your key from console.anthropic.com.

The workflow is safe without the secret — it just skips the enrichment step.

## Configuration

- `config/journal_feeds.yaml` — top-journal RSS feeds (edit freely; per-feed
  failures don't break the run)
- `config/jel_taxonomy.yaml` — field labels, JEL prefix mapping, and the
  NEP-code → field mapping used by the classifier

## Data model

One Pydantic `Paper` per record (see `src/econ_agent/models.py`). Stable id
prefers DOI; falls back to a hash of `(source, source_id)`. The JSONL store
is append-and-merge — re-running `collect` updates metadata in place but
preserves enrichment so you don't pay for re-summarizing.

## What's intentionally out of v1

- **SSRN direct scraping** — they actively block it. We use OpenAlex's SSRN
  mirror instead. Coverage is good but not 100% of SSRN postings.
- **PDF extraction** — Cynthia's agent has a layer-2 PDF reader. Easy to add
  later: `httpx.get(pdf_url)` + `pypdf` + a Claude pass.
- **BibTeX / Zotero export** — not built yet; the JSONL is the source of truth
  and a small `scripts/to_bibtex.py` would be ~30 lines.

## License

MIT.
