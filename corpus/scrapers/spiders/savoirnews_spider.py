"""
Spider for savoirnews.net — Togo news and information portal.

Covers politics, economy, society, diplomacy, sport, and culture in Togo.
WordPress site with 6 post sitemaps (~1,200 articles total).

Uses sitemaps for complete discovery (upgraded from category-page approach).
"""

import re

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

# savoirnews uses simple slugs: /article-slug/ (no date prefix in path)
ARTICLE_SLUG_RE = re.compile(r"^/[a-z][a-z0-9\-]{14,}/?$")

POST_SITEMAPS = [
    f"https://www.savoirnews.net/post-sitemap{'' if i == 1 else i}.xml"
    for i in range(1, 7)  # sitemaps 1..6 = ~1,200 articles
]

EXCLUDED_PATHS = [
    "/tag/",
    "/author/",
    "/page/",
    "/feed/",
    "/wp-admin/",
    "/wp-content/",
    "/category/",
    "/contact",
    "/about",
    "/wp-login",
    "/sitemap",
]


class SavoirnewsSpider(BaseTogoSpider):
    name = "savoirnews"
    source = "savoirnews.net"
    category = "press"
    language = "fr"

    start_urls = POST_SITEMAPS

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
    }

    def parse(self, response):
        ct = response.headers.get("Content-Type", b"").decode()
        if "xml" in ct or response.url.endswith(".xml"):
            response.selector.remove_namespaces()
            for url in response.xpath("//loc/text()").getall():
                url = url.strip()
                if self._is_article_url(url):
                    yield scrapy.Request(url, callback=self.parse_article, priority=10)
        else:
            yield from self.parse_article(response)

    def parse_article(self, response):
        title = (
            response.css("h1.entry-title::text").get("") or response.css("h1::text").get("")
        ).strip()

        if not title or len(title) < 5:
            return

        body_html = response.css(".entry-content, .post-content, article .content").get("")
        raw_content = self.html_to_text(body_html) if body_html else ""

        if not raw_content or len(raw_content.split()) < 30:
            paragraphs = response.css("article p::text, .post p::text").getall()
            raw_content = " ".join(p.strip() for p in paragraphs if p.strip())

        if not raw_content or len(raw_content.split()) < 30:
            return

        published_at = (
            response.css("time::attr(datetime)").get("")
            or response.css("meta[property='article:published_time']::attr(content)").get("")
            or ""
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
        if "savoirnews.net" not in url:
            return False
        if any(e in url for e in EXCLUDED_PATHS):
            return False
        path = url.split("savoirnews.net")[-1].split("?")[0]
        return bool(ARTICLE_SLUG_RE.match(path.rstrip("/") + "/"))

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
