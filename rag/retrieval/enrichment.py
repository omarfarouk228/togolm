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

_ENUMERATION_RE = re.compile(
    r"\b(liste|listes|composition|membres|tous\s+les|toutes\s+les|"
    r"qui\s+sont|quels\s+sont|quelles\s+sont|ensemble\s+des|combien\s+de)\b",
    re.IGNORECASE,
)

_IDENTITY_RE = re.compile(
    r"\b(qui\s+est|qui\s+dirige|qui\s+preside|qui\s+occupe|qui\s+a\s+succede|"
    r"qui\s+remplace|qui\s+incarne|actuel(?:le)?\s+president|actuellement\s+president)\b",
    re.IGNORECASE,
)

# Normalized (accent-stripped) trigger -> the accented phrase as it actually
# appears in document titles, used for an ILIKE title-match boost. Kept
# separate from _ALIASES: these aren't search-term expansions, they identify
# a specific office so the retriever can fetch the most recently published
# document naming its holder (see is_identity_query).
_OFFICE_PHRASES: dict[str, str] = {
    "president de la republique": "président de la République",
    "president du conseil": "président du Conseil",
    "premier ministre": "Premier ministre",
    "president de l assemblee nationale": "président de l'Assemblée nationale",
    "president du senat": "président du Sénat",
}

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
    "culinary": (
        "ayimolou",
        "cuisine togolaise",
        "fufu",
        "gboma",
        "plat togolais",
        "recette",
        "sauce",
        "wagashi",
    ),
    "economy": (
        "bceao",
        "budget",
        "commerce",
        "demographie",
        "developpement",
        "economie",
        "entreprise",
        "entreprises",
        "impot",
        "impots",
        "investissement",
        "pib",
        "pme",
        "port autonome",
        "population",
        "recensement",
        "rgph",
        "secteur prive",
        "statistique",
        "statistiques",
        "taxe",
        "taxes",
        "uemoa",
    ),
    "education": (
        "bac",
        "baccalaureat",
        "campus",
        "diplome",
        "ecole",
        "ecoles",
        "education",
        "educatif",
        "eleve",
        "eleves",
        "enseignement",
        "etudiant",
        "etudiants",
        "universite",
        "universites",
    ),
    "health": ("assurance maladie", "hopital", "inam", "maladie", "sante", "vaccin"),
    "legal": (
        "acte uniforme",
        "code du travail",
        "constitution",
        "contrat",
        "justice",
        "loi",
        "lois",
        "ohada",
        "rccm",
        "sarl",
        "tribunal",
    ),
    "politics": (
        "assemblee nationale",
        "election",
        "elections",
        "gouvernement",
        "ministre",
        "ministres",
        "parti politique",
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


def is_enumeration_query(text: str) -> bool:
    """True when a question asks for a list/roster/full set of items rather
    than a single fact (e.g. "liste des ministres du gouvernement togolais").

    Such answers are often split across many small chunks of the same source
    document (a 27-name cabinet list, a full list of universities...) — the
    retriever needs to know to keep several chunks from that one document
    instead of applying its usual one-chunk-per-document diversification.
    """
    return bool(_ENUMERATION_RE.search(text))


def is_identity_query(text: str) -> bool:
    """True for "who currently holds office X" questions (e.g. "qui est
    l'actuel président de la République ?").

    Pure embedding similarity is unreliable here: a short, name-specific
    article ("X élu président de la République") can rank hundreds of
    positions below generic commentary that happens to repeat the same
    office words many times without ever naming a holder. See
    detect_office_phrase for the companion title-match boost.
    """
    return bool(_IDENTITY_RE.search(text))


def detect_office_phrase(normalized_question: str) -> str | None:
    """Return the accented title-search phrase for the office named in the
    (already normalized/ascii) question, if any of the known ones matches."""
    for trigger, phrase in _OFFICE_PHRASES.items():
        if _contains_term(normalized_question, trigger):
            return phrase
    return None


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
