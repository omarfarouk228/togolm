"""
Deterministic micro-guard for trivially off-topic messages.

Catches only the obvious, zero-ambiguity cases (greetings, bare math, very short
messages) so they skip both retrieval and the LLM router. Everything else is left
to the agentic router (``rag.generation.route_query``), which decides intent with
a structured LLM call inside the graph.
"""

import re

_GREETINGS_RE = re.compile(
    r"^\s*(hello|hi|hey|bonjour|salut|bonsoir|bonne\s*nuit|good\s*morning|good\s*evening|"
    r"coucou|allo|allô|yo|ok|okay|merci|thanks|thank\s*you|au\s*revoir|bye|bonne\s*journée|"
    r"bonne\s*soirée|slt|bjr|svp|s\'il\s*vous\s*plaît)\s*[!?.,]?\s*$",
    re.IGNORECASE,
)
_MATH_RE = re.compile(r"^\s*[\d\s\+\-\*\/\^\(\)=.,]+\s*$")


def is_trivially_off_topic(question: str, has_history: bool = False) -> bool:
    """Return True only for obvious non-domain messages: greetings, bare math,
    or messages too short to carry a real question (< 3 words).

    The short-message rule only applies with no prior conversation: inside an
    ongoing exchange, a short reply ("Explique", "Et Ewe ?") is almost always
    a follow-up on the previous on-topic turn, not a standalone non-sequitur,
    so it's left to the agentic router (which does see history) instead of
    being trivially rejected here.
    """
    q = question.strip()
    if _GREETINGS_RE.match(q):
        return True
    if _MATH_RE.match(q):
        return True
    if not has_history and len(q.split()) < 3:
        return True
    return False
