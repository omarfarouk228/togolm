"""
Spider for dnccp.gouv.tg — Direction nationale du contrôle de la commande
publique (public procurement).

~1,800 documents (2026): procurement plans of every public body ("Plans de
Passation", incl. those reserved for young and women entrepreneurs, JFE),
extracts of the public procurement journal (JMP, where tenders are
announced), decrees and thresholds, standard bidding documents, the price
list (mercuriale). The basis of a procurement watch: who plans to buy what,
when.

Documents are listed from the WordPress REST API (custom type "document",
which has no text), then each page is read for its attached file (PDF), whose
text is stored under the document's page URL. Already-ingested pages are not
fetched again (SKIP_KNOWN_URLS).
"""

import html
import json

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider, parse_date
from scrapers.spiders.legal_pdf_spider import MIN_PDF_WORDS, _extract_pdf_text

API = "https://dnccp.gouv.tg/wp-json/wp/v2"
PER_PAGE = 100

# Category name (lowercased, accents kept) -> subcategory, first match wins.
SUBCATEGORIES = [
    ("jfe", "plan-passation-jfe"),
    ("plans de passation", "plan-passation"),
    ("extrait jmp", "journal-marches-publics"),
    ("décrets", "texte"),
    ("arrêtés", "texte"),
    ("directives", "texte"),
    ("nouveaux seuils", "texte"),
    ("dossiers types", "dossier-type"),
    ("mercuriale", "mercuriale"),
    ("avis généraux", "avis-general"),
    ("lettres circulaires", "circulaire"),
]


class DnccpSpider(BaseTogoSpider):
    name = "dnccp"
    source = "dnccp.gouv.tg"
    category = "economy"

    custom_settings = {
        "DOWNLOAD_DELAY": 1.0,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_MAXSIZE": 50 * 1024 * 1024,
        "SKIP_KNOWN_URLS": True,
    }

    start_urls = [f"{API}/categorie_document?per_page=100&_fields=id,name"]

    def parse(self, response):
        self.category_names = {
            c["id"]: html.unescape(c["name"]).lower() for c in json.loads(response.text)
        }
        yield self._list_request(1)

    def _list_request(self, page: int) -> scrapy.Request:
        return scrapy.Request(
            f"{API}/document?per_page={PER_PAGE}&page={page}"
            "&_fields=id,date,title,link,categorie_document",
            callback=self.parse_list,
            cb_kwargs={"page": page},
        )

    def parse_list(self, response, page: int):
        for doc in json.loads(response.text):
            yield scrapy.Request(
                doc["link"], callback=self.parse_page, cb_kwargs={"doc": doc}, priority=5
            )
        total_pages = int(response.headers.get("X-WP-TotalPages", b"1").decode() or 1)
        if page < total_pages:
            yield self._list_request(page + 1)

    def parse_page(self, response, doc: dict):
        files = response.css("a[href$='.pdf']::attr(href), a[href$='.PDF']::attr(href)").getall()
        if files:
            yield scrapy.Request(
                response.urljoin(files[0]),
                callback=self.parse_file,
                cb_kwargs={"doc": doc, "page_url": response.url},
                # Files before further pages: documents come in as the crawl
                # goes instead of after ~1,800 page visits.
                priority=10,
            )

    def parse_file(self, response, doc: dict, page_url: str):
        text = _extract_pdf_text(response.body)
        if len(text.split()) < MIN_PDF_WORDS:
            return
        title = html.unescape(doc.get("title", {}).get("rendered", "")).strip()
        item = self.make_document(
            response=response,
            title=title or page_url.rstrip("/").rsplit("/", 1)[-1].replace("-", " "),
            raw_content=text,
            subcategory=self._subcategory(doc.get("categorie_document", [])),
            published_at=parse_date(doc.get("date")),
            metadata={
                "word_count": len(text.split()),
                "wp_id": doc.get("id"),
                "file": response.url,
            },
        )
        item["url"] = page_url
        yield item

    def _subcategory(self, category_ids: list[int]) -> str:
        names = [getattr(self, "category_names", {}).get(cid, "") for cid in category_ids]
        for needle, sub in SUBCATEGORIES:
            if any(needle in name for name in names):
                return sub
        return "document"
