"""
Spider for e-documenter.uemoa.int — bibliothèque documentaire de l'UEMOA.

Searches and indexes documents relevant to Togo: directives, règlements,
décisions, rapports involving UEMOA member state Togo.
"""

from urllib.parse import urljoin, urlparse

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

_SKIP_EXT = {".jpg", ".jpeg", ".png", ".gif", ".svg", ".zip", ".css", ".js"}
_SKIP_PATH = {"/login/", "/register/", "/admin/", "/feed/"}


class UemoaSpider(BaseTogoSpider):
    name = "uemoa"
    source = "e-documenter.uemoa.int"
    category = "legal"
    language = "fr"

    start_urls = [
        # Document search filtered for Togo
        "https://e-documenter.uemoa.int/index.php/component/search/?searchword=togo",
        "https://e-documenter.uemoa.int/index.php/documents",
        "https://e-documenter.uemoa.int/index.php/publications",
        "https://e-documenter.uemoa.int/",
        # Also try direct UEMOA domain
        "https://www.uemoa.int/fr/publications",
        "https://www.uemoa.int/fr/actualites",
        "https://www.uemoa.int/fr/textes-legislatifs-et-reglementaires",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 2.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "ROBOTSTXT_OBEY": True,
        "DEPTH_LIMIT": 3,
        "HTTPERROR_ALLOWED_CODES": [403, 404],
    }

    _ALLOWED_DOMAINS = {"e-documenter.uemoa.int", "www.uemoa.int", "uemoa.int"}

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
            if urlparse(url).netloc not in self._ALLOWED_DOMAINS:
                continue
            if self._skip(url):
                continue
            yield scrapy.Request(url, callback=self._parse_page, errback=self._err)

    def _extract(self, response):
        title = (
            response.css("h1.page-title::text").get()
            or response.css("h1.entry-title::text").get()
            or response.css("h1::text").get()
            or response.css("title::text").get("").split("|")[0].split("–")[0]
        ).strip()
        if not title or len(title) < 5:
            return None
        raw = (
            self._text(response, ".item-page p, .item-page li, .item-page h2")
            or self._text(response, ".field--name-body p, .field--name-body li")
            or self._text(response, ".entry-content p, .entry-content li")
            or self._text(response, "article p, article li")
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
