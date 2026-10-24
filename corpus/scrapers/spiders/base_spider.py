import json
import re
from datetime import datetime

import scrapy
from bs4 import BeautifulSoup
from scrapers.items import DocumentItem

FR_MONTHS = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
}
FR_DATE_RE = re.compile(r"\b(\d{1,2})(?:er)?\s+(" + "|".join(FR_MONTHS) + r")\s+(\d{4})", re.I)
ISO_DATE_RE = re.compile(r"^\s*(\d{4})-(\d{2})-(\d{2})")
URL_DATE_RE = re.compile(r"/(20\d{2})/(\d{2})/(\d{2})/")
JSONLD_DATE_KEYS = ("datePublished", "datePosted", "dateCreated")


def parse_date(raw: str | None) -> str | None:
    """ISO YYYY-MM-DD from an ISO timestamp or a French date ("vendredi, 23
    octobre 2026 17:10"), or None. Rejects implausible years."""
    if not raw:
        return None
    m = ISO_DATE_RE.match(raw)
    if m:
        y, mo, d = (int(g) for g in m.groups())
    else:
        m = FR_DATE_RE.search(raw)
        if not m:
            return None
        d, mo, y = int(m.group(1)), FR_MONTHS[m.group(2).lower()], int(m.group(3))
    try:
        date = datetime(y, mo, d)
    except ValueError:
        return None
    if not 1960 <= date.year <= datetime.utcnow().year + 1:
        return None
    if (date.year, date.month, date.day) == (1970, 1, 1):
        return None  # Unix epoch: a zero timestamp, not a date (atop.tg)
    return date.strftime("%Y-%m-%d")


def _jsonld_dates(node):
    if isinstance(node, list):
        for item in node:
            yield from _jsonld_dates(item)
    elif isinstance(node, dict):
        for key in JSONLD_DATE_KEYS:
            if isinstance(node.get(key), str):
                yield node[key]
        if "@graph" in node:
            yield from _jsonld_dates(node["@graph"])


class BaseTogoSpider(scrapy.Spider):
    """
    Base spider for all TogoLM scrapers.

    Subclasses must define:
      - name: spider identifier
      - source: human-readable source name
      - start_urls: seed URLs
      - category: corpus category (legal, education, economy, health, politics, press)

    Subclasses should override parse() and implement extract_document().
    """

    source: str = ""
    category: str = ""
    language: str = "fr"

    custom_settings = {
        "DOWNLOAD_DELAY": 1.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
    }

    def make_document(
        self,
        response,
        title: str,
        raw_content: str,
        subcategory: str = "",
        published_at: str | None = None,
        metadata: dict | None = None,
    ) -> DocumentItem:
        return DocumentItem(
            source=self.source,
            url=response.url,
            title=title.strip(),
            raw_content=raw_content,
            category=self.category,
            subcategory=subcategory,
            language=self.language,
            published_at=published_at,
            metadata={
                "scraped_at": datetime.utcnow().isoformat(),
                **(metadata or {}),
            },
        )

    @staticmethod
    def extract_published_at(response, *text_selectors: str) -> str | None:
        """Publication date of an article page as YYYY-MM-DD, or None.

        Spiders used to read only ``time::attr(datetime)`` and the
        article:published_time meta, then cut the result to 10 characters. On
        prod that left togofirst, republicoftogo, togo24 and anpetogo with no
        date at all (the date is in JSON-LD or in plain French text) and stored
        whitespace when a selector matched an empty text node. Sources tried,
        most reliable first: JSON-LD, meta tags, schema.org microdata, the
        spider's own ``text_selectors``, ``<time datetime>``, then a
        /YYYY/MM/DD/ URL.
        """
        candidates: list[str] = []
        for script in response.css("script[type='application/ld+json']::text").getall():
            try:
                candidates.extend(_jsonld_dates(json.loads(script)))
            except ValueError:
                continue
        candidates += response.css(
            "meta[property='article:published_time']::attr(content),"
            " meta[itemprop='datePublished']::attr(content),"
            " [itemprop='datePublished']::attr(datetime),"
            " [itemprop='datePublished']::attr(content)"
        ).getall()
        candidates.append(" ".join(response.css("[itemprop='datePublished'] ::text").getall()))
        for selector in text_selectors:
            candidates.append(" ".join(response.css(f"{selector} ::text").getall()))
        candidates += response.css("time::attr(datetime)").getall()[:1]
        for raw in candidates:
            date = parse_date(raw)
            if date:
                return date
        m = URL_DATE_RE.search(response.url)
        return parse_date("-".join(m.groups())) if m else None

    @staticmethod
    def html_to_text(html: str) -> str:
        """Convert HTML fragment to clean plain text."""
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)
