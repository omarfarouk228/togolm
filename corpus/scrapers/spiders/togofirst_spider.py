"""
Spider for togofirst.com — Togolese business and economic news portal.

WordPress site with date-based article URLs (/YYYY/MM/DD/slug/).
Covers economics, business, finance, investment, and entrepreneurship in Togo.
"""

import re
from urllib.parse import urljoin

import scrapy

from scrapers.spiders.base_spider import BaseTogoSpider

WP_DATE_URL_RE = re.compile(r"/\d{4}/\d{2}/\d{2}/.+/$")

CATEGORY_URLS = [
    "https://togofirst.com/category/economie/",
    "https://togofirst.com/category/finance/",
    "https://togofirst.com/category/entreprises/",
    "https://togofirst.com/category/investissements/",
    "https://togofirst.com/category/agriculture/",
    "https://togofirst.com/category/marches/",
    "https://togofirst.com/category/politique/",
]

EXCLUDED_PATHS = ["/tag/", "/author/", "/page/", "/feed/", "/wp-admin/", "/wp-content/"]


class TogofirstSpider(BaseTogoSpider):
    name = "togofirst"
    source = "togofirst.com"
    category = "press"
    language = "fr"

    start_urls = CATEGORY_URLS

    def parse(self, response):
        for href in response.css("a::attr(href)").getall():
            url = urljoin(response.url, href)
            if self._is_article_url(url):
                yield scrapy.Request(url, callback=self.parse_article, priority=10)

        next_page = response.css(
            "a.next::attr(href), a[rel='next']::attr(href), .nav-next a::attr(href)"
        ).get()
        if next_page:
            yield scrapy.Request(urljoin(response.url, next_page), callback=self.parse)

    def parse_article(self, response):
        title = (
            response.css("h1.entry-title::text").get("") or
            response.css("h1.post-title::text").get("") or
            response.css("h1::text").get("")
        ).strip()

        if not title or len(title) < 5:
            return

        body_html = response.css(
            ".entry-content, .post-content, .article-content, article .content"
        ).get("")
        raw_content = self.html_to_text(body_html) if body_html else ""

        if not raw_content or len(raw_content.split()) < 30:
            paragraphs = response.css("article p::text, article p *::text").getall()
            raw_content = " ".join(p.strip() for p in paragraphs if p.strip())

        if not raw_content or len(raw_content.split()) < 30:
            return

        published_at = (
            response.css("time::attr(datetime)").get("") or
            response.css("meta[property='article:published_time']::attr(content)").get("") or
            ""
        )

        subcategory = self._infer_subcategory(response.url)

        yield self.make_document(
            response=response,
            title=title,
            raw_content=raw_content,
            subcategory=subcategory,
            published_at=published_at[:10] if published_at else None,
            metadata={"word_count": len(raw_content.split())},
        )

    def _is_article_url(self, url: str) -> bool:
        if "togofirst.com" not in url:
            return False
        if any(e in url for e in EXCLUDED_PATHS):
            return False
        path = url.split("togofirst.com")[-1]
        return bool(WP_DATE_URL_RE.search(path))

    def _infer_subcategory(self, url: str) -> str:
        mapping = {
            "finance": "finance",
            "economie": "economy",
            "entreprises": "business",
            "investissements": "investment",
            "agriculture": "agriculture",
            "marches": "markets",
            "politique": "politics",
        }
        for key, sub in mapping.items():
            if key in url.lower():
                return sub
        return "news"
