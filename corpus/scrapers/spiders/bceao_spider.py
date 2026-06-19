"""
Spider for bceao.int — Banque Centrale des États de l'Afrique de l'Ouest.

Targets only Togo-related pages and publications to avoid crawling the full
international site. Entry points: Togo country page, publications filtered
by country, monetary statistics, and annual reports.
"""

from urllib.parse import urljoin, urlparse

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

_SKIP_EXT = {".jpg", ".jpeg", ".png", ".gif", ".svg", ".zip", ".css", ".js", ".woff"}
_SKIP_PATH = {"/feed/", "/login/", "/admin/", "/search/"}

# Only follow links that are Togo-specific or relevant publications
_TOGO_PATHS = {"/togo", "pays/togo", "country/togo", "/TG/", "/tg/"}


class BceaoSpider(BaseTogoSpider):
    name = "bceao"
    source = "bceao.int"
    category = "economy"
    language = "fr"

    start_urls = [
        "https://www.bceao.int/fr/pays/togo",
        "https://www.bceao.int/fr/publications/liste?field_pays_target_id=15",  # Togo ID
        "https://www.bceao.int/fr/content/taux-directeurs-de-la-bceao",
        "https://www.bceao.int/fr/publications/liste?type=rapport",
        "https://www.bceao.int/fr/statistiques/liste",
        "https://www.bceao.int/fr/content/reglementation",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 2.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "ROBOTSTXT_OBEY": True,
        "DEPTH_LIMIT": 3,
        "HTTPERROR_ALLOWED_CODES": [403, 404],
    }

    def parse(self, response):
        yield from self._parse_page(response)

    def _parse_page(self, response):
        doc = self._extract(response)
        if doc:
            yield doc
        for href in response.css("a::attr(href)").getall():
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            url = urljoin(response.url, href)
            if "bceao.int" not in urlparse(url).netloc:
                continue
            if self._skip(url):
                continue
            if not self._is_relevant(url):
                continue
            yield scrapy.Request(url, callback=self._parse_page, errback=self._err)

    def _is_relevant(self, url: str) -> bool:
        """Only follow links that are Togo-specific or general BCEAO publications."""
        path = urlparse(url).path.lower()
        url_lower = url.lower()
        # Allow Togo-tagged pages
        if any(t in url_lower for t in _TOGO_PATHS):
            return True
        # Allow publications, statistics, regulations, reports
        relevant_sections = ["/publications/", "/statistiques/", "/reglementation/",
                             "/rapports/", "/rapport-", "/notes-", "/bulletin-",
                             "/communique", "/decision", "/instruction"]
        return any(s in path for s in relevant_sections)

    def _extract(self, response):
        title = (
            response.css("h1.page-title::text").get()
            or response.css("h1::text").get()
            or response.css("title::text").get("").split("|")[0].split("–")[0]
        ).strip()
        if not title or len(title) < 5:
            return None
        raw = (
            self._text(response, ".field--name-body p, .field--name-body li, .field--name-body h2")
            or self._text(response, ".field-items p, .field-items li")
            or self._text(response, ".view-content p, .view-content li")
            or self._text(response, "article p, article li, article h2")
            or self._text(response, "main p, main li, .content p")
        )
        if not raw or len(raw.split()) < 30:
            return None
        return self.make_document(response, title, raw)

    def _text(self, r, sel):
        parts = r.css(f"{sel}::text").getall()
        return " ".join(p.strip() for p in parts if p.strip())

    def _skip(self, url):
        path = urlparse(url).path.lower()
        return any(path.endswith(e) for e in _SKIP_EXT) or any(s in path for s in _SKIP_PATH)

    def _err(self, f):
        self.logger.debug(f"Failed: {f.request.url}")
