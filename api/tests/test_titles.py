"""Generic titles, and which documents retrieval treats as navigation pages."""

import pytest

from rag.indexation.titles import better_title, journal_officiel_title
from rag.retrieval.search import NAVIGATION_TITLES, USABLE_TITLE_SQL

HEADER = (
    "71e Année N° 13 Bis NUMERO SPECIAL 02 mars 2026 JOURNAL OFFICIEL DE LA "
    "REPUBLIQUE TOGOLAISE PARAISSANT LE 1er ET LE 16 DE CHAQUE MOIS A LOME"
)


def test_special_issue_title_comes_from_its_header():
    assert journal_officiel_title(HEADER) == (
        "Journal officiel de la République togolaise n° 13 bis (numéro spécial) du 02 mars 2026"
    )


@pytest.mark.parametrize("generic", ["NUMERO SPECIAL", " Numéro spécial ", "JOURNAL OFFICIEL"])
def test_generic_titles_are_replaced(generic):
    assert better_title(generic, HEADER).startswith(
        "Journal officiel de la République togolaise n° 13 bis"
    )


def test_real_titles_are_kept_and_unparsable_generic_ones_left_alone():
    assert better_title("Loi de finances 2026", HEADER) == "Loi de finances 2026"
    assert better_title("NUMERO SPECIAL", "pas d'en-tête") == "NUMERO SPECIAL"


def test_short_real_titles_are_no_longer_filtered_out():
    # The old rule (title longer than 15 characters) hid 1,025 Wikipedia
    # articles such as "Abass Kaboua" and the Journal officiel special issues.
    assert "length(trim(coalesce(d.title, ''))) > 15" not in USABLE_TITLE_SQL
    assert "abass kaboua" not in NAVIGATION_TITLES


def test_navigation_pages_stay_filtered_out():
    assert "'our shop'" in USABLE_TITLE_SQL
    assert ":\\s*$" in USABLE_TITLE_SQL  # "Jour :", "Category:"
