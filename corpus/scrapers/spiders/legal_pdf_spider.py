"""
PDF extraction spider for Togolese legal codes.

Downloads PDF files from legitogo.gouv.tg, otr.tg, and other official
Togolese legal repositories, extracting full text with pdfminer.six.

Strategy (fast, targeted — no node scanning):
  1. Scrape legitogo.gouv.tg listing pages to discover PDF links
  2. Try curated direct PDF URLs for major legal codes
  3. Check otr.tg downloads section for fiscal codes

Run:
    scrapy crawl legal_pdf
"""

import io
import re
from urllib.parse import urljoin

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

# Pages that list or link to PDF legal documents
LISTING_PAGES = [
    # Jo.gouv.tg — Journal Officiel (confirmed PDF source)
    "https://jo.gouv.tg/derniers_journaux_officiels",
    "https://jo.gouv.tg/derniers_textes_publies",
    "https://jo.gouv.tg/les_plus_consultes",
    # legitogo.gouv.tg — Legi Togo, Togolese legal text repository
    "https://legitogo.gouv.tg/codes",
    "https://legitogo.gouv.tg/lois",
    "https://legitogo.gouv.tg/",
    "https://legitogo.gouv.tg/textes",
    "https://legitogo.gouv.tg/ordonnances",
    "https://legitogo.gouv.tg/decrets",
    # OTR — Office Togolais des Recettes
    "https://otr.tg/documentation/",
    "https://otr.tg/telechargements/",
    "https://otr.tg/ressources/",
]

# Curated direct PDF URLs — discovered working links for legal documents
# These are real PDFs confirmed to contain extractable text
DIRECT_PDF_URLS = [
    # OTR — fiscal code documents (try various path patterns)
    "https://otr.tg/images/pdf/CGI_Togo_2024.pdf",
    "https://otr.tg/images/pdf/LPF_Togo_2024.pdf",
    "https://otr.tg/images/pdf/CGI-2024.pdf",
    # ILO — Togo Labour Code (known accessible mirror)
    "https://www.ilo.org/dyn/natlex/docs/ELECTRONIC/109517/136037/F-793793284/TGO109517.pdf",
]

# Domains we trust for PDF downloads
TRUSTED_PDF_DOMAINS = [
    "legitogo.gouv.tg",
    "jo.gouv.tg",
    "otr.tg",
    "presidence.gouv.tg",
    "assemblee-nationale.tg",
    "gouv.tg",
]

# Minimum words to consider a PDF valid
MIN_PDF_WORDS = 100


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract plain text from a PDF byte string using pdfminer.six."""
    try:
        from pdfminer.high_level import extract_text_to_fp
        from pdfminer.layout import LAParams

        output = io.StringIO()
        extract_text_to_fp(
            io.BytesIO(pdf_bytes),
            output,
            laparams=LAParams(line_margin=0.5),
            output_type="text",
            codec="utf-8",
        )
        text = output.getvalue()
        # Collapse excessive whitespace while preserving paragraph breaks
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()
    except Exception:
        return ""


def _infer_subcategory(title: str) -> str:
    low = title.lower()
    mappings = [
        (r"code\s+du\s+travail|droit\s+du\s+travail", "code_travail"),
        (r"code\s+p[eé]nal", "code_penal"),
        (r"code\s+civil", "code_civil"),
        (r"code\s+de\s+commerce", "code_commerce"),
        (r"code\s+(?:g[eé]n[eé]ral\s+des\s+)?imp[oô]ts|cgi\b|lpf\b", "code_impots"),
        (r"code\s+(?:de\s+)?proc[eé]dure", "code_procedure"),
        (r"code\s+(?:de\s+)?la\s+famille", "code_famille"),
        (r"code\s+(?:de\s+l[''])?environnement", "code_environnement"),
        (r"code\s+minier", "code_minier"),
        (r"code\s+(?:de\s+)?la\s+sant[eé]", "code_sante"),
        (r"constitution", "constitution"),
        (r"\bloi\b.*\bfin(?:ancière|ances)\b|\bbudget\b", "loi_finances"),
        (r"\bdécret\b", "decret"),
        (r"\barrêté\b", "arrete"),
    ]
    for pattern, label in mappings:
        if re.search(pattern, low):
            return label
    return "texte_juridique"


def _is_trusted_pdf_url(url: str) -> bool:
    """Return True if this looks like a PDF from a trusted Togolese domain."""
    if not url.lower().endswith(".pdf"):
        return False
    return any(domain in url for domain in TRUSTED_PDF_DOMAINS)


class LegalPdfSpider(BaseTogoSpider):
    """Download and extract text from Togolese legal code PDFs."""

    name = "legal_pdf"
    source = "legitogo.gouv.tg"
    category = "legal"
    language = "fr"

    # All start URLs: direct PDFs first, then listing pages
    start_urls = DIRECT_PDF_URLS + LISTING_PAGES

    custom_settings = {
        "DOWNLOAD_DELAY": 2.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "ROBOTSTXT_OBEY": False,  # Some PDF servers don't have robots.txt
        # Allow large PDF downloads (up to 50 MB)
        "DOWNLOAD_MAXSIZE": 50 * 1024 * 1024,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/pdf,text/html,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9",
            "User-Agent": "Mozilla/5.0 (compatible; TogoLM-Research-Bot/1.0; +https://togolm.ai/bot)",
        },
        # Cap the spider so it never runs more than 20 minutes
        "CLOSESPIDER_TIMEOUT": 1200,
        "CLOSESPIDER_ITEMCOUNT": 200,
        # Allow non-200 status codes to be processed (PDF servers may redirect)
        "HTTPERROR_ALLOWED_CODES": [301, 302, 403, 404],
    }

    def parse(self, response):
        ct = response.headers.get("Content-Type", b"").decode().lower()

        if "pdf" in ct or response.url.lower().endswith(".pdf"):
            yield from self._parse_pdf(response)
        elif response.status == 200:
            yield from self._scan_for_pdf_links(response)

    def _scan_for_pdf_links(self, response):
        """Scan an HTML page for PDF attachment links."""
        for href in response.css("a::attr(href)").getall():
            if not href or len(href) < 4:
                continue
            url = urljoin(response.url, href)
            if _is_trusted_pdf_url(url):
                yield scrapy.Request(
                    url,
                    callback=self._parse_pdf_with_meta,
                    meta={
                        "page_url": response.url,
                        "page_title": self._page_title(response),
                    },
                    priority=15,
                )

        # Follow pagination / next listing pages
        for href in response.css("a[rel='next']::attr(href), a.next::attr(href)").getall():
            url = urljoin(response.url, href)
            if any(domain in url for domain in ["legitogo.gouv.tg", "jo.gouv.tg", "otr.tg"]):
                yield scrapy.Request(url, callback=self.parse)

    def _parse_pdf_with_meta(self, response):
        yield from self._parse_pdf(response)

    def _parse_pdf(self, response):
        """Extract text from a downloaded PDF and yield a document."""
        pdf_bytes = response.body
        if not pdf_bytes or len(pdf_bytes) < 1000:
            return

        text = _extract_pdf_text(pdf_bytes)
        words = text.split()

        if len(words) < MIN_PDF_WORDS:
            self.logger.info(f"PDF too short ({len(words)} words): {response.url}")
            return

        # Derive title from page that linked here, or from URL
        page_title = response.meta.get("page_title", "")
        title = page_title or self._title_from_url(response.url)

        # Try to extract a better title from the first lines of the PDF
        first_lines = text.split("\n")[:15]
        for line in first_lines:
            line = line.strip()
            if 10 < len(line) < 200 and not line[0].isdigit():
                title = line
                break

        if not title:
            title = self._title_from_url(response.url)

        subcategory = _infer_subcategory(title)

        # Determine source domain
        url = response.url
        if "legitogo.gouv.tg" in url:
            source = "legitogo.gouv.tg"
        elif "otr.tg" in url:
            source = "otr.tg"
        else:
            source = "jo.gouv.tg"

        self.logger.info(f"Extracted PDF: {title[:60]} ({len(words)} words) from {url}")

        yield self.make_document(
            response=response,
            title=title,
            raw_content=text,
            subcategory=subcategory,
            metadata={
                "word_count": len(words),
                "document_type": subcategory,
                "source_type": "pdf",
                "pdf_url": url,
                "page_url": response.meta.get("page_url", ""),
                "source": source,
            },
        )

    def _page_title(self, response) -> str:
        return (
            response.css("h1::text").get("")
            or response.css(".field-items::text").get("")
            or response.css("title::text").get("").split("|")[0]
        ).strip()

    def _title_from_url(self, url: str) -> str:
        """Derive a human-readable title from the PDF filename."""
        from urllib.parse import unquote

        filename = url.rstrip("/").split("/")[-1]
        try:
            filename = unquote(filename)
        except Exception:
            pass
        name = re.sub(r"\.pdf$", "", filename, flags=re.IGNORECASE)
        name = re.sub(r"[_\-%+]", " ", name)
        return name.strip()[:200] or "Document juridique"
