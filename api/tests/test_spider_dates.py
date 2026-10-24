"""Publication dates and sitemap discovery of the news spiders."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Scrapy project modules are imported as "scrapers.*" from the corpus/ dir.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "corpus"))

from scrapers.spiders.base_spider import BaseTogoSpider, parse_date  # noqa: E402
from scrapers.spiders.icilome_spider import IcilomeSpider  # noqa: E402
from scrapers.spiders.togoactualite_spider import TogoactualiteSpider  # noqa: E402
from scrapy.http import HtmlResponse, Request, XmlResponse  # noqa: E402

from rag.indexation.ingestor import backfill_published_at  # noqa: E402


def _html(url: str, body: str) -> HtmlResponse:
    return HtmlResponse(
        url=url, body=f"<html><body>{body}</body></html>".encode(), encoding="utf-8"
    )


def test_parse_date_iso_and_french():
    assert parse_date("2026-10-17T19:48:24+00:00") == "2026-10-17"
    assert parse_date(" vendredi, 23 octobre 2026 17:10 ") == "2026-10-23"
    assert parse_date("1er août 2025") == "2025-08-01"
    assert parse_date("   ") is None
    assert parse_date("16.05.22") is None
    assert parse_date("2026-02-30") is None
    assert parse_date("0001-01-01") is None
    assert parse_date("1970-01-01T00:00:00+00:00") is None


def test_togofirst_date_in_k2_text():
    response = _html(
        "https://www.togofirst.com/fr/tic/2310-20442-commerce",
        '<div class="itemDateCreated">\n <img src="/i.png"/> vendredi, 23 octobre 2026 17:10 </div>'
        "<time>16.05.22</time>",
    )
    assert BaseTogoSpider.extract_published_at(response, ".itemDateCreated") == "2026-10-23"


def test_jsonld_article_beats_sidebar_time():
    response = _html(
        "https://www.republicoftogo.com/toutes-les-rubriques/eco-finance/x",
        '<script type="application/ld+json">{"@type": "Article", "datePublished": "2026-10-23"}'
        '</script><div class="publish-date"> <time datetime="2022-05-16">16.05.22</time></div>',
    )
    assert BaseTogoSpider.extract_published_at(response) == "2026-10-23"


def test_jsonld_graph_and_job_posting():
    graph = _html(
        "https://togo24.tg/x",
        '<script type="application/ld+json">{"@graph": [{"@type": "WebSite"},'
        ' {"@type": "NewsArticle", "datePublished": "2026-10-17T19:48:24+00:00"}]}</script>',
    )
    job = _html(
        "https://anpetogo.org/offres/x",
        '<script type="application/ld+json">{"@type": "JobPosting",'
        ' "datePosted": "2026-08-21T05:52:48+00:00"}</script>'
        '<script type="application/ld+json">not json</script>',
    )
    assert BaseTogoSpider.extract_published_at(graph) == "2026-10-17"
    assert BaseTogoSpider.extract_published_at(job) == "2026-08-21"


def test_microdata_text_and_url_fallback():
    savoirnews = _html(
        "https://savoirnews.net/x/",
        '<span class="published" itemprop="datePublished"> 23 octobre 2026 </span>',
    )
    by_url = _html("https://togo24.tg/2026/10/17/okou-le-gouverneur/", "<p>texte</p>")
    undated = _html("https://www.letogolais.com/x/", '<div class="topbar-date"> </div>')
    assert BaseTogoSpider.extract_published_at(savoirnews) == "2026-10-23"
    assert BaseTogoSpider.extract_published_at(by_url) == "2026-10-17"
    assert BaseTogoSpider.extract_published_at(undated) is None


SITEMAP_INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>{base}/post-sitemap.xml</loc></sitemap>
  <sitemap><loc>{base}/post-sitemap14.xml</loc></sitemap>
  <sitemap><loc>{base}/post-sitemap25.xml</loc></sitemap>
  <sitemap><loc>{base}/page-sitemap.xml</loc></sitemap>
  <sitemap><loc>{base}/category-sitemap.xml</loc></sitemap>
</sitemapindex>"""


def _index(base: str) -> XmlResponse:
    url = f"{base}/sitemap_index.xml"
    return XmlResponse(url=url, body=SITEMAP_INDEX.format(base=base).encode(), request=Request(url))


def test_icilome_follows_every_post_sitemap_newest_first():
    requests = list(IcilomeSpider().parse(_index("https://icilome.com")))
    by_url = {r.url: r.priority for r in requests}
    assert by_url == {
        "https://icilome.com/post-sitemap.xml": 1,
        "https://icilome.com/post-sitemap14.xml": 14,
        "https://icilome.com/post-sitemap25.xml": 25,
    }


def test_togoactualite_skips_archive_sitemaps():
    requests = list(TogoactualiteSpider().parse(_index("https://togoactualite.com")))
    assert [r.url for r in requests] == ["https://togoactualite.com/post-sitemap25.xml"]


def test_icilome_post_sitemap_still_yields_articles():
    url = "https://icilome.com/post-sitemap25.xml"
    body = (
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>https://icilome.com/2026/10/un-article/</loc></url>"
        "<url><loc>https://icilome.com/category/politique/</loc></url></urlset>"
    )
    requests = list(IcilomeSpider().parse(XmlResponse(url=url, body=body.encode())))
    assert [r.url for r in requests] == ["https://icilome.com/2026/10/un-article/"]


def test_backfill_published_at_only_fills_missing_dates():
    cur = MagicMock()
    backfill_published_at(cur, "doc-1", "23 octobre 2026")
    sql, params = cur.execute.call_args.args
    assert "published_at IS NULL" in sql
    assert params == ("2026-10-23", "doc-1")

    cur = MagicMock()
    backfill_published_at(cur, "doc-1", None)
    cur.execute.assert_not_called()
