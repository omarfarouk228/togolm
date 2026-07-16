"""Generation stage: LangChain LCEL chains over Gemini + versioned prompts."""

from rag.generation.chains import (
    answer_from_image,
    answer_without_corpus,
    build_answer,
    build_answer_with_image,
    describe_image_question,
    extractive_answer,
    rewrite_question_with_history,
    route_query,
    stream_answer,
    stream_answer_from_image,
    stream_answer_with_image,
    stream_extractive,
    stream_without_corpus,
)

__all__ = [
    "answer_from_image",
    "answer_without_corpus",
    "build_answer",
    "build_answer_with_image",
    "describe_image_question",
    "extractive_answer",
    "rewrite_question_with_history",
    "route_query",
    "stream_answer",
    "stream_answer_from_image",
    "stream_answer_with_image",
    "stream_extractive",
    "stream_without_corpus",
]
