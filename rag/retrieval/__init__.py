"""Retrieval stage: query enrichment + vector/full-text search."""

from rag.retrieval.enrichment import (
    EnrichedQuery,
    enrich_query,
    infer_category,
    normalize_query,
)
from rag.retrieval.search import RetrievedChunk, retrieve

__all__ = [
    "EnrichedQuery",
    "RetrievedChunk",
    "enrich_query",
    "infer_category",
    "normalize_query",
    "retrieve",
]
