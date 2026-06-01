"""
Spider for lomeinfos.com — Lomé-focused Togolese news portal.

WordPress site with 5 post sitemaps (~4,410 articles total).
Covers: politics, economy, society, education, health, culture,
        environment, sports, local communes, cooperation.

Uses post sitemaps for complete article discovery (same approach as icilome).
"""

import re

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

# All known post sitemaps (WordPress generates one per ~1000 posts)
POST_SITEMAPS = [
    "https://www.lomeinfos.com/post-sitemap.xml",
    "https://www.lomeinfos.com/post-sitemap2.xml",
    "https://www.lomeinfos.com/post-sitemap3.xml",
    "https://www.lomeinfos.com/post-sitemap4.xml",
    "https://www.lomeinfos.com/post-sitemap5.xml",
]

# Match article slugs at root: /some-title-here/
# Exclude static pages and WordPress internals
EXCLUDED_PATHS = [
    "/category/", "/togo/", "/tag/", "/author/", "/page/", "/feed/",
    "/wp-content/", "/wp-admin/", "/wp-json/",
    "/mentions-legales/", "/partenariat/", "/publicites/", "/contacts/",
    "/e-reputation/", "/sitemap", "mailto:", "javascript:", "#",
]

SLUG_RE = re.compile(r"^/[a-z][a-z0-9\-]{8,}/$")

SUBCATEGORY_MAP = {
    "togo-politique": "politics",
    "politique": "politics",
    "togo-economie": "economy",
    "economie": "economy",
    "societe": "society",
    "togo-education": "education",
    "education": "education",
    "togo-sante": "health",
    "sante": "health",
    "religion-et-culture": "culture",
    "culture": "culture",
    "sports": "sport",
    "communes": "local",
    "jeunesse-et-emploi": "employment",
    "cooperation": "cooperation",
    "agri-environnement": "environment",
    "technologie": "technology",
    "faits-divers": "faits-divers",
    "people-showbiz": "culture",
}


class LomeinfosSpider(BaseTogoSpider):
    name = "lomeinfos"
    source = "lomeinfos.com"
    category = "press"
    language = "fr"

    start_urls = POST_SITEMAPS

    custom_settings = {
        "DOWNLOAD_DELAY": 0.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
    }

    def parse(self, response):
        ct = response.headers.get("Content-Type", b"").decode()
        if "xml" in ct or response.url.endswith(".xml"):
            yield from self._parse_sitemap(response)
        else:
            yield from self._parse_article(response)

    def _parse_sitemap(self, response):
        response.selector.remove_namespaces()
        for url in response.xpath("//loc/text()").getall():
            url = url.strip()
            if self._is_article_url(url):
                yield scrapy.Request(url, callback=self.parse, priority=10)

    def _parse_article(self, response):
        # Standard WordPress selectors
        title = (
            response.css("h1.entry-title::text").get("") or
            response.css("h1.post-title::text").get("") or
            response.css("h1::text").get("") or
            response.css("title::text").get("")
        ).strip()

        # Remove site name suffix from title
        if " - " in title:
            title = title.split(" - ")[0].strip()
        if " | " in title:
            title = title.split(" | ")[0].strip()

        if not title or len(title) < 5:
            return

        # Main article body
        body_html = response.css(
            ".entry-content, .post-content, .td-post-content, article .content"
        ).get("")
        raw_content = self.html_to_text(body_html) if body_html else ""

        if not raw_content or len(raw_content.split()) < 20:
            paragraphs = response.css(
                "article p::text, .entry-content p::text, .post-content p::text"
            ).getall()
            raw_content = " ".join(p.strip() for p in paragraphs if p.strip())

        if not raw_content or len(raw_content.split()) < 20:
            return

        published_at = (
            response.css("time.entry-date::attr(datetime)").get("") or
            response.css("time.published::attr(datetime)").get("") or
            response.css("meta[property='article:published_time']::attr(content)").get("") or
            ""
        )

        # Infer subcategory from article's CSS class (category-{slug})
        article_classes = response.css("article::attr(class)").get("") or ""
        subcategory = self._infer_subcategory_from_class(article_classes, response.url)

        yield self.make_document(
            response=response,
            title=title,
            raw_content=raw_content,
            subcategory=subcategory,
            published_at=published_at[:10] if published_at else None,
            metadata={"word_count": len(raw_content.split())},
        )

    def _is_article_url(self, url: str) -> bool:
        if "lomeinfos.com" not in url:
            return False
        if any(e in url for e in EXCLUDED_PATHS):
            return False
        path = url.split("lomeinfos.com")[-1]
        # Numeric post ID URLs like /9587/ are also valid
        if re.match(r"^/\d+/$", path):
            return True
        return bool(SLUG_RE.match(path))

    def _infer_subcategory_from_class(self, class_str: str, url: str) -> str:
        """Extract subcategory from WordPress article class 'category-{slug}'."""
        for cls in class_str.split():
            if cls.startswith("category-"):
                cat_slug = cls[len("category-"):]
                if cat_slug in SUBCATEGORY_MAP:
                    return SUBCATEGORY_MAP[cat_slug]
        # Fallback to URL-based inference
        url_lower = url.lower()
        for key, sub in SUBCATEGORY_MAP.items():
            if key in url_lower:
                return sub
        return "news"
