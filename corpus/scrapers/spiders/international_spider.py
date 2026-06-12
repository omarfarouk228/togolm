"""
International sources — Togo-specific pages from major economic institutions.

Covers:
  - Banque Mondiale (World Bank) — country overview and data pages
  - FMI (IMF) — Togo country brief and staff reports
  - BCEAO — Togo-specific monetary statistics and publications
  - Banque Africaine de Développement (BAD/AfDB) — Togo country profile
  - PNUD/UNDP Togo — development reports
  - OMS/WHO Togo — health profiles

Strategy: target specific known stable URLs for Togo country pages.
These are largely static reference pages, not crawled recursively.
"""

from urllib.parse import urljoin

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

# ── Fixed page registry ────────────────────────────────────────────────────────

PAGES = [
    # ── Banque Mondiale / World Bank ─────────────────────────────────────────
    {
        "url": "https://www.banquemondiale.org/fr/country/togo",
        "source": "banquemondiale.org",
        "category": "economy",
        "subcategory": "overview",
        "title": "Togo — Banque Mondiale",
    },
    {
        "url": "https://donnees.banquemondiale.org/pays/TG",
        "source": "banquemondiale.org",
        "category": "economy",
        "subcategory": "statistiques",
        "title": "Données Togo — Banque Mondiale",
    },
    {
        "url": "https://www.banquemondiale.org/fr/country/togo/overview",
        "source": "banquemondiale.org",
        "category": "economy",
        "subcategory": "overview",
        "title": "Vue d'ensemble du Togo — Banque Mondiale",
    },
    # ── FMI / IMF ─────────────────────────────────────────────────────────────
    {
        "url": "https://www.imf.org/fr/Countries/TGO",
        "source": "imf.org",
        "category": "economy",
        "subcategory": "macroeconomie",
        "title": "Togo — FMI",
    },
    {
        "url": "https://www.imf.org/en/countries/TGO",
        "source": "imf.org",
        "category": "economy",
        "subcategory": "macroeconomie",
        "title": "Togo — IMF",
    },
    # ── BCEAO ─────────────────────────────────────────────────────────────────
    {
        "url": "https://www.bceao.int/fr/content/situation-monetaire-du-togo",
        "source": "bceao.int",
        "category": "economy",
        "subcategory": "monetaire",
        "title": "Situation monétaire du Togo — BCEAO",
    },
    {
        "url": "https://www.bceao.int/fr/publications/notes-dinformation-statistiques-nis",
        "source": "bceao.int",
        "category": "economy",
        "subcategory": "statistiques",
        "title": "Notes d'Information Statistiques — BCEAO",
    },
    {
        "url": "https://www.bceao.int/fr/content/togo",
        "source": "bceao.int",
        "category": "economy",
        "subcategory": "overview",
        "title": "Togo — BCEAO",
    },
    # ── Banque Africaine de Développement / AfDB ─────────────────────────────
    {
        "url": "https://www.afdb.org/fr/pays/afrique-de-louest/togo",
        "source": "afdb.org",
        "category": "economy",
        "subcategory": "overview",
        "title": "Togo — Banque Africaine de Développement",
    },
    {
        "url": "https://www.afdb.org/en/countries/west-africa/togo",
        "source": "afdb.org",
        "category": "economy",
        "subcategory": "overview",
        "title": "Togo — AfDB",
    },
    # ── PNUD / UNDP ───────────────────────────────────────────────────────────
    {
        "url": "https://www.tg.undp.org/",
        "source": "undp.org",
        "category": "economy",
        "subcategory": "developpement",
        "title": "PNUD Togo",
    },
    {
        "url": "https://www.tg.undp.org/content/togo/fr/home/ourwork.html",
        "source": "undp.org",
        "category": "economy",
        "subcategory": "developpement",
        "title": "Travaux du PNUD au Togo",
    },
    # ── OMS / WHO ─────────────────────────────────────────────────────────────
    {
        "url": "https://www.afro.who.int/fr/countries/togo",
        "source": "who.int",
        "category": "health",
        "subcategory": "sante_publique",
        "title": "Togo — OMS Afrique",
    },
    {
        "url": "https://www.who.int/countries/tgo/",
        "source": "who.int",
        "category": "health",
        "subcategory": "sante_publique",
        "title": "Togo — OMS",
    },
    # ── UNICEF ────────────────────────────────────────────────────────────────
    {
        "url": "https://www.unicef.org/togo/",
        "source": "unicef.org",
        "category": "health",
        "subcategory": "enfance",
        "title": "UNICEF Togo",
    },
    {
        "url": "https://www.unicef.org/togo/situation-des-enfants",
        "source": "unicef.org",
        "category": "health",
        "subcategory": "enfance",
        "title": "Situation des enfants au Togo — UNICEF",
    },
    # ── OCDE / OECD ──────────────────────────────────────────────────────────
    {
        "url": "https://stats.oecd.org/index.aspx?queryid=48152#",
        "source": "oecd.org",
        "category": "economy",
        "subcategory": "statistiques",
        "title": "Togo — OCDE Statistiques",
    },
    # ── Union Européenne — aide au développement ──────────────────────────────
    {
        "url": "https://www.eeas.europa.eu/delegations/togo_fr",
        "source": "europa.eu",
        "category": "economy",
        "subcategory": "cooperation",
        "title": "Délégation UE au Togo",
    },
]

# Also crawl BCEAO publication listing for Togo-specific reports
BCEAO_LISTING_URLS = [
    "https://www.bceao.int/fr/publications/rapports-annuels",
    "https://www.bceao.int/fr/publications/enquete-sur-le-financement-des-pme",
]


class InternationalSpider(BaseTogoSpider):
    """Fetch Togo country pages from major international institutions."""

    name = "international"
    source = "international"   # overridden per page via meta
    category = "economy"       # overridden per page via meta
    language = "fr"

    custom_settings = {
        "DOWNLOAD_DELAY": 2.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "ROBOTSTXT_OBEY": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "User-Agent": (
                "Mozilla/5.0 (compatible; TogoLM/1.0; "
                "+https://github.com/omarfarouk228/togolm)"
            ),
        },
    }

    @property
    def start_urls(self) -> list[str]:
        return [p["url"] for p in PAGES] + BCEAO_LISTING_URLS

    def parse(self, response):
        url = response.url

        # Check if this URL matches a registered page
        page_meta = next((p for p in PAGES if p["url"] == url), None)

        if page_meta:
            yield from self._parse_country_page(response, page_meta)
        elif "bceao.int" in url:
            yield from self._parse_bceao_listing(response)

    # ── Page parsers ──────────────────────────────────────────────────────────

    def _parse_country_page(self, response, page_meta: dict):
        """Extract content from a known country/institution page."""
        # Try multiple content selectors for different site layouts
        content_html = (
            response.css("main article").get("")
            or response.css(".country-overview, .country-content").get("")
            or response.css(".field-body, .field-items").get("")
            or response.css(".content-region, .region-content").get("")
            or response.css("main .container").get("")
            or response.css("main").get("")
        )

        if not content_html:
            return

        raw_content = self.html_to_text(content_html)
        words = raw_content.split()

        if len(words) < 80:
            return

        title = (
            response.css("h1::text").get("").strip()
            or page_meta["title"]
        )

        yield self.make_document(
            response=response,
            title=title,
            raw_content=raw_content,
            subcategory=page_meta["subcategory"],
            metadata={
                "word_count": len(words),
                "institution": page_meta["source"],
                "source_type": "international",
            },
        )
        # Override source and category from the page registry
        # (make_document uses self.source/category as defaults)

    def _parse_bceao_listing(self, response):
        """Follow links to individual BCEAO publications about Togo."""
        for href in response.css("a::attr(href)").getall():
            url = urljoin(response.url, href)
            if "bceao.int" not in url:
                continue
            if "togo" in url.lower() or "tg" in url.lower():
                yield scrapy.Request(
                    url,
                    callback=self._parse_bceao_doc,
                    meta={"source": "bceao.int", "category": "economy"},
                )

    def _parse_bceao_doc(self, response):
        title = (
            response.css("h1::text").get("").strip()
            or response.css("h2::text").get("").strip()
        )
        if not title:
            return

        content_html = (
            response.css(".field-body, article, main .container").get("")
            or response.css("main").get("")
        )
        if not content_html:
            return

        raw_content = self.html_to_text(content_html)
        if len(raw_content.split()) < 80:
            return

        yield self.make_document(
            response=response,
            title=title,
            raw_content=raw_content,
            subcategory="publication_bceao",
            metadata={"word_count": len(raw_content.split()), "source_type": "international"},
        )

    def make_document(self, response, title, raw_content, **kwargs):
        """Override to inject per-page source/category."""
        doc = super().make_document(response, title, raw_content, **kwargs)
        page_meta = next((p for p in PAGES if p["url"] == response.url), None)
        if page_meta:
            doc["source"] = page_meta["source"]
            doc["category"] = page_meta["category"]
        elif response.meta.get("source"):
            doc["source"] = response.meta["source"]
            doc["category"] = response.meta.get("category", "economy")
        return doc
