"""
Deterministic query enrichment for TogoLM retrieval.

The goal is to improve recall before embedding/vector search without requiring
an LLM call. Conversation-aware rewriting still lives in the router; this module
adds domain aliases, category inference, and whitespace/accent normalization.
"""

import re
import unicodedata
from dataclasses import dataclass

_SPACE_RE = re.compile(r"\s+")

_ALIASES: dict[str, tuple[str, ...]] = {
    "anpe": ("agence nationale pour l emploi", "emploi", "travail"),
    "bceao": ("banque centrale des etats de l afrique de l ouest", "uemoa", "monnaie"),
    "cnss": ("caisse nationale de securite sociale", "securite sociale", "cotisations"),
    "flooz": ("moov money", "mobile money", "paiement mobile"),
    "inam": ("institut national d assurance maladie", "assurance maladie", "sante"),
    "inseed": ("statistique", "demographie", "economie"),
    "ohada": ("droit des affaires", "societe commerciale", "acte uniforme"),
    "otr": ("office togolais des recettes", "impots", "taxes"),
    "rccm": ("registre du commerce et du credit mobilier", "creation entreprise"),
    "sarl": ("societe a responsabilite limitee", "rccm", "creation entreprise"),
    "uemoa": ("union economique et monetaire ouest africaine", "bceao"),
}

_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "administrative": (
        "acte de naissance",
        "carte nationale",
        "certificat",
        "demarche",
        "passeport",
        "service public",
    ),
    "agriculture": ("agriculture", "cacao", "cafe", "coton", "elevage", "mais"),
    "economy": (
        "bceao",
        "budget",
        "commerce",
        "economie",
        "entreprise",
        "impot",
        "impots",
        "investissement",
        "port autonome",
        "taxe",
        "taxes",
        "uemoa",
    ),
    "education": ("bac", "baccalaureat", "campus", "diplome", "ecole", "education", "universite"),
    "health": ("assurance maladie", "hopital", "inam", "maladie", "sante", "vaccin"),
    "legal": (
        "acte uniforme",
        "code du travail",
        "constitution",
        "contrat",
        "justice",
        "loi",
        "ohada",
        "rccm",
        "sarl",
        "tribunal",
    ),
    "politics": (
        "assemblee nationale",
        "gouvernement",
        "ministre",
        "presidence",
        "president",
        "republique",
    ),
    "press": ("actualite", "article", "journal", "presse"),
}


@dataclass(frozen=True)
class EnrichedQuery:
    original: str
    normalized: str
    search_query: str
    category: str | None
    added_terms: tuple[str, ...]


def normalize_query(text: str) -> str:
    """Return a lowercase ASCII-ish query with collapsed whitespace."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return _SPACE_RE.sub(" ", ascii_text.lower()).strip()


def enrich_query(question: str, category: str | None = None) -> EnrichedQuery:
    """Add deterministic Togo-domain aliases and infer category when absent."""
    normalized = normalize_query(question)
    added_terms = _match_alias_terms(normalized)
    enriched_text = _SPACE_RE.sub(" ", " ".join((normalized, *added_terms))).strip()
    inferred_category = category or infer_category(normalized, added_terms)

    return EnrichedQuery(
        original=question,
        normalized=normalized,
        search_query=enriched_text or question,
        category=inferred_category,
        added_terms=added_terms,
    )


def infer_category(normalized_question: str, added_terms: tuple[str, ...] = ()) -> str | None:
    """Infer the most likely corpus category from deterministic keyword scores."""
    haystack = " ".join((normalized_question, *added_terms))
    best_category: str | None = None
    best_score = 0

    for category, keywords in _CATEGORY_KEYWORDS.items():
        score = sum(1 for keyword in keywords if _contains_term(haystack, keyword))
        if score > best_score:
            best_category = category
            best_score = score

    return best_category if best_score > 0 else None


def _match_alias_terms(normalized_question: str) -> tuple[str, ...]:
    terms: list[str] = []
    seen: set[str] = set()

    for trigger, expansions in _ALIASES.items():
        if not _contains_term(normalized_question, trigger):
            continue
        for term in expansions:
            normalized_term = normalize_query(term)
            if normalized_term in seen or _contains_term(normalized_question, normalized_term):
                continue
            terms.append(normalized_term)
            seen.add(normalized_term)

    return tuple(terms)


def _contains_term(text: str, term: str) -> bool:
    normalized_term = normalize_query(term)
    if " " in normalized_term:
        return normalized_term in text
    return bool(re.search(rf"\b{re.escape(normalized_term)}\b", text))
