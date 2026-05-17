"""
Spider for togofirst.com — Togolese business and economic news portal.

Joomla/K2 site. Article URLs follow the pattern:
  /fr/{category}/DDMM-{id}-{slug}

Uses both the RSS feed and category-based crawling to maximize coverage.
Covers economics, business, finance, investment, agriculture, governance.
"""

import re
from urllib.parse import urljoin

import scrapy

from scrapers.spiders.base_spider import BaseTogoSpider

# Joomla K2 article URL: /fr/category/DDMM-NNNNN-slug
ARTICLE_URL_RE = re.compile(r"/fr/[a-z\-]+/\d{4}-\d+-[a-z]")

RSS_FEEDS = [
    "https://www.togofirst.com/fr/rss-fr",
    "https://www.togofirst.com/fr/rss-fr?format=feed&type=atom",
]

CATEGORY_URLS = [
    "https://www.togofirst.com/fr/finance",
    "https://www.togofirst.com/fr/banque",
    "https://www.togofirst.com/fr/gouvernance-economique",
    "https://www.togofirst.com/fr/investissement",
    "https://www.togofirst.com/fr/agro",
    "https://www.togofirst.com/fr/gestion-publique",
    "https://www.togofirst.com/fr/energies",
    "https://www.togofirst.com/fr/telecoms",
    "https://www.togofirst.com/fr/sante",
    "https://www.togofirst.com/fr/securite",
    "https://www.togofirst.com/fr/justice",
    "https://www.togofirst.com/fr/formation",
    "https://www.togofirst.com/fr/culture",
]

EXCLUDED_PATHS = [
    "/templates/", "/components/", "/modules/", "/plugins/", "/media/",
    "/administrator/", "/cache/", "?", "#", "mailto:", "javascript:",
    "/contact", "/login", "/register", "/user",
]


class TogofirstSpider(BaseTogoSpider):
    name = "togofirst"
    source = "togofirst.com"
    category = "press"
    language = "fr"

    start_urls = RSS_FEEDS + CATEGORY_URLS

    custom_settings = {
        "DOWNLOAD_DELAY": 1.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "FEED_EXPORT_ENCODING": "utf-8",
    }

    def parse(self, response):
        ct = response.headers.get("Content-Type", b"").decode()

        # Handle RSS/Atom feeds
        if "xml" in ct or "rss" in ct or "atom" in ct or response.url.endswith(("rss", "atom")):
            yield from self._parse_feed(response)
            return

        # Category listing — follow article links
        for href in response.css("a::attr(href)").getall():
            url = urljoin(response.url, href)
            if self._is_article_url(url):
                yield scrapy.Request(url, callback=self.parse_article, priority=10)

        # Pagination (Joomla style: ?start=N)
        next_links = response.css("a.pagenav::attr(href), li.next a::attr(href), .pagination a::attr(href)").getall()
        for href in next_links:
            url = urljoin(response.url, href)
            if "togofirst.com" in url:
                yield scrapy.Request(url, callback=self.parse, priority=5)

    def _parse_feed(self, response):
        """Parse RSS/Atom feed and follow article links."""
        response.selector.remove_namespaces()
        # RSS <link> elements
        links = response.xpath("//item/link/text()").getall()
        # Atom <link href="...">
        links += response.xpath("//entry/link/@href").getall()

        for url in links:
            url = url.strip()
            if self._is_article_url(url):
                yield scrapy.Request(url, callback=self.parse_article, priority=10)

    def parse_article(self, response):
        title = (
            response.css("h1::text, h2.itemTitle::text, .itemTitle a::text").get("") or
            response.css("h1 *::text").get("")
        ).strip()

        if not title or len(title) < 5:
            return

        # K2 article body
        body_html = response.css(
            ".itemBody, .itemIntroText, .itemFullText, "
            "article .content, .k2-item-body"
        ).get("")
        raw_content = self.html_to_text(body_html) if body_html else ""

        if not raw_content or len(raw_content.split()) < 30:
            paragraphs = response.css(".itemBody p::text, article p::text").getall()
            raw_content = " ".join(p.strip() for p in paragraphs if p.strip())

        if not raw_content or len(raw_content.split()) < 30:
            return

        published_at = (
            response.css("time::attr(datetime)").get("") or
            response.css(".itemDateCreated::text, .published::text").get("") or
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
        return bool(ARTICLE_URL_RE.search(path))

    def _infer_subcategory(self, url: str) -> str:
        mapping = {
            "finance": "finance",
            "banque": "banking",
            "gouvernance": "governance",
            "investissement": "investment",
            "agro": "agriculture",
            "gestion-publique": "public-management",
            "energies": "energy",
            "telecoms": "telecom",
            "sante": "health",
            "securite": "security",
            "justice": "justice",
            "formation": "education",
            "culture": "culture",
        }
        for key, sub in mapping.items():
            if key in url.lower():
                return sub
        return "news"
