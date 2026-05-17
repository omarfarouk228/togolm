"""
Spider for republicoftogo.com — Togolese news and analysis magazine.

eZ Publish CMS site. Article URLs follow:
  /toutes-les-rubriques/{category}/{article-slug}

Articles are discovered from the homepage (section pages are JS-rendered).
Content lives in .ezxmltext-field divs inside article.view-type-full.
"""

from urllib.parse import urljoin

import scrapy

from scrapers.spiders.base_spider import BaseTogoSpider

ENTRY_URLS = [
    "https://www.republicoftogo.com/",
    "https://www.republicoftogo.com/toutes-les-rubriques/politique",
    "https://www.republicoftogo.com/toutes-les-rubriques/eco-finance",
    "https://www.republicoftogo.com/toutes-les-rubriques/societe",
    "https://www.republicoftogo.com/toutes-les-rubriques/diplomatie",
    "https://www.republicoftogo.com/toutes-les-rubriques/culture",
    "https://www.republicoftogo.com/toutes-les-rubriques/sante",
    "https://www.republicoftogo.com/toutes-les-rubriques/environnement",
    "https://www.republicoftogo.com/toutes-les-rubriques/education",
    "https://www.republicoftogo.com/toutes-les-rubriques/justice",
    "https://www.republicoftogo.com/toutes-les-rubriques/sport",
]

EXCLUDED_PATHS = [
    "/connexion", "/inscription", "/recherche", "/contact",
    "/content/search", "/bundles/", "/tendances/",
    "#", "mailto:", "javascript:",
]


class RepublicoftogoSpider(BaseTogoSpider):
    name = "republicoftogo"
    source = "republicoftogo.com"
    category = "press"
    language = "fr"

    start_urls = ENTRY_URLS

    custom_settings = {
        "DOWNLOAD_DELAY": 2,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
    }

    def parse(self, response):
        for href in response.css("a::attr(href)").getall():
            url = urljoin(response.url, href)
            if self._is_article_url(url):
                yield scrapy.Request(url, callback=self.parse_article, priority=10)

    def parse_article(self, response):
        # eZ Publish: <h1 class="full-page-title"><span class="ezstring-field">Title</span></h1>
        title = (
            response.css("h1 .ezstring-field::text").get("") or
            response.css("h1 *::text").get("") or
            response.css("h1::text").get("")
        ).strip()

        if not title or len(title) < 5:
            return

        # Main article body: article.view-type-full contains the actual article;
        # article.view-type-standard elements are related-article previews.
        body_html = response.css("article.view-type-full .ezxmltext-field").get("")
        if not body_html:
            body_html = response.css("article.view-type-full").get("")
        raw_content = self.html_to_text(body_html) if body_html else ""

        if not raw_content or len(raw_content.split()) < 30:
            # Fallback: gather all paragraphs from the full article
            paragraphs = response.css(
                "article.view-type-full p::text, "
                ".full-page-intro p::text, "
                ".ezxmltext-field p::text"
            ).getall()
            raw_content = " ".join(p.strip() for p in paragraphs if p.strip())

        if not raw_content or len(raw_content.split()) < 30:
            return

        published_at = (
            response.css(".publish-date::text").get("") or
            response.css("time::attr(datetime)").get("") or
            response.css("meta[property='article:published_time']::attr(content)").get("") or
            ""
        )

        subcategory = self._infer_subcategory(response.url)

        yield self.make_document(
            response=response,
            title=title,
            raw_content=raw_content,
            subcategory=subcategory,
            published_at=published_at[:10] if published_at else None,
            metadata={"word_count": len(raw_content.split())},
        )

        # Follow related article links found within the article page
        for href in response.css("a::attr(href)").getall():
            url = urljoin(response.url, href)
            if self._is_article_url(url):
                yield scrapy.Request(url, callback=self.parse_article, priority=5)

    def _is_article_url(self, url: str) -> bool:
        if "republicoftogo.com" not in url:
            return False
        if any(e in url.lower() for e in EXCLUDED_PATHS):
            return False
        path = url.split("republicoftogo.com")[-1].lower()
        # Articles: /toutes-les-rubriques/{category}/{slug} — exactly 3 segments
        segments = [s for s in path.split("/") if s]
        return (
            len(segments) == 3
            and segments[0] == "toutes-les-rubriques"
            and len(segments[2]) > 5
        )

    def _infer_subcategory(self, url: str) -> str:
        mapping = {
            "politique": "politics",
            "eco-finance": "economy",
            "societe": "society",
            "diplomatie": "diplomacy",
            "sport": "sport",
            "culture": "culture",
            "sante": "health",
            "environnement": "environment",
            "education": "education",
            "justice": "justice",
        }
        url_lower = url.lower()
        for key, sub in mapping.items():
            if f"/{key}/" in url_lower or url_lower.endswith(f"/{key}"):
                return sub
        return "news"
