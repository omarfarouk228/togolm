"""Ministry of Health spider: WordPress REST API posts and documentation PDFs."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Scrapy project modules are imported as "scrapers.*" from the corpus/ dir.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "corpus"))

from scrapers.spiders.sante_spider import API, SanteSpider  # noqa: E402
from scrapy.http import Request, Response, TextResponse  # noqa: E402

BODY = "<p>" + "Le ministère de la santé renforce la couverture sanitaire. " * 10 + "</p>"


def _json_response(url: str, payload, total_pages: int = 1) -> TextResponse:
    return TextResponse(
        url=url,
        body=json.dumps(payload).encode(),
        encoding="utf-8",
        headers={"X-WP-TotalPages": str(total_pages)},
        request=Request(url),
    )


@pytest.fixture
def spider() -> SanteSpider:
    s = SanteSpider()
    s.category_slugs = {"bk.sante.gouv.tg": {9: "avis-et-annonces", 1: "non-classe"}}
    return s


def test_posts_become_health_documents_under_their_public_url(spider):
    url = f"{API}/posts?page=1"
    post = {
        "id": 1,
        "slug": "campagne-de-vaccination",
        "date": "2026-10-13T15:47:43",
        "title": {"rendered": "Campagne de vaccination&nbsp;: lancement"},
        "content": {"rendered": BODY},
        "categories": [1, 9],
    }
    out = list(spider.parse_posts(_json_response(url, [post], total_pages=2), page=1))

    doc, next_page = out
    assert doc["url"] == "https://sante-assurances.gouv.tg/actualites/campagne-de-vaccination"
    assert doc["category"] == "health"
    assert doc["subcategory"] == "avis"
    assert doc["published_at"] == "2026-10-13"
    assert doc["title"] == "Campagne de vaccination\xa0: lancement"
    assert "page=2" in next_page.url


def test_documentation_resolves_attachments_then_downloads_pdfs_only(spider):
    entry = {"id": 10, "date": "2026-07-15T10:53:08", "title": {"rendered": "Guide"}}
    listing = [{**entry, "acf": {"document": 55}}, {"id": 11, "acf": False}]
    (media_req,) = spider.parse_documentation(_json_response(f"{API}/documentation", listing), 1)
    assert "include=55" in media_req.url

    media = [
        {"id": 55, "mime_type": "application/pdf", "source_url": "https://bk.sante.gouv.tg/g.pdf"},
        {"id": 56, "mime_type": "image/png", "source_url": "https://bk.sante.gouv.tg/x.png"},
    ]
    entries = media_req.cb_kwargs["entries"]
    pdf_reqs = list(spider.parse_media(_json_response(media_req.url, media), entries=entries))
    assert [r.url for r in pdf_reqs] == ["https://bk.sante.gouv.tg/g.pdf"]
    assert pdf_reqs[0].cb_kwargs["entry"]["id"] == 10


def test_pdf_is_stored_under_its_own_url_with_entry_metadata(spider):
    entry = {
        "id": 10,
        "date": "2026-07-15T10:53:08",
        "title": {"rendered": "Guide d&rsquo;antibiothérapie enfant au Togo"},
    }
    url = "https://bk.sante.gouv.tg/wp-content/uploads/2026/07/guide.pdf"
    response = Response(url=url, body=b"%PDF-1.4", request=Request(url))
    text = "Antibiotiques recommandés en pédiatrie. " * 50

    with patch("scrapers.spiders.wp_platform._extract_pdf_text", return_value=text):
        (doc,) = spider.parse_pdf(response, entry=entry)

    assert doc["url"] == url
    assert doc["title"] == "Guide d’antibiothérapie enfant au Togo"
    assert doc["category"] == "health"
    assert doc["subcategory"] == "guide"
    assert doc["published_at"] == "2026-07-15"


def test_pdf_without_extractable_text_is_skipped(spider):
    url = "https://bk.sante.gouv.tg/scan.pdf"
    response = Response(url=url, body=b"%PDF-1.4", request=Request(url))
    with patch("scrapers.spiders.wp_platform._extract_pdf_text", return_value=""):
        assert list(spider.parse_pdf(response, entry={"id": 1, "title": {}})) == []


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("AMI_Recrutement de consultant pour l’elaboration plan strategique", "avis"),
        ("OOAS-Recrute-Traducteur (Anglais)", "avis"),
        ("ARRETE FIXANT LES PRIX DE CESSION DES PRODUITS SANGUINS", "texte"),
        ("Annuaire__Statistique_Sanitaire_Togo_2020", "rapport"),
        ("PLAN NATIONAL DE DEVELOPPEMENT SANITAIRE (PNDS) 2023-2027", "politique"),
        ("WSIS Forum 2022", "document"),
    ],
)
def test_document_subcategory_from_title(title, expected):
    assert SanteSpider._document_subcategory(title) == expected
