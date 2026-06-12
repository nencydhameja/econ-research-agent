"""Streamlit dashboard for the Economics Research Agent.

Deploy on Streamlit Community Cloud:
  1. Push the repo to GitHub (data/processed/papers.jsonl included)
  2. share.streamlit.io → New app → point at dashboard/app.py
  3. The weekly GitHub Action refreshes papers.jsonl; Streamlit re-reads on app restart.
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

# Make `econ_agent` importable when running from repo root
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from econ_agent.storage import PAPERS_PATH  # noqa: E402

st.set_page_config(page_title="Econ Research Agent", layout="wide",
                   initial_sidebar_state="expanded")


@st.cache_data(ttl=600)
def load_df(_mtime: float) -> pd.DataFrame:
    """Mtime is in the signature only so cache invalidates when the file
    is updated by the GitHub Actions cron — Streamlit Cloud otherwise
    keeps serving the prior parse for the full ttl."""
    if not PAPERS_PATH.exists():
        return pd.DataFrame()
    rows = []
    with PAPERS_PATH.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    df = pd.DataFrame(rows)
    if not df.empty and "published" in df.columns:
        df["published"] = pd.to_datetime(df["published"], errors="coerce")
    # Defensive: always ensure these columns exist as the right type, even
    # if the JSONL is empty or missing fields for one source.
    for col, default in [("title", ""), ("abstract", ""), ("summary", ""),
                          ("source", ""), ("url", ""), ("fields", None),
                          ("authors", None), ("published", pd.NaT)]:
        if col not in df.columns:
            df[col] = default
    return df


df = load_df(PAPERS_PATH.stat().st_mtime if PAPERS_PATH.exists() else 0.0)

st.title("Economics Research Agent")
if df.empty:
    st.info(
        "No papers yet. Run `python -m econ_agent.cli collect` to populate the store, "
        "then refresh this page."
    )
    st.stop()

_latest = df["published"].dropna().max()
_latest_str = _latest.date().isoformat() if pd.notna(_latest) else "n/a"
st.caption(
    f"{len(df):,} papers · "
    f"{df['source'].nunique()} sources · "
    f"latest publication: {_latest_str}"
)

# --- Sidebar filters ---
with st.sidebar:
    st.header("Filters")
    today = date.today()
    default_start = today - timedelta(days=30)
    date_range = st.date_input(
        "Published between",
        value=(default_start, today),
        max_value=today,
    )
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start, end = date_range
    else:
        start, end = default_start, today

    all_sources = sorted(df["source"].dropna().unique().tolist())
    src_sel = st.multiselect("Sources", all_sources, default=all_sources)

    # Field labels = exploded `fields`, dropping NaN + nep- + method: prefixes
    all_tags = df["fields"].dropna().explode().dropna()
    all_tags = all_tags[all_tags.apply(lambda x: isinstance(x, str))]
    field_series = all_tags[~all_tags.str.startswith(("nep-", "method:"))]
    all_fields = sorted(field_series.unique().tolist())
    field_sel = st.multiselect("Fields", all_fields)

    # Method tags = stored with "method:" prefix; strip the prefix for display
    method_series = all_tags[all_tags.str.startswith("method:")].str[len("method:"):]
    all_methods = sorted(method_series.unique().tolist())
    method_sel = st.multiselect("Method", all_methods)

    q = st.text_input("Search title / abstract", "")

    only_enriched = st.checkbox("Only papers with Claude summary", value=False)

# --- Apply filters ---
filt = df.copy()
filt = filt[filt["source"].isin(src_sel)]
if start and end:
    pub = pd.to_datetime(filt["published"], errors="coerce")
    pub_dates = pub.dt.date
    filt = filt[pub.isna() | ((pub_dates >= start) & (pub_dates <= end))]
if method_sel:
    method_tags_wanted = {f"method:{m}" for m in method_sel}
    filt = filt[filt["fields"].apply(
        lambda fs: bool(set(fs or []) & method_tags_wanted)
    )]
if field_sel:
    filt = filt[filt["fields"].apply(
        lambda fs: bool(set(fs or []) & set(field_sel))
    )]
if q:
    ql = q.lower()
    filt = filt[
        filt["title"].fillna("").str.lower().str.contains(ql) |
        filt["abstract"].fillna("").str.lower().str.contains(ql)
    ]
if only_enriched:
    filt = filt[filt["summary"].fillna("").str.len() > 0]

st.markdown(f"**{len(filt):,} papers match.**")

# --- Tabs ---
tab_papers, tab_overview, tab_digest = st.tabs(["Papers", "Overview", "Latest digest"])

with tab_papers:
    sort_by = st.radio("Sort by", ["Newest", "Source quality", "Title"],
                       horizontal=True, label_visibility="collapsed")
    if len(filt) > 0:
        if sort_by == "Newest" and "published" in filt.columns:
            filt = filt.sort_values("published", ascending=False, na_position="last")
        elif sort_by == "Source quality" and "source" in filt.columns:
            order = {"journal_rss": 5, "nber": 4, "iza": 3,
                     "repec_nep": 2, "openalex_ssrn": 1, "arxiv": 1}
            filt = filt.assign(_rank=filt["source"].map(order).fillna(0))
            sort_keys = ["_rank"] + (["published"] if "published" in filt.columns else [])
            ascending = [False] + ([False] if "published" in filt.columns else [])
            filt = filt.sort_values(sort_keys, ascending=ascending)
        elif "title" in filt.columns:
            filt = filt.sort_values("title")

    # Paginate
    PAGE = 25
    page_n = st.number_input("Page", min_value=1,
                             max_value=max(1, (len(filt) - 1) // PAGE + 1),
                             value=1, step=1)
    start_i = (page_n - 1) * PAGE

    def _chip(text: str, bg: str, fg: str) -> str:
        return (f"<span style='display:inline-block;background:{bg};color:{fg};"
                f"font-size:0.72rem;padding:0.1rem 0.5rem;border-radius:10px;"
                f"margin-right:0.35rem;margin-top:0.25rem;white-space:nowrap'>"
                f"{text}</span>")

    for _, row in filt.iloc[start_i:start_i + PAGE].iterrows():
        all_tags_row = [f for f in (row.get("fields") or [])
                        if isinstance(f, str) and not f.startswith("nep-")]
        fields = [f for f in all_tags_row if not f.startswith("method:")]
        methods = [f[len("method:"):] for f in all_tags_row if f.startswith("method:")]
        with st.container(border=True):
            st.markdown(
                f"<div style='font-size:0.95rem;font-weight:600;line-height:1.3;"
                f"margin-bottom:0.15rem'>"
                f"<a href='{row['url']}' target='_blank' "
                f"style='text-decoration:none'>{row['title']}</a></div>",
                unsafe_allow_html=True,
            )
            meta_bits = []
            if row.get("authors"):
                a = ", ".join(row["authors"][:4])
                if len(row["authors"]) > 4:
                    a += " et al."
                meta_bits.append(a)
            if pd.notna(row.get("published")):
                _pub = row["published"]
                meta_bits.append(_pub.date().isoformat()
                                 if hasattr(_pub, "date") else str(_pub))
            st.markdown(
                f"<div style='font-size:0.78rem;color:#666;margin-bottom:0.3rem'>"
                f"{' — '.join(meta_bits)}</div>",
                unsafe_allow_html=True,
            )

            if row.get("summary"):
                st.markdown(
                    f"<div style='font-size:0.85rem;line-height:1.4'>{row['summary']}</div>",
                    unsafe_allow_html=True,
                )
                if row.get("why_it_matters"):
                    st.markdown(
                        f"<div style='font-size:0.82rem;color:#444;margin-top:0.3rem'>"
                        f"<b>Why it matters:</b> {row['why_it_matters']}</div>",
                        unsafe_allow_html=True,
                    )
            elif row.get("abstract"):
                st.markdown(
                    f"<div style='font-size:0.83rem;line-height:1.4'>"
                    f"{row['abstract']}</div>",
                    unsafe_allow_html=True,
                )

            # Tag row: source (indigo) + field (green) + method (amber) chips
            src_label = (row.get("raw", {}).get("journal")
                         or row["source"].replace("_", " "))
            chips = [_chip(src_label, "#e8eaf6", "#1a237e")]
            for f in fields:
                chips.append(_chip(f, "#e8f5e9", "#1b5e20"))
            for m in methods:
                chips.append(_chip(m, "#fff3e0", "#e65100"))
            st.markdown(
                f"<div style='margin-top:0.5rem'>{''.join(chips)}</div>",
                unsafe_allow_html=True,
            )

with tab_overview:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Papers by source")
        st.bar_chart(filt["source"].value_counts())
    with col2:
        st.subheader("Papers by field")
        flat_tags = filt["fields"].dropna().explode().dropna()
        flat_tags = flat_tags[flat_tags.apply(lambda x: isinstance(x, str))]
        flat_fields = flat_tags[~flat_tags.str.startswith(("nep-", "method:"))]
        st.bar_chart(flat_fields.value_counts().head(15))

    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Papers by method")
        flat_methods = flat_tags[flat_tags.str.startswith("method:")].str[len("method:"):]
        if len(flat_methods) > 0:
            st.bar_chart(flat_methods.value_counts())
        else:
            st.caption("No method tags in current filter.")

    st.subheader("Publication timeline")
    pub = pd.to_datetime(filt["published"], errors="coerce")
    timeline = pub.dt.to_period("W").value_counts().sort_index()
    timeline.index = timeline.index.astype(str)
    st.bar_chart(timeline)

with tab_digest:
    digest_path = REPO_ROOT / "digests" / "monthly_latest.md"
    if digest_path.exists():
        st.markdown(digest_path.read_text())
    else:
        st.info("No digest generated yet. Run `python -m econ_agent.cli digest monthly`.")
