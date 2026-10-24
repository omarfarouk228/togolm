"""
Administrative procedures as structured cards ("fiches démarches").

Two sources describe procedures field by field: service-public.gouv.tg
("Description: ... | Pièces à fournir: ... | Coût de la procédure: ...") and
investirautogo.tg, the eRegulations portal (lines "Étapes : 1. ... ; 2. ...",
"Coût : ...", written by corpus/scrapers/spiders/eregulations_spider.py).
Their stored text is parsed back into fields, so the web and bot clients can
show the exact documents, cost and time of a procedure next to the generated
answer, which on 2026-10-24 turned "10 000 FCFA" into "10 000 to 15 000 FCFA".
"""

import re

PROCEDURE_SOURCES = ("service-public.gouv.tg", "investirautogo.tg")

# Field -> label patterns (first match wins), both sources' wordings.
FIELDS = [
    ("summary", r"description"),
    ("who", r"(identification des )?personnes|personnes concern"),
    ("conditions", r"conditions"),
    ("steps", r"[ée]tapes"),
    ("documents", r"pi[èe]ces"),
    ("office", r"o[ùu] aller|contact"),
    ("cost", r"co[ûu]t"),
    ("duration", r"d[ée]lai|dur[ée]e totale"),
    ("validity", r"dur[ée]e de validit"),
    ("result", r"ce que vous obtenez"),
    ("legal", r"base l[ée]gale"),
]
LIST_FIELDS = ("steps", "documents")
EMPTY = {"n/a", "na", "-", "aucun", "aucune", "néant", "neant", ""}
LABEL_RE = re.compile(r"^\s*([^:]{3,90}?)\s?:\s*(.*)$", re.DOTALL)
# eRegulations cards are stored as one paragraph once cleaned at ingest:
# split them before each of their labels.
EREG_LABELS = re.compile(
    r"(?<=[.;])\s+(?=(?:Étapes|Où aller|Pièces à fournir|Coût|Durée totale|"
    r"Ce que vous obtenez|Base légale|Informations complémentaires)\s?:)"
)


def _field(label: str) -> str | None:
    label = label.strip().lower()
    for name, pattern in FIELDS:
        if name == "duration" and re.search(r"validit", label):
            continue
        if re.match(pattern, label):
            return name
    return None


def _clean(label: str, value: str) -> str:
    value = " ".join(value.split())
    # service-public repeats the label at the start of some values
    # ("Conditions: Conditions La souscription..."): drop the echo.
    first = label.split()[0]
    if value.lower().startswith(first.lower() + " "):
        value = value[len(first) + 1 :]
    return value.strip(" .;")


def _items(value: str) -> list[str]:
    """'1. A ; 2. B' or 'A ; B' as ['A', 'B']."""
    parts = re.split(r"\s*;\s*|\s+(?=\d{1,2}\.\s)", value)
    items = [re.sub(r"^\d{1,2}\.\s*", "", p).strip(" .") for p in parts]
    return [i for i in items if i]


def parse_procedure(text: str) -> dict:
    """Fields of a procedure from its stored text (unknown fields are omitted)."""
    sections = [
        part
        for section in re.split(r"\s+\|\s+|\n+", text or "")
        for part in EREG_LABELS.split(section)
    ]
    card: dict = {}
    for section in sections:
        match = LABEL_RE.match(section)
        if not match:
            continue
        label, value = match.groups()
        name = _field(label)
        if not name or name in card:
            continue
        value = _clean(label, value)
        if value.lower() in EMPTY or value.lower().startswith("voir la description"):
            continue
        card[name] = _items(value) if name in LIST_FIELDS else value
    return card


def procedure_card(doc_id: str, title: str, url: str, source: str, text: str) -> dict | None:
    """The card shown to users, or None when the text has no procedure fields."""
    fields = parse_procedure(text)
    if not (fields.get("steps") or fields.get("documents") or fields.get("cost")):
        return None
    return {"id": doc_id, "title": title, "url": url, "source": source, **fields}
