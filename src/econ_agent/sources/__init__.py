"""Source fetchers. Each module exposes a `fetch(...)` returning list[Paper]."""

from . import arxiv, journals, nber, openalex_ssrn, repec_nep

ALL_SOURCES = {
    "nber": nber,
    "arxiv": arxiv,
    "repec_nep": repec_nep,
    "openalex_ssrn": openalex_ssrn,
    "journals": journals,
}
