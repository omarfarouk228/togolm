"""
Spider for republiquetogolaise.com — Togolese government & politics news.

Joomla CMS with K2 component. Article URLs follow:
  /{category}/{ddmm}-{id}-{slug}
  e.g. /gestion-publique/3112-11462-conseil-des-ministres-du-30-decembre-2025

Articles are discovered from the homepage and category listing pages.
Pagination via Joomla's ?start=N offset parameter.
"""

import re
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

DOMAIN = "www.republiquetogolaise.com"
BASE_URL = f"https://{DOMAIN}"

CATEGORIES = [
    "gestion-publique",
    "politique",
    "finances-publiques",
    "justice",
    "education",
    "energies",
    "economie-bleue",
    "transports",
    "culture",
    "securite",
    "social",
]

# Joomla article URL: /{category}/{ddmm}-{5+digit-id}-{slug}
ARTICLE_RE = re.compile(r"^/[a-z][a-z0-9\-]+/\d{4}-\d{4,}-[a-z0-9\-]{3,}$")

EXCLUDED = [
    "/component/",
    "/administrator/",
    "/templates/",
    "/media/",
    "/plugins/",
    "/modules/",
    "mailto:",
    "javascript:",
    "#",
    "/feed",
    "?format=feed",
    "/print/",
    "?tmpl=",
]

# Joomla listing page size (articles per page)
PAGE_SIZE = 10
MAX_PAGES = 30

SUBCATEGORY_MAP = {
    "gestion-publique": "governance",
    "politique": "politics",
    "finances-publiques": "economy",
    "justice": "legal",
    "education": "education",
    "energies": "economy",
    "economie-bleue": "economy",
    "transports": "economy",
    "culture": "culture",
    "securite": "politics",
    "social": "society",
}


class RepubliquetogolaisSpider(BaseTogoSpider):
    name = "republiquetogolaise"
    source = "republiquetogolaise.com"
    category = "press"
    language = "fr"

    start_urls = [BASE_URL] + [f"{BASE_URL}/{cat}" for cat in CATEGORIES]

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    def parse(self, response):
        # Collect article links from listing page
        articles_found = 0
        for href in response.css("a::attr(href)").getall():
            url = urljoin(response.url, href)
            if self._is_article_url(url):
                yield scrapy.Request(url, callback=self.parse_article, priority=10)
                articles_found += 1

        # Joomla pagination: ?start=N
        if articles_found > 0:
            parsed = urlparse(response.url)
            qs = parse_qs(parsed.query)
            current_start = int(qs.get("start", [0])[0])
            current_page = current_start // PAGE_SIZE
            if current_page < MAX_PAGES:
                next_start = current_start + PAGE_SIZE
                qs["start"] = [str(next_start)]
                next_url = urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))
                yield scrapy.Request(next_url, callback=self.parse, priority=5)

    def parse_article(self, response):
        # Joomla K2: itemTitle / article h1
        title = (
            response.css("h1.itemTitle::text").get("")
            or response.css("h1.page-header::text").get("")
            or response.css("h1::text").get("")
            or response.css("meta[property='og:title']::attr(content)").get("")
        ).strip()

        if not title or len(title) < 5:
            return

        # Joomla K2 content selectors
        body_html = (
            response.css("div.itemFullText").get("")
            or response.css("div.itemBody").get("")
            or response.css("div.itemIntroText").get("")
            or response.css("div.item-page").get("")
            or response.css("article").get("")
        )
        raw_content = self.html_to_text(body_html) if body_html else ""

        if not raw_content or len(raw_content.split()) < 30:
            paragraphs = response.css(
                "div.itemFullText p::text, div.itemBody p::text, article p::text"
            ).getall()
            raw_content = " ".join(p.strip() for p in paragraphs if p.strip())

        if not raw_content or len(raw_content.split()) < 30:
            return

        # Date: Joomla K2 span, meta tag, or time element
        published_at = (
            response.css("span.itemDateCreated::text").get("")
            or response.css("time::attr(datetime)").get("")
            or response.css("meta[property='article:published_time']::attr(content)").get("")
            or ""
        )
        # Normalize French date "31 Décembre 2025" → handled by ingestor
        published_at = published_at.strip()

        yield self.make_document(
            response=response,
            title=title,
            raw_content=raw_content,
            subcategory=self._infer_subcategory(response.url),
            published_at=published_at[:10] if published_at else None,
            metadata={"word_count": len(raw_content.split())},
        )

    def _is_article_url(self, url: str) -> bool:
        if DOMAIN not in url:
            return False
        if any(e in url for e in EXCLUDED):
            return False
        path = urlparse(url).path.rstrip("/")
        return bool(ARTICLE_RE.match(path))

    def _infer_subcategory(self, url: str) -> str:
        path = urlparse(url).path.lower()
        for cat, sub in SUBCATEGORY_MAP.items():
            if f"/{cat}/" in path or path.startswith(f"/{cat}"):
                return sub
        return "news"
