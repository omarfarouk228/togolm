"""
Unit tests for deterministic query enrichment.
"""

from rag.retrieval.enrichment import (
    detect_office_phrase,
    enrich_query,
    infer_category,
    is_enumeration_query,
    is_identity_query,
    normalize_query,
)


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


def test_is_enumeration_query_detects_list_intent():
    assert is_enumeration_query("liste des ministres du gouvernement togolais")
    assert is_enumeration_query("Quels sont les membres du gouvernement ?")
    assert is_enumeration_query("Composition du gouvernement togolais")


def test_is_enumeration_query_false_for_single_fact_question():
    assert not is_enumeration_query("Qui est le président du Togo ?")
    assert not is_enumeration_query("Quel est le budget de l'Etat togolais ?")


# ---------------------------------------------------------------------------
# Category coverage — regression guard for the most frequent production
# queries that used to fall through to category=None (audit, 2026-07-19).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Identity queries — "qui est l'actuel président de la République ?" (found
# live, 2026-07-20): pure vector similarity ranked the correct officeholder
# article hundreds of positions below generic commentary. detect_office_phrase
# drives a title-match boost in retrieval for this query shape.
# ---------------------------------------------------------------------------


def test_is_identity_query_detects_who_holds_office():
    assert is_identity_query(normalize_query("qui est l'actuel président de la République ?"))
    assert is_identity_query(normalize_query("qui dirige le Togo actuellement ?"))
    assert is_identity_query(normalize_query("qui préside le Conseil des ministres ?"))


def test_is_identity_query_false_for_unrelated_question():
    assert not is_identity_query(normalize_query("liste des ministres du gouvernement togolais"))
    assert not is_identity_query(normalize_query("quel est le budget de l'Etat togolais ?"))


def test_detect_office_phrase_matches_known_offices():
    assert (
        detect_office_phrase(normalize_query("qui est l'actuel président de la République ?"))
        == "président de la République"
    )
    assert (
        detect_office_phrase(normalize_query("qui est le président du Conseil ?"))
        == "président du Conseil"
    )


def test_detect_office_phrase_none_for_unknown_office():
    assert detect_office_phrase(normalize_query("qui est le maire de Lomé ?")) is None


def test_infer_category_covers_top_production_queries():
    assert (
        infer_category(
            normalize_query(
                "Quels sont les résultats du dernier recensement général de la "
                "population du Togo (RGPH-5) ?"
            )
        )
        == "economy"
    )
    assert infer_category(normalize_query("Comment fonctionne le système éducatif au Togo ?")) == (
        "education"
    )
    assert (
        infer_category(
            normalize_query(
                "Comment le Togo soutient-il le développement des PME et le secteur privé ?"
            )
        )
        == "economy"
    )
    assert infer_category(normalize_query("liste des ministres du gouvernement togolais")) == (
        "politics"
    )
