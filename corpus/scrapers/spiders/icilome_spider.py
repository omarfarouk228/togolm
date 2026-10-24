"""
Spider for icilome.com — Le portail togolais par excellence.

Togolese news portal covering politics, economy, society, jobs.
WordPress site whose Yoast sitemap index lists post-sitemapN.xml files
(~1,000 articles each, N grows over time). Date-based article URLs: /YYYY/MM/slug/
"""

import re

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

WP_DATE_URL_RE = re.compile(r"/\d{4}/\d{2}/.+/$")

# The post sitemaps used to be hardcoded as post-sitemap1..23.xml. The site
# opened post-sitemap24 and 25 in September 2026 and every article published
# after 2026-09-24 was never crawled. Read them from the index instead.
SITEMAP_INDEX = "https://icilome.com/sitemap_index.xml"
POST_SITEMAP_RE = re.compile(r"post-sitemap(\d*)\.xml$")

EXCLUDED_PATHS = [
    "/category/",
    "/tag/",
    "/author/",
    "/page/",
    "/feed/",
    "/wp-content/",
    "/wp-admin/",
]

SUBCATEGORY_MAP = {
    "affaires-et-pme": "economy",
    "emplois-et-formation": "education",
    "faits-divers": "faits-divers",
    "international": "international",
    "revue-de-presse": "revue-de-presse",
    "politique": "politics",
    "societe": "society",
    "economie": "economy",
    "sport": "sport",
    "culture": "culture",
}


class IcilomeSpider(BaseTogoSpider):
    name = "icilome"
    source = "icilome.com"
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
        """Follow the post sitemaps, newest (highest N) first: a crawl cut short
        by the subprocess timeout still picks up the latest articles."""
        for url in response.xpath("//sitemap/loc/text()").getall():
            m = POST_SITEMAP_RE.search(url.strip())
            if m:
                n = int(m.group(1) or 1)
                yield scrapy.Request(url.strip(), callback=self.parse, priority=n)

    def _parse_article(self, response):
        title = (
            response.css("h1.entry-title::text").get("")
            or response.css("h1::text").get("")
            or response.css(".post-title::text").get("")
        ).strip()

        if not title or len(title) < 5:
            return

        body_html = response.css(
            ".entry-content, .post-content, article .content, [class*=entry-content]"
        ).get("")
        raw_content = self.html_to_text(body_html) if body_html else ""

        if not raw_content or len(raw_content.split()) < 20:
            paragraphs = response.css("article p::text, article p *::text").getall()
            raw_content = " ".join(p.strip() for p in paragraphs if p.strip())

        if not raw_content or len(raw_content.split()) < 20:
            return

        published_at = (
            response.css("time::attr(datetime)").get("")
            or response.css("meta[property='article:published_time']::attr(content)").get("")
            or ""
        )

        yield self.make_document(
            response=response,
            title=title,
            raw_content=raw_content,
            subcategory=self._infer_subcategory(response.url),
            published_at=published_at[:10] if published_at else None,
            metadata={"word_count": len(raw_content.split())},
        )

    def _is_article_url(self, url: str) -> bool:
        if "icilome.com" not in url:
            return False
        if any(e in url for e in EXCLUDED_PATHS):
            return False
        path = url.split("icilome.com")[-1]
        return bool(WP_DATE_URL_RE.search(path))

    def _infer_subcategory(self, url: str) -> str:
        for key, cat in SUBCATEGORY_MAP.items():
            if key in url:
                return cat
        return "news"
