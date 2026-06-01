"""
Spider for haac.tg — Haute Autorité de l'Audiovisuel et de la Communication du Togo.

Regulatory authority for broadcast and online media in Togo.
Contains official decisions, press freedom reports, media licenses,
and regulatory frameworks for Togolese media.
"""

from urllib.parse import urljoin

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

ENTRY_URLS = [
    "https://www.haac.tg/",
    "https://www.haac.tg/decisions/",
    "https://www.haac.tg/publications/",
    "https://www.haac.tg/actualites/",
    "https://www.haac.tg/textes-fondamentaux/",
    "https://www.haac.tg/communiques/",
]

EXCLUDED_PATHS = [
    "/wp-admin/", "/wp-content/", "/wp-login",
    "/feed/", "/tag/", "/author/", "/#",
    "mailto:", "javascript:", "/search/",
]


class HaacSpider(BaseTogoSpider):
    name = "haac"
    source = "haac.tg"
    category = "legal"
    language = "fr"

    start_urls = ENTRY_URLS

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    def parse(self, response):
        # Try WordPress sitemap
        if response.url in ENTRY_URLS and response.url.endswith("/"):
            sitemap_url = urljoin(response.url, "/wp-sitemap.xml")
            yield scrapy.Request(sitemap_url, callback=self._parse_sitemap, dont_filter=True, priority=20)

        for href in response.css("a::attr(href)").getall():
            url = urljoin(response.url, href)
            if self._is_content_url(url):
                yield scrapy.Request(url, callback=self.parse_page, priority=10)

    def _parse_sitemap(self, response):
        response.selector.remove_namespaces()
        for url in response.xpath("//loc/text()").getall():
            if self._is_content_url(url):
                yield scrapy.Request(url, callback=self.parse_page, priority=10)

    def parse_page(self, response):
        title = (
            response.css("h1::text").get("") or
            response.css("h1 *::text").get("") or
            response.css(".entry-title::text").get("") or
            response.css("title::text").get("").split("|")[0]
        ).strip()

        if not title or len(title) < 5:
            return

        body_html = response.css(
            ".entry-content, .post-content, article, main .content, #content"
        ).get("")
        raw_content = self.html_to_text(body_html) if body_html else ""

        if not raw_content or len(raw_content.split()) < 30:
            paragraphs = response.css("p::text, li::text").getall()
            raw_content = " ".join(p.strip() for p in paragraphs if len(p.strip()) > 10)

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

        for href in response.css("a::attr(href)").getall():
            url = urljoin(response.url, href)
            if self._is_content_url(url):
                yield scrapy.Request(url, callback=self.parse_page, priority=5)

    def _is_content_url(self, url: str) -> bool:
        if "haac.tg" not in url:
            return False
        if any(e in url for e in EXCLUDED_PATHS):
            return False
        path = url.split("haac.tg")[-1].rstrip("/")
        return bool(path) and path != "/" and len(path) > 5

    def _infer_subcategory(self, url: str) -> str:
        mapping = {
            "decision": "decision",
            "publication": "publication",
            "actualite": "actualite",
            "texte": "regulation",
            "communique": "communique",
            "rapport": "report",
        }
        for key, sub in mapping.items():
            if key in url.lower():
                return sub
        return "media-regulation"
