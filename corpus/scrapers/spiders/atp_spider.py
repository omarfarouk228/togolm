"""
Spider for agencetogopresse.com (ATP) — Agence Togolaise de Presse.

The official Togolese press agency. Covers official government news,
diplomatic dispatches, and national announcements directly from the source.
"""

import re
from urllib.parse import urljoin

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

# Article URLs typically have a numeric ID or date segment
ARTICLE_URL_RE = re.compile(r"/(article|actualite|depeche|news)/\d+|/\d{4}/\d{2}/.+/$|/[a-z\-]{15,}/?$")

ENTRY_URLS = [
    "https://www.agencetogopresse.com/",
    "https://www.agencetogopresse.com/categorie/politique",
    "https://www.agencetogopresse.com/categorie/economie",
    "https://www.agencetogopresse.com/categorie/societe",
    "https://www.agencetogopresse.com/categorie/diplomatie",
    "https://www.agencetogopresse.com/categorie/sport",
]

EXCLUDED_PATHS = [
    "/login", "/register", "/search", "/tag", "/auteur", "/feed",
    "#", "mailto:", "javascript:",
]


class AtpSpider(BaseTogoSpider):
    name = "atp"
    source = "agencetogopresse.com"
    category = "press"
    language = "fr"

    start_urls = ENTRY_URLS

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    def parse(self, response):
        for href in response.css("a::attr(href)").getall():
            url = urljoin(response.url, href)
            if self._is_article_url(url):
                yield scrapy.Request(url, callback=self.parse_article, priority=10)

        # Pagination
        next_page = response.css(
            "a.next::attr(href), a[rel='next']::attr(href), "
            ".pagination a[aria-label='Next']::attr(href)"
        ).get()
        if next_page:
            yield scrapy.Request(urljoin(response.url, next_page), callback=self.parse)

    def parse_article(self, response):
        title = (
            response.css("h1::text").get("") or
            response.css("h1 *::text").get("") or
            response.css(".article-title::text").get("") or
            response.css(".titre::text").get("")
        ).strip()

        if not title or len(title) < 5:
            return

        body_html = response.css(
            ".article-body, .article-content, .entry-content, .post-content, article"
        ).get("")
        raw_content = self.html_to_text(body_html) if body_html else ""

        if not raw_content or len(raw_content.split()) < 30:
            paragraphs = response.css("article p::text, .content p::text, main p::text").getall()
            raw_content = " ".join(p.strip() for p in paragraphs if p.strip())

        if not raw_content or len(raw_content.split()) < 30:
            return

        published_at = (
            response.css("time::attr(datetime)").get("") or
            response.css("meta[property='article:published_time']::attr(content)").get("") or
            response.css(".date::text, .published-date::text").get("") or
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
        if "agencetogopresse.com" not in url:
            return False
        if any(e in url for e in EXCLUDED_PATHS):
            return False
        path = url.split("agencetogopresse.com")[-1]
        return bool(ARTICLE_URL_RE.search(path)) and len(path) > 15

    def _infer_subcategory(self, url: str) -> str:
        mapping = {
            "politique": "politics",
            "economie": "economy",
            "societe": "society",
            "diplomatie": "diplomacy",
            "sport": "sport",
            "culture": "culture",
        }
        for key, sub in mapping.items():
            if key in url.lower():
                return sub
        return "news"
