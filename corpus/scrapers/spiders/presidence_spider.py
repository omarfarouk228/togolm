"""
Spider for presidence.gouv.tg — Togolese presidency website (Elementor/WordPress).

Collects news articles, communiqués, speeches from category pages.
Article URLs follow the WordPress date pattern: /YYYY/MM/DD/slug/
"""

import re
from urllib.parse import urljoin

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

# WordPress date-based article URL pattern
WP_DATE_URL_RE = re.compile(r"/\d{4}/\d{2}/\d{2}/.+/$")

CATEGORY_URLS = [
    # ── News & press ──────────────────────────────────────────────────────────
    "https://presidence.gouv.tg/category/news/",
    "https://presidence.gouv.tg/category/diplomatie/",
    "https://presidence.gouv.tg/category/economie-news",
    "https://presidence.gouv.tg/category/securite/",
    "https://presidence.gouv.tg/category/social/",
    "https://presidence.gouv.tg/category/audience/",
    "https://presidence.gouv.tg/category/visites-de-travail/",
    "https://presidence.gouv.tg/category/avis-et-annonces/conseil-des-ministres/",
    "https://presidence.gouv.tg/documents_cat/communique-de-presse/",
    # ── Additional categories (were missing → only 16 docs) ──────────────────
    "https://presidence.gouv.tg/category/discours/",
    "https://presidence.gouv.tg/category/interview/",
    "https://presidence.gouv.tg/category/allocution/",
    "https://presidence.gouv.tg/category/nomination/",
    "https://presidence.gouv.tg/category/cooperation/",
    "https://presidence.gouv.tg/category/sport/",
    "https://presidence.gouv.tg/category/culture/",
    "https://presidence.gouv.tg/category/education/",
    "https://presidence.gouv.tg/category/sante/",
    "https://presidence.gouv.tg/category/infrastructure/",
    "https://presidence.gouv.tg/category/agriculture/",
    "https://presidence.gouv.tg/documents_cat/",
    "https://presidence.gouv.tg/",
    # ── WordPress sitemaps ────────────────────────────────────────────────────
    "https://presidence.gouv.tg/post-sitemap.xml",
    "https://presidence.gouv.tg/wp-sitemap-posts-post-1.xml",
    "https://presidence.gouv.tg/wp-sitemap-posts-post-2.xml",
    "https://presidence.gouv.tg/wp-sitemap-posts-post-3.xml",
    "https://presidence.gouv.tg/sitemap.xml",
    "https://presidence.gouv.tg/sitemap_index.xml",
]


class PresidenceSpider(BaseTogoSpider):
    name = "presidence"
    source = "presidence.gouv.tg"
    category = "politics"
    language = "fr"

    start_urls = CATEGORY_URLS

    def parse(self, response):
        """Dispatch: sitemap XML or HTML listing/article page."""
        ct = response.headers.get("Content-Type", b"").decode().lower()
        if "xml" in ct or response.url.endswith(".xml"):
            yield from self._parse_sitemap(response)
        else:
            yield from self._parse_listing(response)

    def _parse_sitemap(self, response):
        """Extract article URLs from a WordPress sitemap."""
        response.selector.remove_namespaces()
        for loc in response.xpath("//loc/text()").getall():
            if loc.endswith(".xml"):
                yield scrapy.Request(loc, callback=self.parse)
            elif self._is_article_url(loc):
                yield scrapy.Request(loc, callback=self.parse_article, priority=10)

    def _parse_listing(self, response):
        """Parse a category/listing page: follow article links + pagination."""
        for href in response.css("a::attr(href)").getall():
            url = urljoin(response.url, href)
            if self._is_article_url(url):
                yield scrapy.Request(url, callback=self.parse_article, priority=10)

        # WordPress pagination: /page/2/, /page/3/, …
        next_page = response.css("a.next::attr(href), a[rel='next']::attr(href)").get()
        if next_page:
            yield scrapy.Request(urljoin(response.url, next_page), callback=self._parse_listing)

    def parse_article(self, response):
        title = response.css("h1::text").get("").strip()
        if not title:
            return

        # Elementor single-post template: collect all widget text containers
        # that sit inside the single-post template wrapper
        texts = response.css(
            "[class*='elementor-location-single'] .elementor-widget-container p::text, "
            "[class*='elementor-location-single'] .elementor-widget-container li::text, "
            "[class*='elementor-location-single'] .elementor-widget-container h2::text, "
            "[class*='elementor-location-single'] .elementor-widget-container h3::text"
        ).getall()

        raw_content = " ".join(t.strip() for t in texts if t.strip())

        # Broader fallback
        if not raw_content or len(raw_content.split()) < 20:
            raw_content = " ".join(response.css(".elementor-widget-container p::text").getall())

        if not raw_content or len(raw_content.split()) < 20:
            return

        published_at = (
            response.css("time::attr(datetime)").get("")
            or response.css("meta[property='article:published_time']::attr(content)").get("")
            or ""
        )

        # Infer subcategory from URL path (e.g. /category/diplomatie/ → diplomatie)
        subcategory = ""
        if "/category/" in response.url:
            subcategory = response.url.split("/category/")[-1].strip("/").split("/")[0]

        yield self.make_document(
            response=response,
            title=title,
            raw_content=raw_content,
            subcategory=subcategory,
            published_at=published_at[:10] if published_at else None,
            metadata={"word_count": len(raw_content.split())},
        )

    def _is_article_url(self, url: str) -> bool:
        if "presidence.gouv.tg" not in url:
            return False
        path = url.split("presidence.gouv.tg")[-1]
        return bool(WP_DATE_URL_RE.search(path))
