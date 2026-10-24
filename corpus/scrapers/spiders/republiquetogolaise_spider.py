"""
Spider for republiquetogolaise.com — Togolese government & politics news.

Joomla CMS with K2 component. Article URLs follow:
  /{category}/{ddmm}-{id}-{slug}
  e.g. /gestion-publique/3112-11462-conseil-des-ministres-du-30-decembre-2025

Articles are discovered from the JMap sitemap (~12,000 articles), the homepage
and category listing pages (pagination via Joomla's ?start=N offset).
"""

import re
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

DOMAIN = "www.republiquetogolaise.tg"
SITEMAP_URL = f"https://{DOMAIN}/index.php?option=com_jmap&view=sitemap&format=xml"
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
    "gouvernance-economique",
    "sante",
    "agro",
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
    # Sections of the .tg portal (2026), topics as corpus categories so the
    # category filter (category OR subcategory) finds them.
    "gouvernance-economique": "economy",
    "sante": "health",
    "agro": "agriculture",
    "formation": "education",
    "tic": "technologies",
    "cedeao": "international",
}


class RepubliquetogolaisSpider(BaseTogoSpider):
    name = "republiquetogolaise"
    source = "republiquetogolaise.tg"
    category = "press"
    language = "fr"

    start_urls = [SITEMAP_URL, BASE_URL] + [f"{BASE_URL}/{cat}" for cat in CATEGORIES]

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    def parse(self, response):
        if response.url == SITEMAP_URL:
            response.selector.remove_namespaces()
            for url in response.xpath("//loc/text()").getall():
                if self._is_article_url(url.strip()):
                    yield scrapy.Request(url.strip(), callback=self.parse_article)
            return
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

        # Joomla K2: the text is split between the intro and the full text,
        # either of which can be empty (on the .tg portal the whole article is
        # often in itemIntroText). Taking the first non-empty element picked
        # an empty itemFullText, and the paragraph fallback dropped link text.
        raw_content = " ".join(
            self.html_to_text(part)
            for part in response.css("div.itemIntroText, div.itemFullText").getall()
        ).strip()
        if len(raw_content.split()) < 30:
            body_html = response.css("div.item-page").get("") or response.css("article").get("")
            raw_content = self.html_to_text(body_html) if body_html else ""

        if not raw_content or len(raw_content.split()) < 30:
            paragraphs = response.css(
                "div.itemFullText p::text, div.itemBody p::text, article p::text"
            ).getall()
            raw_content = " ".join(p.strip() for p in paragraphs if p.strip())

        if not raw_content or len(raw_content.split()) < 30:
            return

        published_at = self.extract_published_at(response, ".itemDateCreated")

        yield self.make_document(
            response=response,
            title=title,
            raw_content=raw_content,
            subcategory=self._infer_subcategory(response.url),
            published_at=published_at,
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
