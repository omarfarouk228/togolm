"""
PDF extraction spider for Togolese legal codes.

Downloads PDF files linked from jo.gouv.tg and legitogo.gouv.tg document
pages and extracts their full text using pdfminer.six.

These PDFs contain the actual text of major laws that the jo.gouv.tg HTML
pages only describe with metadata (title, date, JO number).

Priority targets:
  - Code du Travail (Loi 2021-012)
  - Code Pénal (Loi 2015-010)
  - Code de Procédure Pénale
  - Code Civil (applicable)
  - Code de Commerce
  - Code Général des Impôts
  - Code de l'Environnement
  - Code de la Famille

Run:
    scrapy crawl legal_pdf
    scrapy crawl legal_pdf -a min_node=8000 -a max_node=16000
"""

import io
import re
from urllib.parse import urljoin

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

# Known PDF links for critical codes (direct, reliable)
PRIORITY_PDF_URLS = [
    # Code du Travail 2021 — multiple mirrors
    "https://legitogo.gouv.tg/annee_txt/2021/Pages%20de%20JO%2066%20E%20ANNEE%20N%2026%20TER%20du%2018%20juin%202021.pdf",
    "https://legitogo.gouv.tg/annee_txt/2022/Pages%20de%20jo67eN49bis.pdf",
    # Code Général des Impôts — OTR publishes it
    "https://otr.tg/images/pdf/CGI_Togo_2024.pdf",
    "https://otr.tg/images/pdf/LPF_Togo_2024.pdf",
]

# jo.gouv.tg node ranges known to have PDF attachments for major codes
# These were identified from the node IDs returned by the existing journal_officiel spider
CODE_NODE_IDS = list(range(14000, 16001, 1))  # Recent laws 2020-2024

# Regex to detect PDF links in page content
PDF_LINK_RE = re.compile(r'href=["\']([^"\']+\.pdf)["\']', re.IGNORECASE)

# Minimum words extracted from a PDF to consider it valid
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
    except Exception as e:
        return ""


def _infer_subcategory(title: str) -> str:
    low = title.lower()
    mappings = [
        (r"code\s+du\s+travail|droit\s+du\s+travail", "code_travail"),
        (r"code\s+p[eé]nal", "code_penal"),
        (r"code\s+civil", "code_civil"),
        (r"code\s+de\s+commerce", "code_commerce"),
        (r"code\s+(?:g[eé]n[eé]ral\s+des\s+)?imp[oô]ts|cgi\b", "code_impots"),
        (r"code\s+(?:de\s+)?proc[eé]dure", "code_procedure"),
        (r"code\s+(?:de\s+)?la\s+famille", "code_famille"),
        (r"code\s+(?:de\s+l['’])?environnement", "code_environnement"),
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


class LegalPdfSpider(BaseTogoSpider):
    """Download and extract text from Togolese legal code PDFs."""

    name = "legal_pdf"
    source = "jo.gouv.tg"
    category = "legal"
    language = "fr"

    # Accept PDF responses
    custom_settings = {
        "DOWNLOAD_DELAY": 2.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
        "ROBOTSTXT_OBEY": True,
        # Allow large PDF downloads (up to 50 MB)
        "DOWNLOAD_MAXSIZE": 50 * 1024 * 1024,
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "application/pdf,text/html,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9",
        },
    }

    def __init__(self, *args, min_node: int = 12000, max_node: int = 16000, **kwargs):
        super().__init__(*args, **kwargs)
        self.min_node = int(min_node)
        self.max_node = int(max_node)

    @property
    def start_urls(self) -> list[str]:
        urls = []
        # 1. Priority PDFs (known direct links)
        urls.extend(PRIORITY_PDF_URLS)
        # 2. jo.gouv.tg document pages to scan for PDF links
        urls.extend(
            f"https://jo.gouv.tg/node/{nid}"
            for nid in range(self.max_node, self.min_node - 1, -1)
        )
        # 3. legitogo.gouv.tg main pages
        urls += [
            "https://legitogo.gouv.tg/codes",
            "https://legitogo.gouv.tg/lois",
            "https://legitogo.gouv.tg",
        ]
        return urls

    def parse(self, response):
        ct = response.headers.get("Content-Type", b"").decode().lower()

        if "pdf" in ct or response.url.lower().endswith(".pdf"):
            yield from self._parse_pdf(response)
        else:
            yield from self._scan_for_pdf_links(response)

    def _scan_for_pdf_links(self, response):
        """Scan an HTML page for PDF attachment links."""
        # Look for explicit PDF <a href> links
        for href in response.css("a::attr(href)").getall():
            if not href:
                continue
            if href.lower().endswith(".pdf") or "pdf" in href.lower():
                pdf_url = urljoin(response.url, href)
                if any(d in pdf_url for d in ("jo.gouv.tg", "legitogo.gouv.tg", "otr.tg")):
                    yield scrapy.Request(
                        pdf_url,
                        callback=self.parse,
                        meta={"page_url": response.url, "page_title": self._page_title(response)},
                        priority=10,
                    )

    def _parse_pdf(self, response):
        """Extract text from a downloaded PDF and yield a document."""
        pdf_bytes = response.body
        if not pdf_bytes or len(pdf_bytes) < 1000:
            return

        text = _extract_pdf_text(pdf_bytes)
        words = text.split()

        if len(words) < MIN_PDF_WORDS:
            return

        # Derive title from the page that linked here, or from URL
        page_title = response.meta.get("page_title", "")
        title = page_title or self._title_from_url(response.url)

        # Try to extract a better title from the first lines of the PDF
        first_lines = "\n".join(text.split("\n")[:10])
        for line in first_lines.split("\n"):
            line = line.strip()
            if 10 < len(line) < 200 and not line.startswith("Page"):
                # Looks like a title line
                title = line
                break

        if not title:
            title = self._title_from_url(response.url)

        subcategory = _infer_subcategory(title)

        # Determine source from URL
        source = "jo.gouv.tg"
        if "legitogo.gouv.tg" in response.url:
            source = "legitogo.gouv.tg"
        elif "otr.tg" in response.url:
            source = "otr.tg"

        yield self.make_document(
            response=response,
            title=title,
            raw_content=text,
            subcategory=subcategory,
            metadata={
                "word_count": len(words),
                "document_type": subcategory,
                "source_type": "pdf",
                "pdf_url": response.url,
                "page_url": response.meta.get("page_url", ""),
            },
        )
        # Override source
        # (make_document sets self.source which is "jo.gouv.tg")

    def _page_title(self, response) -> str:
        return (
            response.css("h1::text").get("")
            or response.css(".field-items::text").get("")
            or response.css("title::text").get("").split("|")[0]
        ).strip()

    def _title_from_url(self, url: str) -> str:
        """Derive a human-readable title from the PDF filename."""
        filename = url.rstrip("/").split("/")[-1]
        # URL-decode and strip extension
        try:
            from urllib.parse import unquote
            filename = unquote(filename)
        except Exception:
            pass
        name = re.sub(r"\.pdf$", "", filename, flags=re.IGNORECASE)
        name = re.sub(r"[_\-%]", " ", name)
        return name.strip()[:200] or "Document juridique"
