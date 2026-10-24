"""Ministries on the government's React platform, read from bk.*.gouv.tg."""

import json
import sys
from pathlib import Path

# Scrapy project modules are imported as "scrapers.*" from the corpus/ dir.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "corpus"))

from scrapers.spiders.gouv_platform_spider import GouvPlatformSpider  # noqa: E402
from scrapy.http import Request, TextResponse  # noqa: E402

BODY = "<p>" + "Le ministère poursuit la modernisation de ses services publics. " * 10 + "</p>"


def _json(url: str, payload, status: int = 200, total_pages: int = 1) -> TextResponse:
    return TextResponse(
        url=url,
        body=json.dumps(payload).encode(),
        encoding="utf-8",
        status=status,
        headers={"X-WP-TotalPages": str(total_pages)},
        request=Request(url),
    )


def test_each_site_gets_its_own_source_category_and_public_url():
    spider = GouvPlatformSpider()
    categories = _json(
        "https://bk.numerique.gouv.tg/wp-json/wp/v2/categories?per_page=100",
        [{"id": 4, "slug": "discours"}],
    )
    posts_req, doc_req = list(spider.parse(categories))
    assert posts_req.url.startswith("https://bk.numerique.gouv.tg/wp-json/wp/v2/posts")
    assert doc_req.url.startswith("https://bk.numerique.gouv.tg/wp-json/wp/v2/documentation")

    post = {
        "id": 1,
        "slug": "backhaul-savanes",
        "date": "2026-10-15T11:52:42",
        "title": {"rendered": "Connectivité à large bande dans les Savanes"},
        "content": {"rendered": BODY},
        "categories": [4],
    }
    (doc,) = list(spider.parse_posts(_json(posts_req.url, [post]), page=1))
    assert doc["url"] == "https://numerique.gouv.tg/actualites/backhaul-savanes"
    assert doc["source"] == "numerique.gouv.tg"
    assert doc["category"] == "economy"
    assert doc["subcategory"] == "discours"
    assert doc["published_at"] == "2026-10-15"

    other = _json("https://bk.defense.gouv.tg/wp-json/wp/v2/posts?page=1", [post])
    (doc,) = list(spider.parse_posts(other, page=1))
    assert doc["source"] == "defense.gouv.tg"
    assert doc["category"] == "politics"
    assert doc["subcategory"] == "actualite"  # defense categories not loaded


def test_site_filter_and_missing_documentation_section():
    spider = GouvPlatformSpider(sites="eau.gouv.tg")
    assert [s["source"] for s in spider.sites] == ["eau.gouv.tg"]
    missing = _json("https://bk.eau.gouv.tg/wp-json/wp/v2/documentation", {"code": "x"}, 404)
    assert list(spider.parse_documentation(missing, 1)) == []


def test_atop_uses_post_link_real_dates_and_topic_subcategories():
    from scrapers.spiders.atop_spider import AtopSpider

    spider = AtopSpider()
    categories = _json(
        "https://atop.tg/wp-json/wp/v2/categories?per_page=100",
        [
            {"id": 1, "slug": "a-la-une"},
            {"id": 133, "slug": "derniere-minute"},
            {"id": 98, "slug": "sante"},
        ],
    )
    requests = list(spider.parse(categories))
    assert [r.url.split("?")[0] for r in requests] == ["https://atop.tg/wp-json/wp/v2/posts"]

    post = {
        "id": 136964,
        "slug": "golfe-6-bureau-du-citoyen",
        "link": "https://atop.tg/golfe-6-bureau-du-citoyen/",
        "date": "2026-10-24T15:06:08",
        "title": {"rendered": "La commune Golfe 6 installe son bureau du citoyen"},
        "content": {"rendered": BODY},
        "categories": [1, 133, 98],
    }
    broken = {**post, "id": 1, "link": "https://atop.tg/vieux/", "date": "1970-01-01T00:00:00"}
    doc, old = list(spider.parse_posts(_json(requests[0].url, [post, broken]), page=1))
    assert doc["url"] == "https://atop.tg/golfe-6-bureau-du-citoyen/"
    assert doc["source"] == "atop.tg"
    assert doc["category"] == "press"
    assert doc["subcategory"] == "health"
    assert doc["published_at"] == "2026-10-24"
    assert old["published_at"] is None


def test_local_wikipedias_are_stored_in_their_language():
    from scrapers.spiders.wikipedia_local_spider import WikipediaLocalSpider

    spider = WikipediaLocalSpider(langs="kbp")
    listing = _json(
        "https://kbp.wikipedia.org/w/api.php?action=query&list=allpages",
        {
            "query": {"allpages": [{"pageid": 7, "title": "Kara"}]},
            "continue": {"apcontinue": "Lama"},
        },
    )
    article_req, next_req = list(spider.parse_list(listing, lang="kbp"))
    assert "pageids=7" in article_req.url
    assert "apcontinue=Lama" in next_req.url

    page = {
        "pageid": 7,
        "title": "Kara",
        "extract": "Kara ɛyʊ Togo tɛtʊ " * 10,
        "canonicalurl": "https://kbp.wikipedia.org/wiki/Kara",
    }
    article = _json(article_req.url, {"query": {"pages": {"7": page}}})
    (doc,) = list(spider.parse_article(article, lang="kbp"))
    assert doc["url"] == "https://kbp.wikipedia.org/wiki/Kara"
    assert doc["source"] == "kbp.wikipedia.org"
    assert doc["language"] == "kbp"

    stub = _json(article_req.url, {"query": {"pages": {"8": {**page, "extract": "Kara."}}}})
    assert list(spider.parse_article(stub, lang="kbp")) == []


def test_atop_daily_crawl_reads_only_the_newest_pages():
    from scrapers.spiders.atop_spider import AtopSpider
    from scrapy.settings import Settings

    spider = AtopSpider()
    url = "https://atop.tg/wp-json/wp/v2/posts?per_page=100&page=5"
    spider.settings = Settings({"SKIP_KNOWN_URLS": True})
    assert list(spider.parse_posts(_json(url, [], total_pages=163), page=5)) == []
    spider.settings = Settings({"SKIP_KNOWN_URLS": False})
    (next_page,) = list(spider.parse_posts(_json(url, [], total_pages=163), page=5))
    assert "page=6" in next_page.url


def test_republiquetogolaise_reads_intro_and_full_text_with_link_text():
    from scrapers.spiders.republiquetogolaise_spider import RepubliquetogolaisSpider
    from scrapy.http import HtmlResponse

    url = "https://www.republiquetogolaise.tg/gestion-publique/1710-12394-togo-chine"
    intro = "Le Togo et la Chine renforcent leur coopération. " * 8
    page = (
        '<h1 class="itemTitle">Le Togo et la Chine scellent 13 accords</h1>'
        f'<div class="itemIntroText"><p>{intro} dans le sillage de '
        '<a href="/x">l’élévation des relations</a>.</p></div>'
        '<div class="itemFullText"> </div><span class="itemDateCreated">'
        "samedi, 17 octobre 2026</span>"
    )
    response = HtmlResponse(url=url, body=page.encode(), encoding="utf-8")
    (doc,) = list(RepubliquetogolaisSpider().parse_article(response))
    assert "dans le sillage de l’élévation des relations" in doc["raw_content"]
    assert doc["source"] == "republiquetogolaise.tg"
    assert doc["published_at"] == "2026-10-17"


def test_eregulations_procedure_becomes_one_readable_document():
    from scrapers.spiders.eregulations_spider import procedure_text

    data = {
        "breadcrumb": [
            {"Name": "ZONE FRANCHE"},
            {"Name": "Carnet bleu"},
            {"Name": "Renouvellement"},
        ],
        "blocksteps/": [
            {"Steps": [{"Name": "Déposer le carnet bleu"}, {"Name": "Payer les frais"}]}
        ],
        "institutions/": [{"Name": "Division des opérations douanières de la zone franche"}],
        "requeriments/": [{"RequirementName": "Carnet bleu", "Comments": None, "CopiesText": None}],
        "costs": [{"Value": 10000.0, "Unit": "CFA", "Comments": "frais de renouvellement"}],
        "timeframe": {"Total": {"Min": 960.0, "Max": 1015.0}},
        "results/": [{"Name": "Carnet bleu renouvelé"}],
        "laws/": [{"Name": "Courrier DG SAZOF sur le carnet bleu"}],
        "additionalinfo": {"Text": ""},
    }
    title, text = procedure_text(data)
    assert title == "Zone franche – Carnet bleu – Renouvellement"
    assert "1. Déposer le carnet bleu ; 2. Payer les frais" in text
    assert "Coût : 10 000 CFA frais de renouvellement." in text
    assert "Durée totale : 2 jours à 2 jours 55 min" in text
    assert "Base légale : Courrier DG SAZOF" in text
