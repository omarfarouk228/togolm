"""
Spider for the Ministry of Health (sante-assurances.gouv.tg).

sante.gouv.tg now 301-redirects to sante-assurances.gouv.tg, a React SPA:
every URL (sitemaps included) returns the same HTML shell, so the old
sitemap-based crawl in gouv_ministry found nothing. The content comes from a
WordPress backend whose REST API is public:

  https://bk.sante.gouv.tg/wp-json/wp/v2/posts   (~640 articles)

Articles are read straight from the API and stored under their public URL
(https://sante-assurances.gouv.tg/actualites/{slug}), the one the SPA serves.
"""

import html
import json

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

API = "https://bk.sante.gouv.tg/wp-json/wp/v2"
PUBLIC_ARTICLE_URL = "https://sante-assurances.gouv.tg/actualites/{slug}"
PER_PAGE = 100
POST_FIELDS = "id,slug,date,title,content,categories"

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
    }

    # Categories first (id -> slug, for subcategories), then the posts.
    start_urls = [f"{API}/categories?per_page=100&_fields=id,slug"]

    def parse(self, response):
        self.category_slugs = {c["id"]: c["slug"] for c in json.loads(response.text)}
        yield self._posts_request(page=1)

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

    def _subcategory(self, category_ids: list[int]) -> str:
        slugs = getattr(self, "category_slugs", {})
        for cid in category_ids:
            sub = SUBCATEGORY_MAP.get(slugs.get(cid, ""))
            if sub:
                return sub
        return "actualite"
