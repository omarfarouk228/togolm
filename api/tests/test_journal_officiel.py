"""Splitting Journal officiel issues into one document per act."""

import uuid

from db import get_conn
from rag.indexation.ingestor import upsert_document
from rag.indexation.journal_officiel import act_url, split_acts
from rag.indexation.split_issues import split_pending_issues

BODY = "Article premier : texte de la loi. " * 30

ISSUE = (
    "71e Année N° 25 Bis NUMERO SPECIAL 09 avril 2026 JOURNAL OFFICIEL DE LA REPUBLIQUE "
    "TOGOLAISE SOMMAIRE LOIS 2026 24 mars-Loi n° 2026-004 portant répression du "
    "faux-monnayage...2 24 mars-Loi n° 2026-005 portant réglementation de la microfinance...6 "
    "Loi n° 20 26-004 du 24 mars 2026 portant répression du faux-monnayage "
    "L’Assemblée nationale a délibéré et adopté ; " + BODY + "Vu la loi n° 2008-005 du 30 mai "
    "2008 portant loi-cadre sur l’environnement ; " + BODY + "2 JOURNAL OFFICIEL DE LA REPUBLIQUE "
    "TOGOLAISE 09 avril 2026 DECRET N° 2026-033/PC du 19 février 2026 portant création de la "
    "direction de la protection LE PRESIDENT DU CONSEIL, Sur le rapport du ministre ; " + BODY
)


def test_acts_are_found_in_order_with_clean_numbers_and_dates():
    acts = split_acts(ISSUE)
    assert [(a.kind, a.number, a.date) for a in acts] == [
        ("Loi", "2026-004", "2026-03-24"),
        ("Décret", "2026-033/PC", "2026-02-19"),
    ]
    assert acts[0].title == "Loi n° 2026-004 du 24 mars 2026 portant répression du faux-monnayage"
    assert acts[1].title.startswith("Décret n° 2026-033/PC du 19 février 2026 portant création")


def test_table_of_contents_and_citations_do_not_start_acts():
    acts = split_acts(ISSUE)
    # The cited 2008 law stays inside the 2026 law's text.
    assert "Vu la loi n° 2008-005" in acts[0].text
    assert all("2008-005" not in a.number for a in acts)


def test_running_page_headers_are_removed():
    assert all(
        "JOURNAL OFFICIEL DE LA REPUBLIQUE TOGOLAISE 09 avril" not in a.text
        for a in split_acts(ISSUE)
    )


def test_act_urls_are_stable_anchors_on_the_issue():
    act = split_acts(ISSUE)[1]
    assert (
        act_url("https://jo.gouv.tg/JO_25.pdf", act)
        == "https://jo.gouv.tg/JO_25.pdf#decret-2026-033-pc"
    )


def test_issue_is_split_into_documents_and_hidden_from_search():
    issue_url = f"https://jo.gouv.tg/test-{uuid.uuid4()}.pdf"
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            issue_id = upsert_document(
                cur,
                {
                    "source": "jo.gouv.tg",
                    "url": issue_url,
                    "category": "legal",
                    "title": "Journal officiel test",
                    "raw_content": ISSUE * 10,
                    "clean_content": ISSUE * 10,
                },
            )
        conn.commit()

        result = split_pending_issues()
        assert result["issues_split"] >= 1

        with conn.cursor() as cur:
            cur.execute("SELECT status FROM documents WHERE id = %s", (issue_id,))
            assert cur.fetchone()[0] == "split"
            cur.execute(
                "SELECT title, published_at, (SELECT count(*) FROM chunks c WHERE c.document_id = d.id) "
                "FROM documents d WHERE url LIKE %s ORDER BY title",
                (issue_url + "#%",),
            )
            rows = cur.fetchall()
        assert [r[0][:12] for r in rows] == ["Décret n° 20", "Loi n° 2026-"]
        assert all(r[2] > 0 for r in rows)  # chunked, waiting for embeddings

        # Running again changes nothing.
        assert split_pending_issues()["issues_split"] == 0
    finally:
        conn.close()
