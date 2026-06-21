"""
Spider for inseed.tg — Institut National de la Statistique et des Études Économiques et Démographiques.

Collects statistical news, reports, and publications.
Site uses Penci WordPress theme — content lives in <main> p tags.
"""

import re
from urllib.parse import urljoin

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

WP_SLUG_RE = re.compile(r"/[a-z0-9][a-z0-9\-]{7,}/$")

LISTING_URLS = [
    # ── Core sections ─────────────────────────────────────────────────────────
    "https://inseed.tg/",
    "https://inseed.tg/actualites/",
    "https://inseed.tg/annuaires/",
    # ── Publications & reports (were missing → only 90 docs) ─────────────────
    "https://inseed.tg/publications/",
    "https://inseed.tg/rapports/",
    "https://inseed.tg/enquetes/",
    "https://inseed.tg/recensement/",
    "https://inseed.tg/note-dinformation/",
    "https://inseed.tg/bulletin/",
    "https://inseed.tg/categories/emploi/",
    "https://inseed.tg/categories/demographie/",
    "https://inseed.tg/categories/economie/",
    "https://inseed.tg/categories/prix/",
    "https://inseed.tg/categories/agriculture/",
    "https://inseed.tg/categories/commerce/",
    "https://inseed.tg/donnees/",
    "https://inseed.tg/indicateurs/",
    # ── WordPress sitemaps ────────────────────────────────────────────────────
    "https://inseed.tg/post-sitemap.xml",
    "https://inseed.tg/wp-sitemap.xml",
    "https://inseed.tg/wp-sitemap-posts-post-1.xml",
    "https://inseed.tg/sitemap.xml",
    "https://inseed.tg/sitemap_index.xml",
]


class InseedSpider(BaseTogoSpider):
    name = "inseed"
    source = "inseed.tg"
    category = "economy"
    language = "fr"

    start_urls = LISTING_URLS

    def parse(self, response):
        ct = response.headers.get("Content-Type", b"").decode().lower()
        if "xml" in ct or response.url.endswith(".xml"):
            yield from self._parse_sitemap(response)
        else:
            yield from self._parse_listing(response)

    def _parse_sitemap(self, response):
        """Extract URLs from a WordPress sitemap."""
        response.selector.remove_namespaces()
        for loc in response.xpath("//loc/text()").getall():
            if loc.endswith(".xml"):
                yield scrapy.Request(loc, callback=self.parse)
            elif self._is_article_url(loc):
                yield scrapy.Request(loc, callback=self.parse_article, priority=10)

    def _parse_listing(self, response):
        for href in response.css("a::attr(href)").getall():
            url = urljoin(response.url, href)
            if self._is_article_url(url):
                yield scrapy.Request(url, callback=self.parse_article, priority=10)

        # WordPress pagination
        next_page = response.css("a.next::attr(href), a[rel='next']::attr(href)").get()
        if next_page:
            yield scrapy.Request(urljoin(response.url, next_page), callback=self._parse_listing)

    def parse_article(self, response):
        # Extract title from breadcrumb or penci-single heading
        title = (
            response.css("[class*=penci-single] h1::text").get("")
            or response.css("[class*=penci-single] h2.title::text").get("")
            or
            # Derive from the breadcrumb last item
            response.css(".breadcrumb span:last-child::text").get("")
            or response.css("title::text").get("").split("|")[0]
        ).strip()

        if not title or len(title) < 5:
            return

        # Soledad/Penci theme: article content is in .entry-content
        paragraphs = response.css(".entry-content p::text, .entry-content p *::text").getall()
        raw_content = " ".join(p.strip() for p in paragraphs if p.strip())

        if not raw_content or len(raw_content.split()) < 20:
            return

        published_at = (
            response.css("time::attr(datetime)").get("")
            or response.css("meta[property='article:published_time']::attr(content)").get("")
            or ""
        )

        yield self.make_document(
            response=response,
            title=title,
            raw_content=raw_content,
            subcategory=self._infer_subcategory(response.url),
            published_at=published_at[:10] if published_at else None,
            metadata={"word_count": len(raw_content.split())},
        )

        # Follow article links found on this page
        for href in response.css("a::attr(href)").getall():
            url = urljoin(response.url, href)
            if self._is_article_url(url):
                yield scrapy.Request(url, callback=self.parse_article)

    def _is_article_url(self, url: str) -> bool:
        if "inseed.tg" not in url:
            return False
        path = url.rstrip("/").split("inseed.tg")[-1]
        # Exclude known non-article paths
        excluded = ["/category/", "/tag/", "/page/", "/author/", "/a-propos", "/organigramme", "/#"]
        if any(e in path for e in excluded):
            return False
        return bool(WP_SLUG_RE.search(path + "/"))

    def _infer_subcategory(self, url: str) -> str:
        if "/annuaire" in url:
            return "annuaire"
        if "/rapport" in url or "/publication" in url:
            return "rapport"
        return "actualite"
