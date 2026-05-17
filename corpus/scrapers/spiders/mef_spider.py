"""
Spider for mef.gouv.tg — Ministère de l'Économie et des Finances du Togo.

Crawls budget documents, economic reports, finance laws, and ministry publications
from the official Togolese Ministry of Economy and Finance website.

The site uses a different domain from finances.gouv.tg (which covers general
financial administration), while mef.gouv.tg focuses on macro-economic data,
budget laws, and ministry-level economic policy documents.
"""

import re
from urllib.parse import urljoin

import scrapy

from scrapers.spiders.base_spider import BaseTogoSpider

DOCUMENT_EXTENSIONS = re.compile(r"\.(pdf|doc|docx|xls|xlsx)$", re.IGNORECASE)

ENTRY_URLS = [
    "https://mef.gouv.tg/",
    "https://mef.gouv.tg/budgets/",
    "https://mef.gouv.tg/rapports/",
    "https://mef.gouv.tg/publications/",
    "https://mef.gouv.tg/lois-finances/",
    "https://mef.gouv.tg/actualites/",
]

EXCLUDED_PATHS = [
    "/wp-admin/", "/wp-content/", "/wp-login",
    "/feed/", "/tag/", "/author/", "/#",
    "/category/", "/search/",
]

# Slugs must have at least 8 characters and contain a hyphen
SLUG_RE = re.compile(r"/[a-z][a-z0-9\-]{7,}/?$")


class MefSpider(BaseTogoSpider):
    name = "mef"
    source = "mef.gouv.tg"
    category = "economy"
    language = "fr"

    start_urls = ENTRY_URLS

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    def parse(self, response):
        ct = response.headers.get("Content-Type", b"").decode()

        # Handle sitemap
        if "xml" in ct or response.url.endswith(".xml"):
            response.selector.remove_namespaces()
            for url in response.xpath("//loc/text()").getall():
                if self._is_content_url(url):
                    yield scrapy.Request(url, callback=self.parse, priority=10)
            return

        # Try WordPress sitemap first
        sitemap_url = urljoin(response.url, "/wp-sitemap.xml")
        if response.url in ENTRY_URLS:
            yield scrapy.Request(sitemap_url, callback=self.parse, dont_filter=True, priority=20)

        # Follow internal links
        for href in response.css("a::attr(href)").getall():
            url = urljoin(response.url, href)
            if not url.startswith("http"):
                continue
            # Skip binary documents (PDF/XLS) for now — no parser in base spider
            if DOCUMENT_EXTENSIONS.search(url):
                continue
            if self._is_content_url(url):
                yield scrapy.Request(url, callback=self.parse_page, priority=10)

    def parse_page(self, response):
        title = (
            response.css("h1::text").get("") or
            response.css("h1 *::text").get("") or
            response.css("title::text").get("").split("|")[0]
        ).strip()

        if not title or len(title) < 5:
            return

        paragraphs = [
            p.strip()
            for p in response.css("p::text, p *::text, li::text, li *::text").getall()
            if p.strip() and len(p.strip()) > 15
        ]
        raw_content = " ".join(paragraphs)

        if not raw_content or len(raw_content.split()) < 40:
            body_html = response.css("main, article, .content, .entry-content, #content").get("")
            raw_content = self.html_to_text(body_html) if body_html else ""

        if not raw_content or len(raw_content.split()) < 40:
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

        # Follow pagination and sub-links from this page
        for href in response.css("a::attr(href)").getall():
            url = urljoin(response.url, href)
            if self._is_content_url(url) and not DOCUMENT_EXTENSIONS.search(url):
                yield scrapy.Request(url, callback=self.parse_page, priority=5)

    def _is_content_url(self, url: str) -> bool:
        if "mef.gouv.tg" not in url:
            return False
        if any(e in url for e in EXCLUDED_PATHS):
            return False
        path = url.split("mef.gouv.tg")[-1].rstrip("/")
        if not path or path == "/":
            return False
        return bool(SLUG_RE.search(path + "/"))

    def _infer_subcategory(self, url: str) -> str:
        mapping = {
            "budget": "budget",
            "rapport": "report",
            "publication": "publication",
            "loi-finance": "loi-finances",
            "actualite": "actualite",
            "douane": "customs",
            "impot": "tax",
            "investissement": "investment",
            "dette": "debt",
        }
        for key, sub in mapping.items():
            if key in url.lower():
                return sub
        return "economy"
