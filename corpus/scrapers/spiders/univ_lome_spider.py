"""Spider for univ-lome.tg — Université de Lomé."""

from urllib.parse import urljoin, urlparse

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

_SKIP_EXT = {".jpg", ".jpeg", ".png", ".gif", ".svg", ".pdf", ".zip", ".css", ".js", ".woff"}
_SKIP_PATH = {"/feed/", "/wp-admin/", "/wp-content/", "/login/", "/author/", "/tag/"}


class UnivLomeSpider(BaseTogoSpider):
    name = "univ_lome"
    source = "univ-lome.tg"
    category = "education"
    language = "fr"

    start_urls = [
        "https://univ-lome.tg/sitemap.xml",
        "https://univ-lome.tg/wp-sitemap.xml",
        "https://univ-lome.tg/",
        "https://univ-lome.tg/actualites/",
        "https://univ-lome.tg/formations/",
        "https://univ-lome.tg/recherche/",
        "https://univ-lome.tg/facultes/",
        "https://univ-lome.tg/ecoles/",
        "https://univ-lome.tg/instituts/",
        "https://univ-lome.tg/concours/",
        "https://univ-lome.tg/bourses/",
    ]

    custom_settings = {
        "DOWNLOAD_DELAY": 1.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "ROBOTSTXT_OBEY": True,
        "DEPTH_LIMIT": 4,
        "HTTPERROR_ALLOWED_CODES": [403, 404],
    }

    def parse(self, response):
        ct = response.headers.get("Content-Type", b"").decode().lower()
        if "xml" in ct or response.url.endswith(".xml"):
            yield from self._parse_sitemap(response)
        else:
            yield from self._parse_page(response)

    def _parse_sitemap(self, response):
        response.selector.remove_namespaces()
        for loc in response.xpath("//loc/text()").getall():
            if loc.endswith(".xml"):
                yield scrapy.Request(loc, callback=self.parse, errback=self._err)
            elif not self._skip(loc):
                yield scrapy.Request(loc, callback=self._parse_page, errback=self._err, priority=10)

    def _parse_page(self, response):
        doc = self._extract(response)
        if doc:
            yield doc
        for href in response.css("a::attr(href)").getall():
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            url = urljoin(response.url, href)
            if "univ-lome.tg" not in urlparse(url).netloc:
                continue
            if self._skip(url):
                continue
            yield scrapy.Request(url, callback=self._parse_page, errback=self._err)

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
            or self._text(response, ".elementor-widget-container p, .elementor-widget-container li")
            or self._text(response, "article p, article li, article h2")
            or self._text(response, "main p, main li, .content p, #content p")
        )
        if not raw or len(raw.split()) < 30:
            return None
        pub = (
            response.css("time::attr(datetime)").get()
            or response.css("meta[property='article:published_time']::attr(content)").get()
            or ""
        )
        return self.make_document(response, title, raw, published_at=pub[:10] if pub else None)

    def _text(self, r, sel):
        parts = r.css(f"{sel}::text").getall()
        return " ".join(p.strip() for p in parts if p.strip())

    def _skip(self, url):
        path = urlparse(url).path.lower()
        return any(path.endswith(e) for e in _SKIP_EXT) or any(s in path for s in _SKIP_PATH)

    def _err(self, f):
        self.logger.debug(f"Failed: {f.request.url}")
