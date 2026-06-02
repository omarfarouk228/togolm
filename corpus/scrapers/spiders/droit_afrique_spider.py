"""
Spider for Togolese legal texts from multiple open sources.

droit-afrique.com blocks all scrapers (403). This spider targets:
  1. legitogo.gouv.tg — official Togolese legislation portal
  2. Specific Wikipedia (fr) pages for major Togolese codes and the constitution

These sources are freely accessible and cover the critical gap:
Constitution, Code du Travail, Code Pénal, Code Civil, etc.
"""

import re
from urllib.parse import urljoin

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

# Specific Wikipedia pages for major Togolese legal texts
WIKIPEDIA_LEGAL_PAGES = [
    # Juridique
    "https://fr.wikipedia.org/wiki/Constitution_du_Togo",
    "https://fr.wikipedia.org/wiki/Droit_du_travail_au_Togo",
    "https://fr.wikipedia.org/wiki/Code_p%C3%A9nal_togolais",
    "https://fr.wikipedia.org/wiki/Droit_togolais",
    "https://fr.wikipedia.org/wiki/Syst%C3%A8me_judiciaire_du_Togo",
    "https://fr.wikipedia.org/wiki/Assembl%C3%A9e_nationale_(Togo)",
    "https://fr.wikipedia.org/wiki/Cour_supr%C3%AAme_(Togo)",
    "https://fr.wikipedia.org/wiki/Cour_constitutionnelle_(Togo)",
    # Éducation & universités
    "https://fr.wikipedia.org/wiki/%C3%89ducation_au_Togo",
    "https://fr.wikipedia.org/wiki/Universit%C3%A9_de_Lom%C3%A9",
    "https://fr.wikipedia.org/wiki/Universit%C3%A9_de_Kara",
    "https://fr.wikipedia.org/wiki/Enseignement_sup%C3%A9rieur_au_Togo",
    # Économie & gouvernement
    "https://fr.wikipedia.org/wiki/%C3%89conomie_du_Togo",
    "https://fr.wikipedia.org/wiki/Budget_du_Togo",
    "https://fr.wikipedia.org/wiki/Gouvernement_du_Togo",
    "https://fr.wikipedia.org/wiki/Office_togolais_des_recettes",
    # Géographie & société
    "https://fr.wikipedia.org/wiki/Togo",
    "https://fr.wikipedia.org/wiki/Lom%C3%A9",
    "https://fr.wikipedia.org/wiki/D%C3%A9mographie_du_Togo",
    "https://fr.wikipedia.org/wiki/Sant%C3%A9_au_Togo",
]

# legitogo.gouv.tg — official legal portal
LEGITOGO_URLS = [
    "https://legitogo.gouv.tg",
    "https://legitogo.gouv.tg/codes",
    "https://legitogo.gouv.tg/lois",
]

_SUBCAT_MAP = [
    (r"constitution", "constitution"),
    (r"code\s+du\s+travail|droit\s+du\s+travail", "code_travail"),
    (r"code\s+p[eé]nal", "code_penal"),
    (r"code\s+civil", "code_civil"),
    (r"code\s+de\s+commerce", "code_commerce"),
    (r"code\s+(?:de\s+)?proc[eé]dure", "code_procedure"),
    (r"code\s+(?:de\s+)?la\s+famille", "code_famille"),
    (r"syst[eè]me\s+judiciaire|cour\s+supr[eê]me|cour\s+constitutionnelle", "justice"),
    (r"assembl[eé]e\s+nationale", "parlement"),
    (r"\bloi\b", "loi"),
]


def _infer_subcategory(title: str) -> str:
    low = title.lower()
    for pattern, label in _SUBCAT_MAP:
        if re.search(pattern, low):
            return label
    return "texte_juridique"


class DroitAfriqueSpider(BaseTogoSpider):
    """Scrape Togolese legal texts from legitogo.gouv.tg and Wikipedia."""

    name = "droit_afrique"
    source = "legitogo.gouv.tg"
    category = "legal"
    language = "fr"

    start_urls = LEGITOGO_URLS + WIKIPEDIA_LEGAL_PAGES

    custom_settings = {
        "DOWNLOAD_DELAY": 1.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "ROBOTSTXT_OBEY": True,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        },
    }

    def parse(self, response):
        url = response.url

        # Wikipedia pages → parse directly
        if "wikipedia.org" in url:
            yield from self._parse_wikipedia(response)
            return

        # legitogo.gouv.tg → follow links to legal documents
        if "legitogo.gouv.tg" in url:
            yield from self._parse_legitogo(response)
            return

    def _parse_wikipedia(self, response):
        """Extract article content from a French Wikipedia page."""
        title = response.css("#firstHeading span::text, #firstHeading::text").get("").strip()
        if not title:
            return

        # Main article content (excludes navboxes, references, etc.)
        content_el = response.css("#mw-content-text .mw-parser-output")
        if not content_el:
            return

        # Remove unwanted sections (references, see also, navboxes)
        raw_html = content_el.get()
        raw_text = self.html_to_text(raw_html)

        words = raw_text.split()
        if len(words) < 100:
            return

        subcategory = _infer_subcategory(title)

        yield self.make_document(
            response=response,
            title=title,
            raw_content=raw_text,
            subcategory=subcategory,
            metadata={
                "word_count": len(words),
                "document_type": subcategory,
                "source_type": "wikipedia",
            },
        )

    def _parse_legitogo(self, response):
        """Parse legitogo.gouv.tg pages and follow document links."""
        # Follow links to legal documents
        for href in response.css("a::attr(href)").getall():
            if not href:
                continue
            if href.startswith(("#", "mailto:", "javascript:")):
                continue
            url = urljoin("https://legitogo.gouv.tg", href)
            if "legitogo.gouv.tg" not in url:
                continue
            if url == response.url:
                continue
            yield scrapy.Request(url, callback=self._parse_legitogo_doc)

    def _parse_legitogo_doc(self, response):
        """Extract a legal document from legitogo.gouv.tg."""
        title = (
            response.css("h1::text").get()
            or response.css("h2::text").get()
            or response.css("title::text").get()
            or ""
        ).strip()

        if not title:
            return

        content_sel = (
            response.css(".field-items")
            or response.css("article")
            or response.css(".content")
            or response.css("main")
        )

        if content_sel:
            raw_text = self.html_to_text(content_sel.get())
        else:
            raw_text = self.html_to_text(response.text)

        words = raw_text.split()
        if len(words) < 80:
            return

        subcategory = _infer_subcategory(title)

        yield self.make_document(
            response=response,
            title=title,
            raw_content=raw_text,
            subcategory=subcategory,
            metadata={
                "word_count": len(words),
                "document_type": subcategory,
                "source_type": "legitogo",
            },
        )
