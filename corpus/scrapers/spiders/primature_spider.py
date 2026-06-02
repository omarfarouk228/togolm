"""
Spider for presidenceduconseil.gouv.tg — Primature (Premier Ministère) du Togo.

Collecte toutes les pages du site : actualités, communiqués, discours,
décisions du Conseil des Ministres, pages institutionnelles, etc.
"""

import re
from urllib.parse import urljoin, urlparse

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

BASE_DOMAIN = "presidenceduconseil.gouv.tg"
BASE_URL = f"https://{BASE_DOMAIN}/"

# WordPress date-based article URL pattern
WP_DATE_URL_RE = re.compile(r"/\d{4}/\d{2}/\d{2}/.+")

# Extensions to skip (non-text resources)
SKIP_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".svg", ".pdf",
                   ".zip", ".doc", ".docx", ".xls", ".xlsx", ".mp4",
                   ".mp3", ".avi", ".css", ".js", ".ico", ".woff", ".woff2"}


def _is_skippable_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in SKIP_EXTENSIONS)


class PrimatureSpider(BaseTogoSpider):
    """Scrape all content from presidenceduconseil.gouv.tg (Primature du Togo)."""

    name = "primature"
    source = "presidenceduconseil.gouv.tg"
    category = "government"
    language = "fr"

    start_urls = [BASE_URL]

    custom_settings = {
        "DOWNLOAD_DELAY": 1.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "ROBOTSTXT_OBEY": True,
        "DEPTH_LIMIT": 6,
    }

    def parse(self, response):
        """Follow all internal links from any page."""
        # Try to extract content from this page first
        yield from self._try_extract(response)

        # Follow all internal links
        for href in response.css("a::attr(href)").getall():
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
                continue
            url = urljoin(response.url, href)
            if not self._is_internal(url):
                continue
            if _is_skippable_url(url):
                continue
            yield scrapy.Request(
                url,
                callback=self.parse,
                errback=self._errback,
                dont_filter=False,
            )

        # WordPress pagination
        next_page = response.css(
            "a.next::attr(href), a[rel='next']::attr(href), "
            ".nav-previous a::attr(href), .pagination a::attr(href)"
        ).get()
        if next_page:
            url = urljoin(response.url, next_page)
            if self._is_internal(url):
                yield scrapy.Request(url, callback=self.parse, errback=self._errback)

    def _try_extract(self, response):
        """Extract document content from the current page if it has sufficient text."""
        title = (
            response.css("h1.entry-title::text").get()
            or response.css("h1::text").get()
            or response.css("title::text").get()
            or ""
        ).strip()

        # Strip site name suffix (e.g. " - Primature du Togo")
        title = re.sub(r"\s*[-|–]\s*(Primature|Gouvernement|Togo).*$", "", title,
                       flags=re.IGNORECASE).strip()

        if not title or len(title) < 5:
            return

        # Try content selectors in priority order (WordPress/Elementor/generic)
        raw_text = (
            self._extract_wp_content(response)
            or self._extract_elementor_content(response)
            or self._extract_generic_content(response)
        )

        if not raw_text or len(raw_text.split()) < 40:
            return

        published_at = (
            response.css("time::attr(datetime)").get()
            or response.css("meta[property='article:published_time']::attr(content)").get()
            or ""
        )

        subcategory = self._infer_subcategory(response.url, title)

        yield self.make_document(
            response=response,
            title=title,
            raw_content=raw_text,
            subcategory=subcategory,
            published_at=published_at[:10] if published_at else None,
            metadata={
                "word_count": len(raw_text.split()),
                "document_type": subcategory,
            },
        )

    def _extract_wp_content(self, response) -> str:
        """Standard WordPress article content."""
        texts = response.css(
            ".entry-content p::text, .entry-content li::text, "
            ".entry-content h2::text, .entry-content h3::text, "
            ".entry-content h4::text, .post-content p::text, "
            ".post-content li::text"
        ).getall()
        return " ".join(t.strip() for t in texts if t.strip())

    def _extract_elementor_content(self, response) -> str:
        """Elementor page builder content (used by many Togolese gov sites)."""
        texts = response.css(
            ".elementor-widget-container p::text, "
            ".elementor-widget-container li::text, "
            ".elementor-widget-container h2::text, "
            ".elementor-widget-container h3::text, "
            ".elementor-text-editor p::text"
        ).getall()
        return " ".join(t.strip() for t in texts if t.strip())

    def _extract_generic_content(self, response) -> str:
        """Fallback: main/article/section tag content."""
        for sel in ("article", "main", ".content", "#content", ".page-content"):
            texts = response.css(f"{sel} p::text, {sel} li::text, {sel} h2::text").getall()
            result = " ".join(t.strip() for t in texts if t.strip())
            if len(result.split()) >= 40:
                return result
        return ""

    def _infer_subcategory(self, url: str, title: str) -> str:
        url_low = url.lower()
        title_low = title.lower()
        if any(k in url_low or k in title_low
               for k in ["conseil-des-ministres", "conseil des ministres"]):
            return "conseil_ministres"
        if any(k in url_low or k in title_low
               for k in ["discours", "allocution", "speech"]):
            return "discours"
        if any(k in url_low or k in title_low
               for k in ["communique", "communiqué", "press"]):
            return "communique"
        if any(k in url_low or k in title_low
               for k in ["actualit", "news", "article"]):
            return "actualite"
        if WP_DATE_URL_RE.search(url):
            return "actualite"
        return "institutionnel"

    def _is_internal(self, url: str) -> bool:
        return BASE_DOMAIN in urlparse(url).netloc

    def _errback(self, failure):
        self.logger.warning(f"Request failed: {failure.request.url} — {failure.value}")
