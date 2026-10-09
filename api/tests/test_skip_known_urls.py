"""Incremental crawl: news spiders must not re-download ingested articles."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Scrapy project modules are imported as "scrapers.*" from the corpus/ dir.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "corpus"))

from scrapers.middlewares import SkipKnownUrlsMiddleware, normalize_url  # noqa: E402
from scrapy.exceptions import IgnoreRequest  # noqa: E402
from scrapy.http import Request  # noqa: E402


def test_normalize_url_ignores_scheme_www_slash_and_fragment():
    assert normalize_url("https://www.icilome.com/2026/10/article/#top") == normalize_url(
        "http://icilome.com/2026/10/article"
    )


def _middleware(known: set[str], enabled: bool = True) -> SkipKnownUrlsMiddleware:
    mw = SkipKnownUrlsMiddleware(enabled)
    spider = MagicMock(source="icilome.com")
    with patch.object(SkipKnownUrlsMiddleware, "_load_known_urls", return_value=known):
        mw.spider_opened(spider)
    return mw


def test_known_article_is_skipped():
    mw = _middleware({normalize_url("https://icilome.com/a")})
    with pytest.raises(IgnoreRequest):
        mw.process_request(Request("https://www.icilome.com/a/"))
    assert mw.skipped == 1


def test_new_article_and_sitemaps_are_fetched():
    mw = _middleware({normalize_url("https://icilome.com/a")})
    assert mw.process_request(Request("https://icilome.com/b")) is None
    assert mw.process_request(Request("https://icilome.com/wp-sitemap.xml")) is None


def test_disabled_middleware_never_queries_the_database():
    with patch.object(SkipKnownUrlsMiddleware, "_load_known_urls") as load:
        mw = SkipKnownUrlsMiddleware(False)
        mw.spider_opened(MagicMock(source="icilome.com"))
    load.assert_not_called()
    assert mw.process_request(Request("https://icilome.com/a")) is None


def test_database_error_falls_back_to_full_crawl():
    mw = SkipKnownUrlsMiddleware(True)
    with patch.object(SkipKnownUrlsMiddleware, "_load_known_urls", side_effect=OSError("down")):
        mw.spider_opened(MagicMock(source="icilome.com"))
    assert mw.process_request(Request("https://icilome.com/a")) is None
