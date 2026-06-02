"""
Spider for French Wikipedia — Togo-related articles.

Uses the MediaWiki API to retrieve all pages in the 'Togo' category tree.
Extracts clean article text via the extracts API (no HTML parsing needed).

Covers: history, politics, geography, economy, culture, education, health,
        notable people, institutions, events related to Togo.

API endpoints used:
  - Category members: /w/api.php?action=query&list=categorymembers
  - Article extracts: /w/api.php?action=query&prop=extracts&exintro=true|false
"""

import json
from urllib.parse import urlencode

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

BASE_API = "https://fr.wikipedia.org/w/api.php"

# Root Togo categories to crawl
ROOT_CATEGORIES = [
    "Catégorie:Togo",
    "Catégorie:Géographie du Togo",
    "Catégorie:Histoire du Togo",
    "Catégorie:Politique au Togo",
    "Catégorie:Économie au Togo",
    "Catégorie:Culture au Togo",
    "Catégorie:Enseignement au Togo",
    "Catégorie:Santé au Togo",
    "Catégorie:Droit au Togo",
    "Catégorie:Environnement au Togo",
    "Catégorie:Société togolaise",
    "Catégorie:Religion au Togo",
    "Catégorie:Défense et sécurité au Togo",
    "Catégorie:Communication au Togo",
]

# Subcategory depth limit
MAX_DEPTH = 3


def _api_url(**params) -> str:
    params.setdefault("format", "json")
    params.setdefault("utf8", "1")
    return BASE_API + "?" + urlencode(params)


class WikipediaSpider(BaseTogoSpider):
    name = "wikipedia"
    source = "fr.wikipedia.org"
    category = "encyclopedie"
    language = "fr"

    # Use start_urls so Scrapy's built-in start() handles URL dispatch
    # Each URL maps to parse() which routes to parse_category
    start_urls = [
        _api_url(
            action="query",
            list="categorymembers",
            cmtitle=cat,
            cmlimit=500,
            cmtype="page|subcat",
        )
        for cat in ROOT_CATEGORIES
    ]

    # Use a browser-like User-Agent (Wikipedia may rate-limit bots)
    custom_settings = {
        "USER_AGENT": "TogoLM-Bot/0.1 (+https://github.com/togolm/togolm; educational use)",
        "DOWNLOAD_DELAY": 0.5,  # Wikipedia API is fast and allows bots
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "ROBOTSTXT_OBEY": False,  # Wikipedia explicitly allows API bots
    }

    def parse(self, response):
        """Route start_urls responses to parse_category."""
        return self.parse_category(response)

    def parse_category(self, response):
        """Parse category member list, follow article links and subcategories."""
        depth = response.meta.get("depth", 0)
        data = json.loads(response.text)
        members = data.get("query", {}).get("categorymembers", [])

        for member in members:
            ns = member.get("ns", 0)
            title = member["title"]

            if ns == 14:  # Subcategory
                if depth < MAX_DEPTH:
                    yield scrapy.Request(
                        _api_url(
                            action="query",
                            list="categorymembers",
                            cmtitle=title,
                            cmlimit=500,
                            cmtype="page|subcat",
                        ),
                        callback=self.parse_category,
                        meta={"depth": depth + 1},
                    )
            elif ns == 0:  # Article
                yield scrapy.Request(
                    _api_url(
                        action="query",
                        titles=title,
                        prop="extracts|info",
                        exlimit=1,
                        explaintext=1,  # Plain text, no HTML
                        inprop="url",
                    ),
                    callback=self.parse_article,
                    meta={"title": title},
                )

        # Pagination (cmcontinue)
        cont = data.get("continue", {}).get("cmcontinue")
        if cont:
            current_url = response.url.split("cmcontinue=")[0].rstrip("&")
            yield scrapy.Request(
                current_url + f"&cmcontinue={cont}",
                callback=self.parse_category,
                meta={"depth": depth},
            )

    def parse_article(self, response):
        """Parse a Wikipedia article's plain text extract."""
        data = json.loads(response.text)
        pages = data.get("query", {}).get("pages", {})

        for page_id, page in pages.items():
            if page_id == "-1":
                continue  # Page not found

            title = page.get("title", "")
            raw_content = page.get("extract", "").strip()

            if not raw_content or len(raw_content.split()) < 30:
                continue

            # Wikipedia canonical URL
            url = (
                page.get("canonicalurl", "")
                or f"https://fr.wikipedia.org/wiki/{title.replace(' ', '_')}"
            )

            # Infer subcategory from content (first 200 chars)
            subcategory = self._infer_subcategory(title, raw_content[:200])

            yield self.make_document(
                response=response,
                title=title,
                raw_content=raw_content,
                subcategory=subcategory,
                metadata={
                    "word_count": len(raw_content.split()),
                    "page_id": page_id,
                    "source_url": url,
                },
            )

    def make_document(self, response, title, raw_content, subcategory="", **kwargs):
        """Override to use canonical Wikipedia URL instead of API URL."""
        from datetime import datetime

        from scrapers.items import DocumentItem

        meta = kwargs.get("metadata", {})
        url = meta.get("source_url", response.url)

        return DocumentItem(
            source=self.source,
            url=url,
            title=title.strip(),
            raw_content=raw_content,
            category=self.category,
            subcategory=subcategory,
            language=self.language,
            published_at=None,
            metadata={
                "scraped_at": datetime.utcnow().isoformat(),
                **meta,
            },
        )

    def _infer_subcategory(self, title: str, content_preview: str) -> str:
        keywords = {
            "politique": "politics",
            "gouvernement": "government",
            "ministre": "government",
            "élection": "politics",
            "géographie": "geography",
            "ville": "geography",
            "fleuve": "geography",
            "économie": "economy",
            "agriculture": "economy",
            "histoire": "history",
            "culture": "culture",
            "religion": "religion",
            "santé": "health",
            "éducation": "education",
            "université": "education",
            "droit": "legal",
            "loi": "legal",
        }
        text = (title + " " + content_preview).lower()
        for kw, sub in keywords.items():
            if kw in text:
                return sub
        return "encyclopedie"
