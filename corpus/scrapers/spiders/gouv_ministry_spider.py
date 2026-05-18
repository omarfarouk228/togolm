"""
Spider for Togolese government ministry sites sharing the same WordPress/Elementor stack.

Currently covers:
  - finances.gouv.tg    (finance — budget, tax, fiscal)
  - education.gouv.tg   (education — policy, curriculum, recruitment)
  - agriculture.gouv.tg (agriculture — food security, rural development)
  - commerce.gouv.tg    (commerce — trade, industry, SMEs)
  - securite.gouv.tg    (security — public safety, civil protection)

All sites expose XML sitemaps at /wp-sitemap.xml with post and documentation sub-sitemaps.
Content lives in plain <p> tags across the page (no wrapping <article> element).
"""

import re
from urllib.parse import urljoin

import scrapy

from scrapers.spiders.base_spider import BaseTogoSpider

SITES = [
    # ── Economy / Finance ────────────────────────────────────────────────────
    {
        "domain": "finances.gouv.tg",
        "source": "finances.gouv.tg",
        "category": "economy",
        "sitemaps": [
            "https://finances.gouv.tg/post-sitemap.xml",
            "https://finances.gouv.tg/post-sitemap2.xml",
            "https://finances.gouv.tg/documentation-sitemap.xml",
        ],
    },
    {
        "domain": "commerce.gouv.tg",
        "source": "commerce.gouv.tg",
        "category": "economy",
        "sitemaps": [
            "https://commerce.gouv.tg/wp-sitemap-posts-post-1.xml",
            "https://commerce.gouv.tg/post-sitemap.xml",
            "https://commerce.gouv.tg/documentation-sitemap.xml",
        ],
    },
    # ── Education ────────────────────────────────────────────────────────────
    {
        "domain": "education.gouv.tg",
        "source": "education.gouv.tg",
        "category": "education",
        "sitemaps": [
            "https://education.gouv.tg/post-sitemap.xml",
            "https://education.gouv.tg/documentation-sitemap.xml",
        ],
    },
    # ── Agriculture / Environment ────────────────────────────────────────────
    {
        "domain": "agriculture.gouv.tg",
        "source": "agriculture.gouv.tg",
        "category": "agriculture",
        "sitemaps": [
            "https://agriculture.gouv.tg/wp-sitemap-posts-post-1.xml",
            "https://agriculture.gouv.tg/post-sitemap.xml",
            "https://agriculture.gouv.tg/documentation-sitemap.xml",
        ],
    },
    {
        "domain": "environnement.gouv.tg",
        "source": "environnement.gouv.tg",
        "category": "agriculture",
        "sitemaps": [
            "https://environnement.gouv.tg/wp-sitemap-posts-post-1.xml",
            "https://environnement.gouv.tg/post-sitemap.xml",
        ],
    },
    # ── Health ───────────────────────────────────────────────────────────────
    {
        "domain": "sante.gouv.tg",
        "source": "sante.gouv.tg",
        "category": "health",
        "sitemaps": [
            "https://sante.gouv.tg/wp-sitemap-posts-post-1.xml",
            "https://sante.gouv.tg/post-sitemap.xml",
            "https://sante.gouv.tg/documentation-sitemap.xml",
        ],
    },
    # ── Justice / Security ───────────────────────────────────────────────────
    {
        "domain": "justice.gouv.tg",
        "source": "justice.gouv.tg",
        "category": "legal",
        "sitemaps": [
            "https://justice.gouv.tg/wp-sitemap-posts-post-1.xml",
            "https://justice.gouv.tg/post-sitemap.xml",
        ],
    },
    {
        "domain": "securite.gouv.tg",
        "source": "securite.gouv.tg",
        "category": "politics",
        "sitemaps": [
            "https://securite.gouv.tg/wp-sitemap-posts-post-1.xml",
            "https://securite.gouv.tg/post-sitemap.xml",
            "https://securite.gouv.tg/documentation-sitemap.xml",
        ],
    },
    # ── Labour / Social ──────────────────────────────────────────────────────
    # travail.gouv.tg: returns Apache directory listing — no site deployed
    # ── Infrastructure / Energy ──────────────────────────────────────────────
    # infrastructure.gouv.tg: SSL error (HTTP 526) — skip
    # mines.gouv.tg: same site as energie.gouv.tg — skip (duplicate)
    # plan.gouv.tg: TCP timeout — skip
    {
        "domain": "energie.gouv.tg",
        "source": "energie.gouv.tg",
        "category": "economy",
        "sitemaps": [
            "https://energie.gouv.tg/wp-sitemap-posts-post-1.xml",
            "https://energie.gouv.tg/post-sitemap.xml",
        ],
    },
    # ── Digital ──────────────────────────────────────────────────────────────
    # numerique.gouv.tg: sitemap returns no URLs — skip
    # sante.gouv.tg: React SPA, no WordPress sitemap — skip
    # ── Tourism ──────────────────────────────────────────────────────────────
    {
        "domain": "tourisme.gouv.tg",
        "source": "tourisme.gouv.tg",
        "category": "economy",
        "sitemaps": [
            "https://tourisme.gouv.tg/wp-sitemap-posts-post-1.xml",
            "https://tourisme.gouv.tg/post-sitemap.xml",
        ],
    },
    # ── Presidency of the Council ─────────────────────────────────────────────
    {
        "domain": "presidenceduconseil.gouv.tg",
        "source": "presidenceduconseil.gouv.tg",
        "category": "politics",
        "sitemaps": [
            "https://presidenceduconseil.gouv.tg/post-sitemap.xml",
            "https://presidenceduconseil.gouv.tg/wp-sitemap-posts-post-1.xml",
        ],
    },
    # ── Urban Development ─────────────────────────────────────────────────────
    {
        "domain": "urbanisme.gouv.tg",
        "source": "urbanisme.gouv.tg",
        "category": "economy",
        "sitemaps": [
            "https://urbanisme.gouv.tg/wp-sitemap-posts-post-1.xml",
            "https://urbanisme.gouv.tg/wp-sitemap-posts-documentation-1.xml",
        ],
    },
    # ── Social Security ───────────────────────────────────────────────────────
    {
        "domain": "cnss.tg",
        "source": "cnss.tg",
        "category": "legal",
        "sitemaps": [
            "https://cnss.tg/wp-sitemap-posts-post-1.xml",
            "https://cnss.tg/sitemap.xml",
        ],
    },
]

# Paths that are never articles
EXCLUDED_PATHS = [
    "/category/", "/tag/", "/author/", "/page/", "/feed/",
    "/wp-content/", "/wp-admin/", "/#",
]

# Slug must be at least 10 chars (digits allowed at start for year-prefixed URLs like /2017-la-...)
SLUG_RE = re.compile(r"/[a-z0-9][a-z0-9\-]{8,}/?$")


class GouvMinistrySpider(BaseTogoSpider):
    name = "gouv_ministry"
    source = "gouv.tg"      # overridden per-URL via meta
    category = "government"  # overridden per-URL via meta
    language = "fr"

    # Sitemap URLs are the entry points
    start_urls = []

    def __init__(self, *args, sites=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Optional comma-separated domain filter, e.g. -a sites=mines.gouv.tg,sante.gouv.tg
        site_filter = set(sites.split(",")) if sites else None
        active_sites = [s for s in SITES if site_filter is None or s["domain"] in site_filter]
        for site in active_sites:
            for sitemap_url in site["sitemaps"]:
                self.start_urls.append(sitemap_url)

    def parse(self, response):
        """Parse either a sitemap XML or an article page."""
        ct = response.headers.get("Content-Type", b"").decode()
        if "xml" in ct or response.url.endswith(".xml"):
            yield from self._parse_sitemap(response)
        else:
            yield from self._parse_article(response)

    def _parse_sitemap(self, response):
        """Extract article URLs from a WordPress XML sitemap (namespace-agnostic)."""
        response.selector.remove_namespaces()
        urls = response.xpath("//loc/text()").getall()
        for url in urls:
            site = self._site_for_url(url)
            if site and self._is_article_url(url):
                yield scrapy.Request(
                    url,
                    callback=self.parse,
                    meta={"site": site},
                    priority=10,
                )

    def _parse_article(self, response):
        site = response.meta.get("site") or self._site_for_url(response.url) or {}

        title = (
            response.css("h1::text").get("") or
            response.css("h2.entry-title::text").get("") or
            response.css("title::text").get("").split("|")[0]
        ).strip()

        if not title or len(title) < 5:
            return

        # Collect all substantial paragraphs from the page
        paragraphs = [
            p.strip()
            for p in response.css("p::text, p *::text").getall()
            if p.strip() and len(p.strip()) > 20
        ]
        raw_content = " ".join(paragraphs)

        if not raw_content or len(raw_content.split()) < 20:
            return

        published_at = (
            response.css("time::attr(datetime)").get("") or
            response.xpath('//meta[@property="article:published_time"]/@content').get("") or
            ""
        )

        subcategory = self._infer_subcategory(response.url)

        yield self.make_document(
            response=response,
            title=title,
            raw_content=raw_content,
            subcategory=subcategory,
            published_at=published_at[:10] if published_at else None,
            metadata={
                "word_count": len(raw_content.split()),
                "source_site": site.get("source", ""),
            },
        )

    def _site_for_url(self, url: str) -> dict | None:
        for site in SITES:
            if site["domain"] in url:
                return site
        return None

    def _is_article_url(self, url: str) -> bool:
        if any(e in url for e in EXCLUDED_PATHS):
            return False
        path = "/" + url.split("/", 3)[-1].rstrip("/")
        return bool(SLUG_RE.search(path + "/"))

    def _infer_subcategory(self, url: str) -> str:
        url_lower = url.lower()
        if "/documentation/" in url_lower:
            return "document"
        if "/budget" in url_lower or "/finance" in url_lower:
            return "budget"
        if "/impot" in url_lower or "/taxe" in url_lower or "/fiscal" in url_lower:
            return "fiscal"
        if "/curriculum" in url_lower or "/programme" in url_lower:
            return "curriculum"
        if "/agriculture" in url_lower or "/elevage" in url_lower or "/peche" in url_lower:
            return "agriculture"
        if "/commerce" in url_lower or "/industrie" in url_lower or "/pme" in url_lower:
            return "commerce"
        if "/securite" in url_lower or "/police" in url_lower or "/gendarmerie" in url_lower:
            return "securite"
        return "actualite"

    def make_document(self, response, title, raw_content, **kwargs):
        """Override to inject per-site source and category from meta."""
        site = response.meta.get("site") or self._site_for_url(response.url) or {}
        doc = super().make_document(response, title, raw_content, **kwargs)
        if site:
            doc["source"] = site["source"]
            doc["category"] = site["category"]
        return doc
