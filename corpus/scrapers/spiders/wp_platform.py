"""
Base spider for the government's React platform (sante, numerique,
diplomatie... .gouv.tg).

Those sites are React SPAs: every URL, sitemaps included, returns the same
HTML shell, so sitemap crawls find nothing (environnement.gouv.tg silently
stopped updating that way in June 2026). The content comes from a WordPress
backend whose REST API is public: https://bk.<site>.gouv.tg/wp-json/wp/v2.

Articles are read from /posts and stored under their public URL
(https://<site>/actualites/{slug}), the one the SPA serves. The
"Documentation" section is a custom post type whose entries only point to a
PDF attachment (acf.document): each PDF is downloaded, its text extracted,
and stored under the PDF's own URL. PDFs already in the database are not
downloaded again (SKIP_KNOWN_URLS).
"""

import html
import json
import re
from urllib.parse import urlparse

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider, parse_date
from scrapers.spiders.legal_pdf_spider import MIN_PDF_WORDS, _extract_pdf_text

PER_PAGE = 100
POST_FIELDS = "id,slug,link,date,title,content,categories"
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


class WordPressPlatformSpider(BaseTogoSpider):
    """Sites of the government's React platform, read from their public
    WordPress REST API (bk.<site>.gouv.tg/wp-json/wp/v2).

    Subclasses list their sites in SITES: {"api": "https://bk.x.gouv.tg",
    "public": "https://x.gouv.tg", "source": "x.gouv.tg", "category": ...}.
    Every request goes to a site's bk.* host (API calls and its PDF uploads),
    which tells which site a response belongs to.

    Optional site keys, for ordinary WordPress sites with an open REST API:
    "public": None stores articles under the post's own link; "documentation":
    False skips the documentation post type; "subcategories" maps the site's
    category slugs to subcategories (checked before SUBCATEGORY_MAP).
    """

    SITES: list[dict] = []
    language = "fr"
    # With SKIP_KNOWN_URLS (daily news crawl), read only this many pages of the
    # newest posts instead of the whole archive. None: always everything.
    incremental_pages: int | None = None

    custom_settings = {
        "DOWNLOAD_DELAY": 1.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "DOWNLOAD_MAXSIZE": 50 * 1024 * 1024,
        "SKIP_KNOWN_URLS": True,
    }

    def __init__(self, *args, sites=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Optional comma-separated filter, e.g. -a sites=numerique.gouv.tg
        wanted = set(sites.split(",")) if sites else None
        self.sites = [s for s in self.SITES if wanted is None or s["source"] in wanted]
        self.category_slugs: dict[str, dict[int, str]] = {}

    async def start(self):
        # Categories first (id -> slug, for subcategories), then posts and
        # documentation.
        for site in self.sites:
            yield scrapy.Request(
                f"{site['api']}/wp-json/wp/v2/categories?per_page=100&_fields=id,slug",
                callback=self.parse,
            )

    def _site(self, url: str) -> dict:
        host = urlparse(url).netloc
        return next(s for s in self.SITES if urlparse(s["api"]).netloc == host)

    def _api(self, url: str) -> str:
        return f"{self._site(url)['api']}/wp-json/wp/v2"

    def parse(self, response):
        if response.status != 200:
            return
        host = urlparse(response.url).netloc
        self.category_slugs[host] = {c["id"]: c["slug"] for c in json.loads(response.text)}
        yield self._posts_request(response.url, page=1)
        if self._site(response.url).get("documentation", True):
            yield self._documentation_request(response.url, page=1)

    def _posts_request(self, url: str, page: int) -> scrapy.Request:
        return scrapy.Request(
            f"{self._api(url)}/posts?per_page={PER_PAGE}&page={page}&_fields={POST_FIELDS}",
            callback=self.parse_posts,
            cb_kwargs={"page": page},
        )

    def parse_posts(self, response, page: int):
        if response.status != 200:
            return
        for post in json.loads(response.text):
            doc = self._post_to_document(response, post)
            if doc:
                yield doc

        total_pages = int(response.headers.get("X-WP-TotalPages", b"1").decode() or 1)
        settings = getattr(self, "settings", None)  # unset outside a crawl (tests)
        if self.incremental_pages and settings and settings.getbool("SKIP_KNOWN_URLS"):
            total_pages = min(total_pages, self.incremental_pages)
        if page < total_pages:
            yield self._posts_request(response.url, page + 1)

    def _post_to_document(self, response, post: dict):
        title = html.unescape(post.get("title", {}).get("rendered", "")).strip()
        raw_content = self.html_to_text(post.get("content", {}).get("rendered", ""))
        if len(title) < 5 or len(raw_content.split()) < 20:
            return None

        doc = self.make_document(
            response=response,
            title=title,
            raw_content=raw_content,
            subcategory=self._subcategory(response.url, post.get("categories", [])),
            # Some sites date old posts 1970-01-01: parse_date drops those.
            published_at=parse_date(post.get("date")),
            metadata={"word_count": len(raw_content.split()), "wp_id": post.get("id")},
        )
        public = self._site(response.url).get("public")
        doc["url"] = f"{public}/actualites/{post['slug']}" if public else post["link"]
        return doc

    # ── Documentation (PDF attachments) ──────────────────────────────────────

    def _documentation_request(self, url: str, page: int) -> scrapy.Request:
        return scrapy.Request(
            f"{self._api(url)}/documentation?per_page={PER_PAGE}&page={page}"
            f"&_fields={DOCUMENTATION_FIELDS}",
            callback=self.parse_documentation,
            cb_kwargs={"page": page},
        )

    def parse_documentation(self, response, page: int):
        if response.status != 200:  # site without a documentation section
            return
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
                f"{self._api(response.url)}/media?per_page={PER_PAGE}&include={ids}"
                "&_fields=id,mime_type,source_url",
                callback=self.parse_media,
                cb_kwargs={"entries": entries},
            )

        total_pages = int(response.headers.get("X-WP-TotalPages", b"1").decode() or 1)
        if page < total_pages:
            yield self._documentation_request(response.url, page + 1)

    def parse_media(self, response, entries: dict):
        if response.status != 200:
            return
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
            published_at=parse_date(entry.get("date")),
            metadata={"word_count": word_count, "wp_id": entry.get("id"), "format": "pdf"},
        )

    @staticmethod
    def _document_subcategory(title: str) -> str:
        words = set(re.findall(r"[^\W_]+", title.lower()))
        for keywords, sub in DOCUMENT_SUBCATEGORIES:
            if words.intersection(keywords):
                return sub
        return "document"

    def _subcategory(self, url: str, category_ids: list[int]) -> str:
        slugs = self.category_slugs.get(urlparse(url).netloc, {})
        post_slugs = [slugs.get(cid, "") for cid in category_ids]
        # A site's own map is in priority order (topics before generic
        # sections: an ATOP post is filed under "a-la-une", "developpement"
        # and "sante" at once); SUBCATEGORY_MAP follows the post's order.
        for slug, sub in self._site(url).get("subcategories", {}).items():
            if slug in post_slugs:
                return sub
        for slug in post_slugs:
            if slug in SUBCATEGORY_MAP:
                return SUBCATEGORY_MAP[slug]
        return "actualite"

    def make_document(self, response, title, raw_content, **kwargs):
        """Source and category of the site the response belongs to."""
        site = self._site(response.url)
        doc = super().make_document(response, title, raw_content, **kwargs)
        doc["source"] = site["source"]
        doc["category"] = site["category"]
        return doc
