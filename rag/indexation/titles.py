"""
Fix generic document titles at ingest time.

Special issues of the Journal officiel are PDFs whose first line is just
"NUMERO SPECIAL", so they were stored under that title. Short, generic titles
hid them from retrieval (which skips navigation pages) and from the sources
shown to users, although they carry 2025-2026 laws and decrees (anti-money
laundering, microfinance, composition of the government...). Their header
always names the issue and date, which makes a real title.
"""

import re

GENERIC_TITLES = {"numero special", "numéro spécial", "journal officiel"}

_JO_HEADER = re.compile(
    r"N°\s*(?P<num>\d+\s*(?:bis|ter)?)\s+NUM[EÉ]RO\s+SP[EÉ]CIAL\s+"
    r"(?P<date>\d{1,2}\s+[A-Za-zéèûÉÈÛ]+\s+\d{4})",
    re.IGNORECASE,
)


def journal_officiel_title(content: str) -> str | None:
    """'Journal officiel de la République togolaise n° 13 bis (numéro spécial)
    du 02 mars 2026' from a special issue's header, or None."""
    match = _JO_HEADER.search(content[:600])
    if not match:
        return None
    number = re.sub(r"\s+", " ", match.group("num")).strip().lower()
    date = re.sub(r"\s+", " ", match.group("date")).strip().lower()
    return f"Journal officiel de la République togolaise n° {number} (numéro spécial) du {date}"


def better_title(title: str | None, content: str) -> str:
    """Replace a generic title with one derived from the content, if possible."""
    clean = re.sub(r"\s+", " ", title or "").strip()
    if clean.lower() in GENERIC_TITLES:
        return journal_officiel_title(content) or clean
    return clean or (journal_officiel_title(content) or "")
