"""
Spider for icilome.com — Le portail togolais par excellence.

Togolese news portal covering politics, economy, society, jobs.
WordPress site with date-based URLs: /YYYY/MM/slug/
"""

import re
from urllib.parse import urljoin

import scrapy

from scrapers.spiders.base_spider import BaseTogoSpider

WP_DATE_URL_RE = re.compile(r"/\d{4}/\d{2}/.+/$")

CATEGORY_URLS = [
    "https://icilome.com/category/togo/",
    "https://icilome.com/category/affaires-et-pme/",
    "https://icilome.com/category/emplois-et-formation/",
    "https://icilome.com/category/faits-divers/",
    "https://icilome.com/category/pays/international/",
    "https://icilome.com/category/revue-de-presse/",
]


class IcilomeSpider(BaseTogoSpider):
    name = "icilome"
    source = "icilome.com"
    category = "press"
    language = "fr"

    start_urls = CATEGORY_URLS

    def parse(self, response):
        for href in response.css("a::attr(href)").getall():
            url = urljoin(response.url, href)
            if self._is_article_url(url):
                yield scrapy.Request(url, callback=self.parse_article, priority=10)

        next_page = response.css("a.next::attr(href), a[rel='next']::attr(href)").get()
        if next_page:
            yield scrapy.Request(urljoin(response.url, next_page), callback=self.parse)

    def parse_article(self, response):
        title = (
            response.css("h1.entry-title::text").get("") or
            response.css("h1::text").get("") or
            response.css(".post-title::text").get("")
        ).strip()

        if not title:
            return

        # WordPress content — try standard selectors
        body_html = response.css(
            ".entry-content, .post-content, article .content, [class*=entry-content]"
        ).get("")

        raw_content = self.html_to_text(body_html) if body_html else ""

        if not raw_content or len(raw_content.split()) < 20:
            # Fallback: p tags in article
            paragraphs = response.css("article p::text, article p *::text").getall()
            raw_content = " ".join(p.strip() for p in paragraphs if p.strip())

        if not raw_content or len(raw_content.split()) < 20:
            return

        published_at = (
            response.css("time::attr(datetime)").get("") or
            response.css("meta[property='article:published_time']::attr(content)").get("") or
            ""
        )

        subcategory = self._infer_category(response.url)

        yield self.make_document(
            response=response,
            title=title,
            raw_content=raw_content,
            subcategory=subcategory,
            published_at=published_at[:10] if published_at else None,
            metadata={"word_count": len(raw_content.split())},
        )

    def _is_article_url(self, url: str) -> bool:
        if "icilome.com" not in url:
            return False
        path = url.split("icilome.com")[-1]
        return bool(WP_DATE_URL_RE.search(path))

    def _infer_category(self, url: str) -> str:
        mapping = {
            "affaires-et-pme": "economy",
            "emplois-et-formation": "education",
            "faits-divers": "faits-divers",
            "international": "international",
            "revue-de-presse": "revue-de-presse",
        }
        for key, cat in mapping.items():
            if key in url:
                return cat
        return "news"
