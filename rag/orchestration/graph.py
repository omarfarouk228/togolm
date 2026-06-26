"""
LangGraph orchestration for the non-streaming RAG query path.

The route keeps HTTP concerns such as status codes and background tasks. This
graph owns the RAG workflow: classify, rewrite/enrich, retrieve, then answer.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from rag.retrieval.enrichment import enrich_query

HistoryMessages = list[Any]


class QueryGraphState(TypedDict, total=False):
    question: str
    category: str | None
    language: str
    history: HistoryMessages
    is_off_topic: bool
    search_question: str
    search_category: str | None
    added_terms: tuple[str, ...]
    chunks: list[Any]
    answer: str


@dataclass(frozen=True)
class QueryGraphResult:
    answer: str
    chunks: list[Any]
    is_off_topic: bool
    search_question: str
    search_category: str | None
    added_terms: tuple[str, ...]


def build_query_graph(
    *,
    is_trivially_off_topic: Callable[[str], bool],
    route_query: Callable[[str], str],
    answer_without_corpus: Callable[[str, HistoryMessages], str],
    rewrite_question: Callable[[str, HistoryMessages], str],
    retriever: Callable[..., list[Any]],
    answer_builder: Callable[..., str],
    top_k: int = 5,
):
    """Build a compiled graph with injectable side-effecting dependencies.

    Routing is two-stage: a deterministic micro-guard handles the obvious cases
    for free, then an agentic LLM router classifies the rest.
    """

    def guard_node(state: QueryGraphState) -> dict:
        return {"is_off_topic": is_trivially_off_topic(state["question"])}

    def route_after_guard(state: QueryGraphState) -> Literal["off_topic", "route"]:
        return "off_topic" if state.get("is_off_topic") else "route"

    def router_node(state: QueryGraphState) -> dict:
        return {"is_off_topic": route_query(state["question"]) == "off_topic"}

    def route_after_router(state: QueryGraphState) -> Literal["off_topic", "enrich"]:
        return "off_topic" if state.get("is_off_topic") else "enrich"

    def off_topic_node(state: QueryGraphState) -> dict:
        history = state.get("history", [])
        return {
            "answer": answer_without_corpus(state["question"], history),
            "chunks": [],
            "search_question": state["question"],
            "search_category": state.get("category"),
            "added_terms": (),
        }

    def enrich_node(state: QueryGraphState) -> dict:
        history = state.get("history", [])
        search_question = state["question"]
        if history:
            search_question = rewrite_question(state["question"], history)

        enriched = enrich_query(search_question, category=state.get("category"))
        return {
            "search_question": enriched.search_query,
            "search_category": enriched.category,
            "added_terms": enriched.added_terms,
        }

    def retrieve_node(state: QueryGraphState) -> dict:
        chunks = retriever(
            question=state["search_question"],
            category=state.get("search_category"),
            top_k=top_k,
        )
        return {"chunks": chunks}

    def answer_node(state: QueryGraphState) -> dict:
        history_dicts = [_message_to_dict(message) for message in state.get("history", [])]
        answer = answer_builder(
            state["question"],
            state.get("chunks", []),
            history=history_dicts,
        )
        return {"answer": answer}

    builder = StateGraph(QueryGraphState)
    builder.add_node("guard", guard_node)
    builder.add_node("router", router_node)
    builder.add_node("off_topic", off_topic_node)
    builder.add_node("enrich", enrich_node)
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("answer", answer_node)
    builder.add_edge(START, "guard")
    builder.add_conditional_edges(
        "guard",
        route_after_guard,
        {"off_topic": "off_topic", "route": "router"},
    )
    builder.add_conditional_edges(
        "router",
        route_after_router,
        {"off_topic": "off_topic", "enrich": "enrich"},
    )
    builder.add_edge("off_topic", END)
    builder.add_edge("enrich", "retrieve")
    builder.add_edge("retrieve", "answer")
    builder.add_edge("answer", END)
    return builder.compile()


def run_query_graph(
    *,
    question: str,
    category: str | None,
    language: str,
    history: HistoryMessages,
    is_trivially_off_topic: Callable[[str], bool] | None = None,
    route_query: Callable[[str], str] | None = None,
    answer_without_corpus: Callable[[str, HistoryMessages], str] | None = None,
    rewrite_question: Callable[[str, HistoryMessages], str] | None = None,
    retriever: Callable[..., list[Any]] | None = None,
    answer_builder: Callable[..., str] | None = None,
    top_k: int = 5,
) -> QueryGraphResult:
    """Run the query graph and normalize the final state for HTTP handlers.

    Side-effecting dependencies default to the real implementations and can be
    overridden (e.g. in tests) by passing callables.
    """
    if None in (
        is_trivially_off_topic,
        route_query,
        answer_without_corpus,
        rewrite_question,
        answer_builder,
    ):
        from rag import generation
        from rag.orchestration import classification

        is_trivially_off_topic = is_trivially_off_topic or classification.is_trivially_off_topic
        route_query = route_query or generation.route_query
        answer_without_corpus = answer_without_corpus or generation.answer_without_corpus
        rewrite_question = rewrite_question or generation.rewrite_question_with_history
        answer_builder = answer_builder or generation.build_answer
    if retriever is None:
        from rag.retrieval import retrieve

        retriever = retriever or retrieve

    graph = build_query_graph(
        is_trivially_off_topic=is_trivially_off_topic,
        route_query=route_query,
        answer_without_corpus=answer_without_corpus,
        rewrite_question=rewrite_question,
        retriever=retriever,
        answer_builder=answer_builder,
        top_k=top_k,
    )
    final_state = graph.invoke(
        {
            "question": question,
            "category": category,
            "language": language,
            "history": history,
        }
    )
    return QueryGraphResult(
        answer=final_state.get("answer", ""),
        chunks=final_state.get("chunks", []),
        is_off_topic=bool(final_state.get("is_off_topic")),
        search_question=final_state.get("search_question", question),
        search_category=final_state.get("search_category"),
        added_terms=final_state.get("added_terms", ()),
    )


def _message_to_dict(message: Any) -> dict[str, str]:
    if isinstance(message, dict):
        return {
            "role": str(message.get("role", "")),
            "content": str(message.get("content", "")),
        }
    return {
        "role": str(getattr(message, "role", "")),
        "content": str(getattr(message, "content", "")),
    }
