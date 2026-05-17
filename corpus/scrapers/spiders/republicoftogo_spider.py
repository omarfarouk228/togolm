"""
Spider for republicoftogo.com — Official Togolese news and government information portal.

Covers official government announcements, diplomacy, economy, and national news.
"""

import re
from urllib.parse import urljoin

import scrapy

from scrapers.spiders.base_spider import BaseTogoSpider

# Article URLs typically contain a date segment or a long slug
ARTICLE_URL_RE = re.compile(r"/\d{4}/\d{2}/.+|/[a-z\-]{20,}/?$")

SECTION_URLS = [
    "https://www.republicoftogo.com/Toutes-les-rubriques/Politique",
    "https://www.republicoftogo.com/Toutes-les-rubriques/Eco-Business",
    "https://www.republicoftogo.com/Toutes-les-rubriques/Societe",
    "https://www.republicoftogo.com/Toutes-les-rubriques/Diplomatie",
    "https://www.republicoftogo.com/Toutes-les-rubriques/Sports",
    "https://www.republicoftogo.com/Toutes-les-rubriques/Tech-and-telecom",
    "https://www.republicoftogo.com/",
]

EXCLUDED_PATHS = [
    "/Connexion", "/Inscription", "/Recherche", "/Contact",
    "/Toutes-les-rubriques/",
    "#", "mailto:", "javascript:",
]


class RepublicoftogoSpider(BaseTogoSpider):
    name = "republicoftogo"
    source = "republicoftogo.com"
    category = "press"
    language = "fr"

    start_urls = SECTION_URLS

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    def parse(self, response):
        for href in response.css("a::attr(href)").getall():
            url = urljoin(response.url, href)
            if self._is_article_url(url):
                yield scrapy.Request(url, callback=self.parse_article, priority=10)
            elif self._is_listing_url(url):
                yield scrapy.Request(url, callback=self.parse, priority=5)

    def parse_article(self, response):
        title = (
            response.css("h1::text").get("") or
            response.css(".article-title::text").get("") or
            response.css(".titre::text").get("")
        ).strip()

        if not title or len(title) < 5:
            return

        body_html = response.css(
            ".article-body, .article-content, .contenu, .corps-article, article"
        ).get("")
        raw_content = self.html_to_text(body_html) if body_html else ""

        if not raw_content or len(raw_content.split()) < 30:
            paragraphs = response.css("article p::text, .content p::text").getall()
            raw_content = " ".join(p.strip() for p in paragraphs if p.strip())

        if not raw_content or len(raw_content.split()) < 30:
            return

        published_at = (
            response.css("time::attr(datetime)").get("") or
            response.css(".date::text").get("") or
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
        if "republicoftogo.com" not in url:
            return False
        if any(e in url for e in EXCLUDED_PATHS):
            return False
        path = url.split("republicoftogo.com")[-1]
        # Articles have at least 3 path segments (section/subsection/slug)
        segments = [s for s in path.split("/") if s]
        return len(segments) >= 3 and len(path) > 40

    def _is_listing_url(self, url: str) -> bool:
        if "republicoftogo.com" not in url:
            return False
        if any(e in url for e in EXCLUDED_PATHS):
            return False
        return "/Toutes-les-rubriques/" not in url and "republicoftogo.com" in url

    def _infer_subcategory(self, url: str) -> str:
        mapping = {
            "Politique": "politics",
            "Eco-Business": "economy",
            "Societe": "society",
            "Diplomatie": "diplomacy",
            "Sports": "sport",
            "Tech": "tech",
        }
        for key, sub in mapping.items():
            if key.lower() in url.lower():
                return sub
        return "news"
