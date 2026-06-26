"""
Unit tests for deterministic query enrichment.
"""

from rag.retrieval.enrichment import enrich_query, infer_category, normalize_query


def test_normalize_query_strips_accents_and_collapses_spaces():
    assert normalize_query("  Creation   d'entreprise a Lome  ") == "creation d'entreprise a lome"


def test_enrich_query_expands_otr_alias():
    result = enrich_query("Quels sont les impots OTR pour une entreprise ?")

    assert "office togolais des recettes" in result.search_query
    assert "taxes" in result.search_query
    assert result.category == "economy"


def test_enrich_query_expands_sarl_alias_and_infers_legal_category():
    result = enrich_query("Comment creer une SARL au Togo ?")

    assert "societe a responsabilite limitee" in result.search_query
    assert "rccm" in result.search_query
    assert result.category == "legal"


def test_explicit_category_is_preserved():
    result = enrich_query("Budget de l'Etat togolais", category="press")

    assert result.category == "press"


def test_infer_category_returns_none_without_match():
    assert infer_category("question generale sans mot cle") is None
