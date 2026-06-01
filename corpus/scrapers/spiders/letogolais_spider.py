"""
Spider for letogolais.com — Independent Togolese news and analysis.

WordPress site. Article URLs: /{article-slug}/
Covers: politics, human rights, civil society, opposition news.
Independent voice with analysis rarely found on government-aligned media.
"""

import re
from urllib.parse import urljoin

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

# WordPress simple slug: /slug/ (no date in path)
SLUG_RE = re.compile(r"^/[a-z][a-z0-9\-]{14,}/?$")

CATEGORY_URLS = [
    "https://www.letogolais.com/",
    "https://www.letogolais.com/category/politique/",
    "https://www.letogolais.com/category/societe/",
    "https://www.letogolais.com/category/droits/",
    "https://www.letogolais.com/category/economie/",
    "https://www.letogolais.com/category/international/",
]

EXCLUDED_PATHS = [
    "/tag/", "/author/", "/page/", "/feed/", "/wp-admin/", "/wp-content/",
    "/wp-json/", "/category/", "/lettre-dinformations/", "/publicite/",
    "/soutenez/", "/contact", "/about", "/elementor-",
    "mailto:", "javascript:", "#",
]


class LetogolaisSpider(BaseTogoSpider):
    name = "letogolais"
    source = "letogolais.com"
    category = "press"
    language = "fr"

    start_urls = CATEGORY_URLS

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

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
            response.css("h1 *::text").get("")
        ).strip()

        if not title or len(title) < 5:
            return

        body_html = response.css(
            ".entry-content, .post-content, article .content, .tdb-block-inner"
        ).get("")
        raw_content = self.html_to_text(body_html) if body_html else ""

        if not raw_content or len(raw_content.split()) < 30:
            paragraphs = response.css("article p::text, .entry-content p::text").getall()
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
        if "letogolais.com" not in url:
            return False
        if any(e in url for e in EXCLUDED_PATHS):
            return False
        path = url.split("letogolais.com")[-1].split("?")[0]
        return bool(SLUG_RE.match(path.rstrip("/") + "/"))

    def _infer_subcategory(self, url: str) -> str:
        mapping = {
            "politique": "politics",
            "societe": "society",
            "droits": "human-rights",
            "economie": "economy",
            "international": "international",
            "culture": "culture",
        }
        for key, sub in mapping.items():
            if key in url.lower():
                return sub
        return "news"
