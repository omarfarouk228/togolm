"""
Split an issue of the Journal officiel into its individual acts.

Special issues of the Journal officiel arrive as one PDF holding dozens of
laws, decrees, orders and decisions (up to ~650 chunks). As a single document
an act is hard to find (a question about the 2026 legal interest rate never
reached the decree fixing it, buried among 400 chunks) and impossible to
cite precisely. Each act becomes its own document instead.

The text is flattened (no line breaks), so acts are found by their heading,
"Loi n° 2026-004 du 24 mars 2026 portant ..." or "DECRET N° 2026-033/PC du
19 février 2026 ...", and kept only when an enactment formula follows ("a
délibéré et adopté", "Le Président du Conseil", "DECRETE"...). That rules
out the table of contents (whose entries have no "du <date>") and citations
inside other acts ("Vu la loi n° 2008-005 du 30 mai 2008", lowercase and
never followed by an enactment formula).
"""

import re
import unicodedata
from dataclasses import dataclass

MONTHS = {
    "janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12, "décembre": 12,
}  # fmt: skip

KIND_LABELS = {
    "loi": "Loi",
    "ordonnance": "Ordonnance",
    "decret": "Décret",
    "arrete": "Arrêté",
    "arrete interministeriel": "Arrêté interministériel",
    "decision": "Décision",
}

# Heading: kind starting with a capital letter (citations are lowercase),
# number, then "du <date>".
_HEADING = re.compile(
    r"(?P<kind>LOI|Loi|ORDONNANCE|Ordonnance|D[EÉ]CRET|D[ée]cret"
    r"|ARR[EÊ]T[EÉ](?:\s+INTERMINIST[EÉ]RIEL)?|Arr[êe]t[ée](?:\s+interminist[ée]riel)?"
    r"|D[EÉ]CISION|D[ée]cision)"
    r"\s+[Nn][°o]\s*(?P<num>[0-9][0-9 ]*[0-9]?(?:\s*[-/]\s*[0-9A-Za-z]+){1,3}(?:\s*bis)?)"
    r"\s+du\s+(?P<date>\d{1,2}(?:er)?\s+[A-Za-zéèûÉÈÛ]+\s+\d{4})"
)
_ENACTMENT = re.compile(
    r"a\s+d[ée]lib[ée]r[ée]\s+et\s+adopt[ée]|Le\s+Pr[ée]sident\s+du\s+Conseil"
    r"|LE\s+PR[EÉ]SIDENT\s+DU\s+CONSEIL|Le\s+Pr[ée]sident\s+de\s+la\s+R[ée]publique"
    r"|LE\s+PR[EÉ]SIDENT\s+DE\s+LA\s+R[EÉ]PUBLIQUE|D[EÉ]CR[EÈ]TE\s*:|D[ée]cr[èe]te\s*:"
    r"|ARR[EÊ]TE\s*:|Arr[êe]te\s*:|D[EÉ]CIDE\s*:|D[ée]cide\s*:"
    r"|Le\s+Ministre|LE\s+MINISTRE|Le\s+Conseil\s+des\s+ministres\s+entendu"
)
# What ends an act's title in its heading: the enactment formula, or debris
# the PDF extraction glued after it (list items "12. Ministre ...", a table of
# contents entry "07 octobre- Arrêté ...", closing formulas).
_TITLE_END = re.compile(
    r"\s(?:L[’']Assembl[ée]e\s+nationale|Le\s+Pr[ée]sident|LE\s+PR[EÉ]SIDENT|Le\s+Ministre"
    r"|LE\s+MINISTRE|Vu\s|VU\s|Sur\s+(?:le\s+)?rapport|Le\s+Conseil\s+des\s+ministres"
    r"|\d{1,3}\s*[.)]\s|\d{1,2}(?:er)?\s+[a-zéû]+\s*-\s*[A-ZÉ]|Fait\s+[àa]\s|[A-Z]{4,}\s+[A-Z]{4,}"
    r"|d[ée]cret\s+qui\s+sera|enregistr[ée]\s+et\s+publi[ée])"
)
# Running page header repeated inside the text: "JOURNAL OFFICIEL DE LA
# REPUBLIQUE TOGOLAISE 09 avril 2026" (sometimes with a page number first).
_PAGE_HEADER = re.compile(
    r"(?:\b\d{1,3}\s+)?JOURNAL\s+OFFICIEL\s+DE\s+LA\s+REPUBLIQUE\s+TOGOLAISE\s+"
    r"\d{1,2}(?:er)?\s+[A-Za-zéèûÉÈÛ]+\s+\d{4}(?:\s+\d{1,3}\b)?"
)

MIN_ACT_CHARS = 200
ENACTMENT_WINDOW = 700


@dataclass
class Act:
    kind: str  # "Loi", "Décret"...
    number: str  # "2026-004", "2026-033/PC"
    date: str | None  # ISO date of signature, when parsable
    title: str  # "Loi n° 2026-004 du 24 mars 2026 portant ..."
    text: str


def _fold(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    ).lower()


def _iso_date(raw: str) -> str | None:
    m = re.match(r"(\d{1,2})(?:er)?\s+(\S+)\s+(\d{4})", raw.strip())
    if not m:
        return None
    month = MONTHS.get(m.group(2).lower()) or MONTHS.get(_fold(m.group(2)))
    if not month:
        return None
    return f"{int(m.group(3)):04d}-{month:02d}-{int(m.group(1)):02d}"


def _clean_number(raw: str) -> str:
    # OCR splits digits ("20 26-004"); keep letters like "/PC".
    num = re.sub(r"(?<=\d)\s+(?=\d)", "", raw.strip())
    num = re.sub(r"\s*([-/])\s*", r"\1", num)
    return re.sub(r"\s+", " ", num)


def split_acts(content: str) -> list[Act]:
    """The acts contained in a Journal officiel issue, in order."""
    text = _PAGE_HEADER.sub(" ", content)
    text = re.sub(r"\s+", " ", text)

    starts = []
    for m in _HEADING.finditer(text):
        window = text[m.end() : m.end() + ENACTMENT_WINDOW]
        if _ENACTMENT.search(window):
            starts.append(m)

    acts: list[Act] = []
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        body = text[m.start() : end].strip()
        if len(body) < MIN_ACT_CHARS:
            continue
        kind = KIND_LABELS.get(_fold(re.sub(r"\s+", " ", m.group("kind"))), m.group("kind"))
        number = _clean_number(m.group("num"))
        date_raw = re.sub(r"\s+", " ", m.group("date")).strip()
        heading_rest = body[m.end() - m.start() :]
        stop = _TITLE_END.search(heading_rest)
        subject = heading_rest[: stop.start() if stop else 250].strip(" ,;:.")
        subject = subject[:250].rsplit(" ", 1)[0] if len(subject) > 250 else subject
        # A lone capitalised word glued from the next heading ("... massive LOI").
        subject = re.sub(r"\s+[A-ZÉÈ]{2,}$", "", subject)
        title = f"{kind} n° {number} du {date_raw.lower()}" + (f" {subject}" if subject else "")
        acts.append(Act(kind=kind, number=number, date=_iso_date(date_raw), title=title, text=body))
    return acts


def act_url(issue_url: str, act: Act) -> str:
    """Stable URL for an act: the issue's URL plus an anchor naming the act."""
    slug = re.sub(r"[^a-z0-9]+", "-", _fold(f"{act.kind} {act.number}")).strip("-")
    return f"{issue_url.split('#', 1)[0]}#{slug}"
