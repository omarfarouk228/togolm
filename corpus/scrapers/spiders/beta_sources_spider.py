"""
Beta-launch institutional sources not yet covered by the corpus.

Sites:
  - ul.tg / univ-lome.tg      — Université de Lomé (education)
  - api.tg                     — Agence de Promotion des Investissements (economy)
  - ceet.tg                    — Compagnie Énergie Électrique du Togo (utilities)
  - cour-constitutionnelle.tg  — Cour Constitutionnelle (legal)
  - inam.tg                    — Institut National d'Assurance Maladie (health)

Strategy per site:
  1. Try WordPress/standard sitemaps (fast path when available)
  2. Crawl from known category/listing pages
  3. Follow pagination and content links

Run a single site with: scrapy crawl beta_sources -a sites=ul.tg
"""

import re
from urllib.parse import urljoin

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

# ── Site registry ─────────────────────────────────────────────────────────────

SITES = [
    # ── Education ─────────────────────────────────────────────────────────────
    {
        "domain": "ul.tg",
        "source": "ul.tg",
        "category": "education",
        "sitemaps": [
            "https://ul.tg/wp-sitemap.xml",
            "https://ul.tg/sitemap.xml",
            "https://ul.tg/sitemap_index.xml",
        ],
        "start_urls": [
            "https://ul.tg/",
            "https://ul.tg/facultes-et-ecoles/",
            "https://ul.tg/scolarite/",
            "https://ul.tg/formation/",
            "https://ul.tg/actualites/",
            "https://ul.tg/recherche/",
            "https://ul.tg/vie-universitaire/",
        ],
        "content_keywords": ["faculte", "ecole", "formation", "programme", "actualite",
                              "scolarite", "licence", "master", "doctorat", "inscription"],
    },
    # ── Economy / Investment ───────────────────────────────────────────────────
    {
        "domain": "api.tg",
        "source": "api.tg",
        "category": "economy",
        "sitemaps": [
            "https://api.tg/wp-sitemap.xml",
            "https://api.tg/sitemap.xml",
            "https://api.tg/sitemap_index.xml",
        ],
        "start_urls": [
            "https://api.tg/",
            "https://api.tg/investir-au-togo/",
            "https://api.tg/creer-une-entreprise/",
            "https://api.tg/secteurs-porteurs/",
            "https://api.tg/actualites/",
            "https://api.tg/pourquoi-investir/",
            "https://api.tg/cadre-juridique/",
            "https://api.tg/services/",
            "https://api.tg/guichet-unique/",
        ],
        "content_keywords": ["investir", "entreprise", "secteur", "actualite", "service",
                              "creation", "juridique", "fiscal", "guichet"],
    },
    # ── Utilities ─────────────────────────────────────────────────────────────
    {
        "domain": "ceet.tg",
        "source": "ceet.tg",
        "category": "economy",
        "sitemaps": [
            "https://www.ceet.tg/sitemap.xml",
            "https://www.ceet.tg/wp-sitemap.xml",
        ],
        "start_urls": [
            "https://www.ceet.tg/",
            "https://www.ceet.tg/tarifs/",
            "https://www.ceet.tg/raccordement/",
            "https://www.ceet.tg/actualites/",
            "https://www.ceet.tg/nos-offres/",
            "https://www.ceet.tg/decouvrir-la-ceet/",
            "https://www.ceet.tg/clients/",
        ],
        "content_keywords": ["tarif", "raccordement", "offre", "actualite", "electricite",
                              "client", "service", "facturation", "compteur"],
    },
    # ── Legal ─────────────────────────────────────────────────────────────────
    {
        "domain": "cour-constitutionnelle.tg",
        "source": "cour-constitutionnelle.tg",
        "category": "legal",
        "sitemaps": [
            "https://www.cour-constitutionnelle.tg/sitemap.xml",
            "https://www.cour-constitutionnelle.tg/wp-sitemap.xml",
        ],
        "start_urls": [
            "https://www.cour-constitutionnelle.tg/",
            "https://www.cour-constitutionnelle.tg/decisions/",
            "https://www.cour-constitutionnelle.tg/jurisprudence/",
            "https://www.cour-constitutionnelle.tg/actualites/",
            "https://www.cour-constitutionnelle.tg/arrets/",
            "https://www.cour-constitutionnelle.tg/avis/",
        ],
        "content_keywords": ["decision", "arret", "avis", "jurisprudence", "constitution",
                              "actualite", "election", "loi"],
    },
    # ── Health ────────────────────────────────────────────────────────────────
    {
        "domain": "inam.tg",
        "source": "inam.tg",
        "category": "health",
        "sitemaps": [
            "https://www.inam.tg/sitemap.xml",
            "https://www.inam.tg/wp-sitemap.xml",
        ],
        "start_urls": [
            "https://www.inam.tg/",
            "https://www.inam.tg/prestations/",
            "https://www.inam.tg/comment-beneficier/",
            "https://www.inam.tg/actualites/",
            "https://www.inam.tg/structures-agreees/",
            "https://www.inam.tg/remboursements/",
            "https://www.inam.tg/assures/",
        ],
        "content_keywords": ["prestation", "assure", "remboursement", "structure",
                              "actualite", "adherent", "cotisation", "soin"],
    },
]

# ── Helpers ───────────────────────────────────────────────────────────────────

# A slug must have at least 8 meaningful characters after the domain
_SLUG_RE = re.compile(r"/[a-z0-9][a-z0-9\-]{6,}/?$")

_EXCLUDED_PATHS = [
    "/category/", "/tag/", "/author/", "/page/", "/feed/",
    "/wp-content/", "/wp-admin/", "/wp-json/", "/#", "/cdn-cgi/",
    "/login", "/logout", "/search", "/panier", "/cart",
]


def _site_for_url(url: str) -> dict | None:
    for site in SITES:
        if site["domain"] in url:
            return site
    return None


def _is_excluded(url: str) -> bool:
    path = "/" + url.split("/", 3)[-1].lower()
    return any(e in path for e in _EXCLUDED_PATHS)


def _is_content_url(url: str, site: dict) -> bool:
    """Return True if the URL looks like a content page for this site."""
    if site["domain"] not in url:
        return False
    if _is_excluded(url):
        return False
    path = url.split(site["domain"])[-1].lower()
    # Accept if path contains a known keyword
    if any(kw in path for kw in site["content_keywords"]):
        return True
    # Or if it looks like a slug (enough path segments)
    return bool(_SLUG_RE.search(path + "/"))


# ── Spider ────────────────────────────────────────────────────────────────────


class BetaSourcesSpider(BaseTogoSpider):
    """Crawl all beta-launch institutional sites in one pass."""

    name = "beta_sources"
    source = "beta"       # overridden per-URL via meta
    category = "general"  # overridden per-URL via meta
    language = "fr"

    start_urls: list[str] = []

    custom_settings = {
        "DOWNLOAD_DELAY": 1.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "ROBOTSTXT_OBEY": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        },
    }

    def __init__(self, *args, sites: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        # Optional filter: -a sites=ul.tg,api.tg
        domain_filter = set(sites.split(",")) if sites else None
        active = [s for s in SITES if domain_filter is None or s["domain"] in domain_filter]

        for site in active:
            # Try sitemaps first, then HTML listing pages
            for url in site["sitemaps"] + site["start_urls"]:
                self.start_urls.append(url)

    # ── Entry-point dispatcher ────────────────────────────────────────────────

    def parse(self, response):
        ct = response.headers.get("Content-Type", b"").decode().lower()
        url = response.url

        if "xml" in ct or url.endswith(".xml"):
            yield from self._parse_sitemap(response)
        else:
            yield from self._parse_html(response)

    # ── Sitemap parsing ───────────────────────────────────────────────────────

    def _parse_sitemap(self, response):
        """Extract all <loc> URLs from a sitemap; handle sitemap-index too."""
        response.selector.remove_namespaces()
        locs = response.xpath("//loc/text()").getall()
        site = _site_for_url(response.url)
        if not site:
            return
        for loc in locs:
            if loc.endswith(".xml"):
                # Nested sitemap
                yield scrapy.Request(loc, callback=self.parse, meta={"site": site})
            elif _is_content_url(loc, site):
                yield scrapy.Request(
                    loc,
                    callback=self._parse_article,
                    meta={"site": site},
                    priority=10,
                )

    # ── HTML page parsing ─────────────────────────────────────────────────────

    def _parse_html(self, response):
        """Parse any HTML page: extract content if article-like, follow links."""
        site = response.meta.get("site") or _site_for_url(response.url)
        if not site:
            return

        # Follow all outbound links on the page
        for href in response.css("a::attr(href)").getall():
            url = urljoin(response.url, href)
            if not _is_content_url(url, site):
                continue
            yield scrapy.Request(
                url,
                callback=self._parse_article,
                meta={"site": site},
                priority=5,
            )

        # WordPress pagination
        next_page = response.css(
            "a.next::attr(href), a[rel='next']::attr(href), .nav-next a::attr(href)"
        ).get()
        if next_page:
            yield scrapy.Request(
                urljoin(response.url, next_page),
                callback=self._parse_html,
                meta={"site": site},
            )

    # ── Article extraction ────────────────────────────────────────────────────

    def _parse_article(self, response):
        site = response.meta.get("site") or _site_for_url(response.url)
        if not site:
            return

        # Follow links found on this article page too
        yield from self._parse_html(response)

        # Title
        title = (
            response.css("h1::text").get("")
            or response.css("h2.entry-title::text").get("")
            or response.css(".page-title::text").get("")
            or response.css("title::text").get("").split("|")[0].split("–")[0]
        ).strip()

        if not title or len(title) < 5:
            return

        # Content — try rich selectors first, fall back to all <p> tags
        content_html = (
            response.css(".entry-content").get("")
            or response.css("article .content").get("")
            or response.css(".elementor-widget-container").get("")
            or response.css("main .content, main article").get("")
            or response.css(".post-content, .single-content").get("")
        )

        if content_html:
            raw_content = self.html_to_text(content_html)
        else:
            # Last resort: collect all paragraph text
            paras = response.css("main p::text, article p::text, .container p::text").getall()
            raw_content = " ".join(p.strip() for p in paras if p.strip())

        if not raw_content or len(raw_content.split()) < 30:
            return

        published_at = (
            response.css("time::attr(datetime)").get("")
            or response.css("meta[property='article:published_time']::attr(content)").get("")
            or ""
        )

        subcategory = self._infer_subcategory(response.url, site)

        yield self._make_site_document(
            response=response,
            site=site,
            title=title,
            raw_content=raw_content,
            subcategory=subcategory,
            published_at=published_at[:10] if published_at else None,
            metadata={"word_count": len(raw_content.split())},
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _make_site_document(self, response, site: dict, **kwargs):
        """make_document override that uses per-site source/category."""
        doc = self.make_document(response=response, **kwargs)
        doc["source"] = site["source"]
        doc["category"] = site["category"]
        return doc

    def _infer_subcategory(self, url: str, site: dict) -> str:
        path = url.lower()
        if site["domain"] == "ul.tg":
            if "faculte" in path or "ecole" in path:
                return "faculte"
            if "master" in path or "licence" in path or "doctorat" in path:
                return "formation"
            if "inscription" in path or "scolarite" in path:
                return "scolarite"
            if "recherche" in path:
                return "recherche"
        elif site["domain"] == "api.tg":
            if "creer" in path or "creation" in path:
                return "creation_entreprise"
            if "secteur" in path:
                return "secteurs"
            if "juridique" in path or "fiscal" in path:
                return "cadre_juridique"
            if "guichet" in path:
                return "guichet_unique"
        elif site["domain"] == "ceet.tg":
            if "tarif" in path:
                return "tarifs"
            if "raccordement" in path:
                return "raccordement"
        elif site["domain"] == "cour-constitutionnelle.tg":
            if "decision" in path or "arret" in path:
                return "decision"
            if "avis" in path:
                return "avis"
            if "jurisprudence" in path:
                return "jurisprudence"
        elif site["domain"] == "inam.tg":
            if "prestation" in path:
                return "prestations"
            if "remboursement" in path:
                return "remboursements"
            if "structure" in path:
                return "structures_agreees"
        return "actualite"
