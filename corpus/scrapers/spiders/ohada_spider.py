"""
Spider for ohada.org — Organisation pour l'Harmonisation en Afrique du Droit des Affaires.

Targets the OHADA Uniform Acts (Actes Uniformes) and related legal texts that
apply to all OHADA member states including Togo. Does not crawl the full site.
"""

from urllib.parse import urljoin, urlparse

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

_SKIP_EXT = {".jpg", ".jpeg", ".png", ".gif", ".svg", ".zip", ".css", ".js"}
_SKIP_PATH = {"/feed/", "/wp-admin/", "/wp-content/", "/login/"}


class OhadaSpider(BaseTogoSpider):
    name = "ohada"
    source = "ohada.org"
    category = "legal"
    language = "fr"

    start_urls = [
        # Actes Uniformes — the core OHADA legislation
        "https://www.ohada.com/actes-uniformes.html",
        "https://www.ohada.org/index.php/actes-uniformes",
        "https://ohada.org/actes-uniformes",
        # Jurisprudence CCJA
        "https://www.ohada.com/jurisprudence-ccja.html",
        # Traité OHADA
        "https://www.ohada.com/traite.html",
        # Règlements
        "https://www.ohada.com/reglements.html",
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
            parsed = urlparse(url)
            if parsed.netloc and "ohada" not in parsed.netloc:
                continue
            if self._skip(url):
                continue
            if not self._is_legal_content(url):
                continue
            yield scrapy.Request(url, callback=self._parse_page, errback=self._err)

    def _is_legal_content(self, url: str) -> bool:
        path = urlparse(url).path.lower()
        legal_sections = [
            "/actes-uniformes", "/acte-uniforme", "/traite", "/reglements",
            "/jurisprudence", "/doctrine", "/legislation", "/textes",
            "/droit-uniforme", "/droit-des-affaires",
        ]
        return any(s in path for s in legal_sections)

    def _extract(self, response):
        title = (
            response.css("h1.entry-title::text").get()
            or response.css("h1::text").get()
            or response.css(".page-title::text").get()
            or response.css("title::text").get("").split("|")[0].split("–")[0]
        ).strip()
        if not title or len(title) < 5:
            return None
        raw = (
            self._text(response, ".entry-content p, .entry-content li, .entry-content h2, .entry-content h3")
            or self._text(response, ".post-content p, .post-content li")
            or self._text(response, ".field--name-body p, .field--name-body li")
            or self._text(response, "article p, article li, article h2")
            or self._text(response, "main p, main li, .content p, #content p")
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
