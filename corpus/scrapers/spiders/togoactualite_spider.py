"""
Spider for togoactualite.com — Togo news aggregator and press portal.

WordPress site using the JEG theme with 28 post sitemaps (~28,000 articles).
Covers: politics, economy, society, sports, culture, international.

Uses post sitemaps for complete article discovery.
"""

import re

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

# Post sitemaps are numbered oldest -> newest. Only sitemaps 15 and up (the
# ~14,000 most recent articles) are crawled, to skip 10+ years of archives.
# They are read from the sitemap index rather than hardcoded (the old
# range(15, 29) would have silently stopped at post-sitemap28, as icilome's
# hardcoded list did at 23).
SITEMAP_INDEX = "https://togoactualite.com/sitemap_index.xml"
POST_SITEMAP_RE = re.compile(r"post-sitemap(\d*)\.xml$")
MIN_POST_SITEMAP = 15

EXCLUDED_PATHS = [
    "/category/",
    "/tag/",
    "/author/",
    "/page/",
    "/feed/",
    "/wp-content/",
    "/wp-admin/",
    "/wp-json/",
    "/sitemap",
    "mailto:",
    "javascript:",
    "#",
]

SUBCATEGORY_MAP = {
    "politique": "politics",
    "economie": "economy",
    "societe": "society",
    "sport": "sport",
    "culture": "culture",
    "international": "international",
    "sante": "health",
    "education": "education",
    "justice": "justice",
    "environnement": "environment",
    "securite": "security",
    "diplomatie": "diplomacy",
}


class TogoactualiteSpider(BaseTogoSpider):
    name = "togoactualite"
    source = "togoactualite.com"
    category = "press"
    language = "fr"

    start_urls = [SITEMAP_INDEX]

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
    }

    def parse(self, response):
        ct = response.headers.get("Content-Type", b"").decode()
        if "xml" in ct or response.url.endswith(".xml"):
            yield from self._parse_sitemap(response)
        else:
            yield from self._parse_article(response)

    def _parse_sitemap(self, response):
        response.selector.remove_namespaces()
        if response.xpath("/sitemapindex"):
            yield from self._parse_sitemap_index(response)
            return
        for url in response.xpath("//loc/text()").getall():
            url = url.strip()
            if self._is_article_url(url):
                yield scrapy.Request(url, callback=self.parse, priority=10)

    def _parse_sitemap_index(self, response):
        """Follow post sitemaps >= MIN_POST_SITEMAP, newest first."""
        for url in response.xpath("//sitemap/loc/text()").getall():
            m = POST_SITEMAP_RE.search(url.strip())
            if m and int(m.group(1) or 1) >= MIN_POST_SITEMAP:
                yield scrapy.Request(url.strip(), callback=self.parse, priority=int(m.group(1)))

    def _parse_article(self, response):
        # JEG theme selectors
        title = (
            response.css("h1.jeg_post_title::text").get("")
            or response.css("h1.entry-title::text").get("")
            or response.css("h1::text").get("")
            or ""
        ).strip()

        if not title or len(title) < 5:
            return

        # Main article body
        body_html = (
            response.css(".entry-content").get("")
            or response.css(".jeg_inner_content .content-inner").get("")
            or response.css(".content-inner").get("")
            or ""
        )
        raw_content = self.html_to_text(body_html) if body_html else ""

        if not raw_content or len(raw_content.split()) < 20:
            paragraphs = response.css(
                ".entry-content p::text, .content-inner p::text, article p::text"
            ).getall()
            raw_content = " ".join(p.strip() for p in paragraphs if p.strip())

        if not raw_content or len(raw_content.split()) < 20:
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
        if "togoactualite.com" not in url:
            return False
        if any(e in url for e in EXCLUDED_PATHS):
            return False
        path = url.split("togoactualite.com")[-1]
        # Article URLs: /some-long-slug/
        parts = [p for p in path.split("/") if p]
        return len(parts) == 1 and len(parts[0]) > 8

    def _infer_subcategory(self, url: str) -> str:
        url_lower = url.lower()
        for key, sub in SUBCATEGORY_MAP.items():
            if f"/{key}/" in url_lower or url_lower.endswith(f"/{key}"):
                return sub
        return "news"
