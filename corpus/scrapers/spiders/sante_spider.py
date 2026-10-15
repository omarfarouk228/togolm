"""
Spider for the Ministry of Health (sante-assurances.gouv.tg).

sante.gouv.tg now 301-redirects to sante-assurances.gouv.tg, a React SPA:
every URL (sitemaps included) returns the same HTML shell, so the old
sitemap-based crawl in gouv_ministry found nothing. The content comes from a
WordPress backend whose REST API is public:

  https://bk.sante.gouv.tg/wp-json/wp/v2/posts   (~640 articles)

Articles are read straight from the API and stored under their public URL
(https://sante-assurances.gouv.tg/actualites/{slug}), the one the SPA serves.

The "Documentation" section (~90 entries: clinical guides, health accounts,
bulletins, calls for applications) is a custom post type whose entries only
point to a PDF attachment (acf.document). Each PDF is downloaded, its text
extracted, and stored under the PDF's own URL. PDFs already in the database
are not downloaded again (SKIP_KNOWN_URLS): together they weigh ~100 MB.
"""

import html
import json
import re

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider
from scrapers.spiders.legal_pdf_spider import MIN_PDF_WORDS, _extract_pdf_text

API = "https://bk.sante.gouv.tg/wp-json/wp/v2"
PUBLIC_ARTICLE_URL = "https://sante-assurances.gouv.tg/actualites/{slug}"
PER_PAGE = 100
POST_FIELDS = "id,slug,date,title,content,categories"
DOCUMENTATION_FIELDS = "id,date,title,acf"

# Documentation entries have no taxonomy: subcategory from title keywords
# (whole words, accents kept), first match wins. Calls for applications come
# first: "AMI ... plan stratégique" is a recruitment, not a policy.
DOCUMENT_SUBCATEGORIES = [
    (
        ("recrute", "recrutement", "ami", "aao", "avis", "appel", "concours", "poste"),
        "avis",
    ),
    (("communiqué", "communique"), "communique"),
    (("loi", "décret", "decret", "arrêté", "arrete"), "texte"),
    (("guide", "protocole", "directives", "normes", "manuel", "dictionnaire"), "guide"),
    (
        (
            "rapport",
            "rap",
            "annuel",
            "comptes",
            "annuaire",
            "bulletin",
            "enquête",
            "etude",
            "étude",
        ),
        "rapport",
    ),
    (("plan", "politique", "stratégique", "strategique", "pnds", "policy"), "politique"),
]

# WordPress category slug -> subcategory. Unlisted slugs ("non-classe",
# "news", "actualite"...) fall back to "actualite".
SUBCATEGORY_MAP = {
    "avis-et-annonces": "avis",
    "communique": "communique",
    "communication-amu": "assurance-maladie",
    "discours": "discours",
    "deplacements-visites": "visite",
    "atelier": "evenement",
    "conference": "evenement",
    "seminaire": "evenement",
    "evenements": "evenement",
    "revue-de-presse": "presse",
    "document": "document",
}


class SanteSpider(BaseTogoSpider):
    name = "sante"
    source = "sante-assurances.gouv.tg"
    category = "health"
    language = "fr"

    custom_settings = {
        "DOWNLOAD_DELAY": 1.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_MAXSIZE": 50 * 1024 * 1024,
        "SKIP_KNOWN_URLS": True,
    }

    # Categories first (id -> slug, for subcategories), then posts and
    # documentation.
    start_urls = [f"{API}/categories?per_page=100&_fields=id,slug"]

    def parse(self, response):
        self.category_slugs = {c["id"]: c["slug"] for c in json.loads(response.text)}
        yield self._posts_request(page=1)
        yield self._documentation_request(page=1)

    def _posts_request(self, page: int) -> scrapy.Request:
        return scrapy.Request(
            f"{API}/posts?per_page={PER_PAGE}&page={page}&_fields={POST_FIELDS}",
            callback=self.parse_posts,
            cb_kwargs={"page": page},
        )

    def parse_posts(self, response, page: int):
        for post in json.loads(response.text):
            doc = self._post_to_document(response, post)
            if doc:
                yield doc

        total_pages = int(response.headers.get("X-WP-TotalPages", b"1").decode() or 1)
        if page < total_pages:
            yield self._posts_request(page + 1)

    def _post_to_document(self, response, post: dict):
        title = html.unescape(post.get("title", {}).get("rendered", "")).strip()
        raw_content = self.html_to_text(post.get("content", {}).get("rendered", ""))
        if len(title) < 5 or len(raw_content.split()) < 20:
            return None

        doc = self.make_document(
            response=response,
            title=title,
            raw_content=raw_content,
            subcategory=self._subcategory(post.get("categories", [])),
            published_at=(post.get("date") or "")[:10] or None,
            metadata={"word_count": len(raw_content.split()), "wp_id": post.get("id")},
        )
        doc["url"] = PUBLIC_ARTICLE_URL.format(slug=post["slug"])
        return doc

    # ── Documentation (PDF attachments) ──────────────────────────────────────

    def _documentation_request(self, page: int) -> scrapy.Request:
        return scrapy.Request(
            f"{API}/documentation?per_page={PER_PAGE}&page={page}&_fields={DOCUMENTATION_FIELDS}",
            callback=self.parse_documentation,
            cb_kwargs={"page": page},
        )

    def parse_documentation(self, response, page: int):
        entries = {}
        for entry in json.loads(response.text):
            acf = entry.get("acf") or {}
            attachment_id = acf.get("document") if isinstance(acf, dict) else None
            if isinstance(attachment_id, int):
                entries[attachment_id] = entry

        # One media request per listing page (<= PER_PAGE ids) resolves the
        # attachment ids to PDF URLs.
        if entries:
            ids = ",".join(str(i) for i in entries)
            yield scrapy.Request(
                f"{API}/media?per_page={PER_PAGE}&include={ids}&_fields=id,mime_type,source_url",
                callback=self.parse_media,
                cb_kwargs={"entries": entries},
            )

        total_pages = int(response.headers.get("X-WP-TotalPages", b"1").decode() or 1)
        if page < total_pages:
            yield self._documentation_request(page + 1)

    def parse_media(self, response, entries: dict):
        for media in json.loads(response.text):
            entry = entries.get(media.get("id"))
            if not entry or media.get("mime_type") != "application/pdf":
                continue
            yield scrapy.Request(
                media["source_url"],
                callback=self.parse_pdf,
                cb_kwargs={"entry": entry},
                priority=-1,
            )

    def parse_pdf(self, response, entry: dict):
        raw_content = _extract_pdf_text(response.body)
        word_count = len(raw_content.split())
        if word_count < MIN_PDF_WORDS:
            self.logger.info("PDF too short (%d words): %s", word_count, response.url)
            return

        title = html.unescape(entry.get("title", {}).get("rendered", "")).strip()
        if len(title) < 5:
            title = response.url.rsplit("/", 1)[-1].removesuffix(".pdf").replace("-", " ")
        yield self.make_document(
            response=response,
            title=title,
            raw_content=raw_content,
            subcategory=self._document_subcategory(title),
            published_at=(entry.get("date") or "")[:10] or None,
            metadata={"word_count": word_count, "wp_id": entry.get("id"), "format": "pdf"},
        )

    @staticmethod
    def _document_subcategory(title: str) -> str:
        words = set(re.findall(r"[^\W_]+", title.lower()))
        for keywords, sub in DOCUMENT_SUBCATEGORIES:
            if words.intersection(keywords):
                return sub
        return "document"

    def _subcategory(self, category_ids: list[int]) -> str:
        slugs = getattr(self, "category_slugs", {})
        for cid in category_ids:
            sub = SUBCATEGORY_MAP.get(slugs.get(cid, ""))
            if sub:
                return sub
        return "actualite"
