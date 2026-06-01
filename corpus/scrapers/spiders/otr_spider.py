"""
Spider for otr.tg — Office Togolais des Recettes (Togolese Revenue Authority).

Joomla site. Article URLs follow: /index.php/fr/{id}-{slug}.html
RSS feed exposes 300+ fiscal, tax, and customs articles.
Covers: tax law, fiscal procedures, customs, taxpayer sensitization.
"""

import re
from urllib.parse import urljoin

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

# Joomla article: /index.php/fr/NNN-slug.html
ARTICLE_URL_RE = re.compile(r"/index\.php/fr/\d+-[a-z]")

RSS_FEEDS = [
    "https://www.otr.tg/index.php/fr/?format=feed&type=rss",
    "https://www.otr.tg/index.php/fr/?format=feed&type=atom",
]

ENTRY_URLS = [
    "https://www.otr.tg/index.php/fr/",
    "https://www.otr.tg/index.php/fr/documentation.html",
    "https://www.otr.tg/index.php/fr/fiscalite.html",
    "https://www.otr.tg/index.php/fr/douanes.html",
    "https://www.otr.tg/index.php/fr/legislation.html",
]

EXCLUDED_PATHS = [
    "/administrator/", "/cache/", "/templates/", "/components/", "/modules/",
    "/wp-content/", "#", "mailto:", "javascript:", "?format=",
]


class OtrSpider(BaseTogoSpider):
    name = "otr"
    source = "otr.tg"
    category = "legal"
    language = "fr"

    start_urls = RSS_FEEDS + ENTRY_URLS

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "USER_AGENT": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    def parse(self, response):
        ct = response.headers.get("Content-Type", b"").decode()

        if "xml" in ct or "rss" in ct or "atom" in ct:
            yield from self._parse_feed(response)
            return

        for href in response.css("a::attr(href)").getall():
            url = urljoin(response.url, href)
            if self._is_article_url(url):
                yield scrapy.Request(url, callback=self.parse_article, priority=10)

        next_links = response.css(
            "a.pagenav::attr(href), .pagination a::attr(href), li.next a::attr(href)"
        ).getall()
        for href in next_links:
            url = urljoin(response.url, href)
            if "otr.tg" in url:
                yield scrapy.Request(url, callback=self.parse, priority=5)

    def _parse_feed(self, response):
        response.selector.remove_namespaces()
        links = response.xpath("//item/link/text()").getall()
        links += response.xpath("//entry/link/@href").getall()
        for url in links:
            url = url.strip()
            if self._is_article_url(url):
                yield scrapy.Request(url, callback=self.parse_article, priority=10)

    def parse_article(self, response):
        # OTR Joomla: article title is in h3.item_title with each word in a child span
        title_parts = response.css("h3.item_title *::text").getall()
        title = " ".join(t.strip() for t in title_parts if t.strip())
        if not title:
            title = (
                response.css("h1::text").get("") or
                response.css("title::text").get("").split(" - ")[0]
            ).strip()
        # Exclude the generic site header
        if title.startswith("..::") or title == "OFFICE TOGOLAIS DES RECETTES":
            title = ""

        if not title or len(title) < 5:
            return

        # Joomla: article body is in .item_fulltext or .content-inner
        body_html = response.css(".item_fulltext, .content-inner").get("")
        raw_content = self.html_to_text(body_html) if body_html else ""

        if not raw_content or len(raw_content.split()) < 30:
            paragraphs = response.css("p::text").getall()
            raw_content = " ".join(
                p.strip() for p in paragraphs
                if len(p.strip()) > 20
            )

        if not raw_content or len(raw_content.split()) < 30:
            return

        published_at = (
            response.css("time::attr(datetime)").get("") or
            response.css("meta[property='article:published_time']::attr(content)").get("") or
            response.css(".article-info time::text, .published::text").get("") or
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
        if "otr.tg" not in url:
            return False
        if any(e in url for e in EXCLUDED_PATHS):
            return False
        path = url.split("otr.tg")[-1]
        return bool(ARTICLE_URL_RE.search(path))

    def _infer_subcategory(self, url: str) -> str:
        url_lower = url.lower()
        if "douane" in url_lower or "customs" in url_lower:
            return "customs"
        if "fiscalit" in url_lower or "impot" in url_lower or "taxe" in url_lower:
            return "fiscal"
        if "documentation" in url_lower or "legislation" in url_lower:
            return "legislation"
        if "sensibilisation" in url_lower or "formation" in url_lower:
            return "outreach"
        return "revenue"
