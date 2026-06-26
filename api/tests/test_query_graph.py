"""
Unit tests for the LangGraph RAG orchestration.
"""

from dataclasses import dataclass

from rag.orchestration.graph import run_query_graph


@dataclass(frozen=True)
class FakeChunk:
    title: str = "Creation d'entreprise"
    url: str = "https://service-public.gouv.tg/entreprise"
    source: str = "service-public.gouv.tg"
    category: str = "administrative"
    content: str = "Le RCCM est necessaire pour creer une SARL au Togo."
    score: float = 0.89


FAKE_CHUNK = FakeChunk()


def test_query_graph_enriches_before_retrieval():
    calls = {}

    def retriever(**kwargs):
        calls.update(kwargs)
        return [FAKE_CHUNK]

    result = run_query_graph(
        question="Comment creer une SARL au Togo ?",
        category=None,
        language="fr",
        history=[],
        is_trivially_off_topic=lambda _question: False,
        route_query=lambda _question: "on_topic",
        answer_without_corpus=lambda _question, _history: "off topic",
        rewrite_question=lambda question, _history: question,
        retriever=retriever,
        answer_builder=lambda _question, _chunks, history=None: "answer",
    )

    assert calls["category"] == "legal"
    assert "societe a responsabilite limitee" in calls["question"]
    assert result.answer == "answer"
    assert result.chunks == [FAKE_CHUNK]
    assert not result.is_off_topic


def test_query_graph_router_redirects_off_topic_without_retrieval():
    def retriever(**_kwargs):
        raise AssertionError("retriever should not be called")

    result = run_query_graph(
        question="Ecris une fonction Python qui trie une liste",
        category=None,
        language="fr",
        history=[],
        is_trivially_off_topic=lambda _question: False,
        route_query=lambda _question: "off_topic",
        answer_without_corpus=lambda _question, _history: "Posez-moi une question sur le Togo.",
        rewrite_question=lambda question, _history: question,
        retriever=retriever,
        answer_builder=lambda _question, _chunks, history=None: "answer",
    )

    assert result.answer == "Posez-moi une question sur le Togo."
    assert result.chunks == []
    assert result.is_off_topic


def test_query_graph_trivial_guard_skips_router_and_retrieval():
    def route_query(_question):
        raise AssertionError("router should not be called for trivial messages")

    def retriever(**_kwargs):
        raise AssertionError("retriever should not be called")

    result = run_query_graph(
        question="Bonjour",
        category=None,
        language="fr",
        history=[],
        is_trivially_off_topic=lambda _question: True,
        route_query=route_query,
        answer_without_corpus=lambda _question, _history: "Posez-moi une question sur le Togo.",
        rewrite_question=lambda question, _history: question,
        retriever=retriever,
        answer_builder=lambda _question, _chunks, history=None: "answer",
    )

    assert result.is_off_topic
    assert result.chunks == []


def test_query_graph_uses_history_rewriter():
    calls = {}

    def retriever(**kwargs):
        calls.update(kwargs)
        return [FAKE_CHUNK]

    result = run_query_graph(
        question="Et pour la SARL ?",
        category=None,
        language="fr",
        history=[{"role": "user", "content": "Je veux creer une entreprise"}],
        is_trivially_off_topic=lambda _question: False,
        route_query=lambda _question: "on_topic",
        answer_without_corpus=lambda _question, _history: "off topic",
        rewrite_question=lambda _question, _history: "Comment creer une SARL au Togo ?",
        retriever=retriever,
        answer_builder=lambda _question, _chunks, history=None: "answer",
    )

    assert calls["category"] == "legal"
    assert "rccm" in calls["question"]
    assert result.search_category == "legal"
