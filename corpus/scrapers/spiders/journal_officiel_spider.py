"""
Spider for jo.gouv.tg — Journal Officiel de la République Togolaise.

Collects laws, decrees, ordinances, and regulatory texts from /node/{id} pages.
Documents have clean structured metadata: title, date, domain, JO number.
"""

import re
from urllib.parse import urljoin

import scrapy

from scrapers.spiders.base_spider import BaseTogoSpider

LISTING_URLS = [
    "https://jo.gouv.tg/derniers_textes_publies",
    "https://jo.gouv.tg/derniers_journaux_officiels",
    "https://jo.gouv.tg/les_plus_consultes",
]

# Detect document type from title prefix
DOC_TYPE_RE = re.compile(
    r"^(loi|ordonnance|décret|arrêté|arrête|convention|accord|circulaire|decision)",
    re.IGNORECASE,
)

DATE_RE = re.compile(r"Date de signature\s*:\s*\w+,?\s*([\d\w\s]+\d{4})", re.IGNORECASE)


class JournalOfficielSpider(BaseTogoSpider):
    name = "journal_officiel"
    source = "jo.gouv.tg"
    category = "legal"
    language = "fr"

    start_urls = LISTING_URLS

    # jo.gouv.tg assigns sequential node IDs — we crawl down from the latest known
    MAX_NODE_ID = 15900
    MIN_NODE_ID = 14000  # ~2 years of history

    def parse(self, response):
        """Parse listing pages: follow /node/ links and discover more IDs."""
        node_links = response.css("a[href*='/node/']::attr(href)").getall()

        seen_ids: set[int] = set()
        for href in node_links:
            url = urljoin(response.url, href)
            match = re.search(r"/node/(\d+)", url)
            if match:
                seen_ids.add(int(match.group(1)))
                yield scrapy.Request(url, callback=self.parse_document)

        # From the highest ID seen, walk down to fill gaps
        if seen_ids:
            max_seen = max(seen_ids)
            for node_id in range(max_seen - 1, self.MIN_NODE_ID, -1):
                if node_id not in seen_ids:
                    yield scrapy.Request(
                        f"https://jo.gouv.tg/node/{node_id}",
                        callback=self.parse_document,
                        priority=-1,  # Lower priority than listing-discovered links
                    )

    def parse_document(self, response):
        content_el = response.css(".content")
        if not content_el:
            return

        raw_text = content_el.css("::text").getall()
        full_text = " ".join(t.strip() for t in raw_text if t.strip())

        if not full_text or len(full_text.split()) < 15:
            return

        title = self._extract_title(content_el, response.url)
        if not title:
            return

        published_at = self._extract_date(full_text)
        subcategory = self._infer_type(title)

        yield self.make_document(
            response=response,
            title=title,
            raw_content=full_text,
            subcategory=subcategory,
            published_at=published_at,
            metadata={
                "word_count": len(full_text.split()),
                "document_type": subcategory,
                "node_id": response.url.split("/node/")[-1],
            },
        )

    def _extract_title(self, content_el, url: str) -> str:
        # The listing link text (from the homepage) is the best title.
        # On the document page itself, the first meaningful text before
        # "Domaine du texte" serves as the title.
        texts = content_el.css("::text").getall()
        parts = []
        for t in texts:
            t = t.strip()
            if not t:
                continue
            if t.lower().startswith("domaine du texte"):
                break
            parts.append(t)

        title = " ".join(parts).strip()

        # If title is still empty or too short, derive from node ID
        if not title or len(title) < 5:
            node_id = url.split("/node/")[-1]
            title = f"Document JO node {node_id}"

        return title

    def _extract_date(self, text: str) -> str | None:
        match = DATE_RE.search(text)
        if match:
            return match.group(1).strip()
        return None

    def _infer_type(self, title: str) -> str:
        match = DOC_TYPE_RE.match(title.strip())
        if match:
            return match.group(1).lower()
        return "texte"
