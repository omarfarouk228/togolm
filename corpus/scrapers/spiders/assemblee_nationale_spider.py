"""
Spider for assemblee-nationale.tg — Togolese National Assembly.

Collects:
  - Laws (lois) and ordinances
  - Decrees (décrets)
  - Parliamentary debates and session reports
  - Press releases and communiqués
  - Committee reports
"""

from urllib.parse import urljoin

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider


class AssembleeNationaleSpider(BaseTogoSpider):
    name = "assemblee_nationale"
    source = "assemblee-nationale.tg"
    category = "legal"
    language = "fr"

    start_urls = [
        "https://www.assemblee-nationale.tg/",
        "https://www.assemblee-nationale.tg/lois/",
        "https://www.assemblee-nationale.tg/actualites/",
        "https://www.assemblee-nationale.tg/communiques/",
    ]

    content_path_keywords = [
        "loi",
        "lois",
        "decret",
        "ordonnance",
        "resolution",
        "actualite",
        "actualites",
        "communique",
        "seance",
        "rapport",
        "commission",
        "debat",
        "article",
    ]

    denied_paths = ["/login", "/admin", "/search", "/api", "/wp-admin"]

    def parse(self, response):
        yield from self._follow_content_links(response)
        yield from self._follow_navigation(response)

    def _follow_navigation(self, response):
        nav_links = response.css(
            "nav a::attr(href), "
            ".menu a::attr(href), "
            ".nav a::attr(href), "
            "a[rel='next']::attr(href), "
            "a.next::attr(href), "
            ".pagination a::attr(href)"
        ).getall()

        for href in set(nav_links):
            url = urljoin(response.url, href)
            if self._should_follow(url):
                yield scrapy.Request(url, callback=self.parse)

    def _follow_content_links(self, response):
        all_links = response.css("a::attr(href)").getall()

        for href in set(all_links):
            url = urljoin(response.url, href)
            if self._is_legal_document_url(url):
                yield scrapy.Request(url, callback=self.parse_document, priority=10)
            elif self._is_article_url(url):
                yield scrapy.Request(url, callback=self.parse_article)

    def parse_document(self, response):
        """Parse a law, decree, or official document page."""
        title = self._extract_title(response)
        if not title:
            return

        # Try to get the full document text
        body_html = response.css(
            ".document-content, .loi-content, .decret-content, "
            "article, .content, .entry-content, main .text"
        ).get("")

        raw_content = self.html_to_text(body_html) if body_html else ""

        if not raw_content or len(raw_content.split()) < 20:
            paragraphs = response.css("main p::text, article p::text, .content p::text").getall()
            raw_content = " ".join(paragraphs)

        if not raw_content or len(raw_content.split()) < 20:
            return

        subcategory = self._infer_subcategory(response.url)
        published_at = self._extract_date(response)

        yield self.make_document(
            response=response,
            title=title,
            raw_content=raw_content,
            subcategory=subcategory,
            published_at=published_at,
            metadata={
                "word_count": len(raw_content.split()),
                "document_type": subcategory,
            },
        )

        yield from self._follow_content_links(response)

    def parse_article(self, response):
        """Parse a news article or press release."""
        title = self._extract_title(response)
        if not title:
            return

        body_html = response.css(
            "article, .article-body, .content, .post-content, .entry-content, main p"
        ).get("")

        raw_content = self.html_to_text(body_html) if body_html else ""

        if not raw_content or len(raw_content.split()) < 20:
            return

        published_at = self._extract_date(response)

        yield self.make_document(
            response=response,
            title=title,
            raw_content=raw_content,
            subcategory="news",
            published_at=published_at,
            metadata={"word_count": len(raw_content.split())},
        )

        yield from self._follow_content_links(response)

    def _extract_title(self, response) -> str:
        candidates = [
            response.css("h1::text").get(""),
            response.css(".document-title::text").get(""),
            response.css(".loi-title::text").get(""),
            response.css(".article-title::text").get(""),
            response.css(".entry-title::text").get(""),
            response.css("h2.title::text").get(""),
        ]
        for c in candidates:
            if c.strip():
                return c.strip()
        return ""

    def _extract_date(self, response) -> str | None:
        candidates = [
            response.css("time::attr(datetime)").get(""),
            response.css(".date::text").get(""),
            response.css(".post-date::text").get(""),
            response.css("meta[property='article:published_time']::attr(content)").get(""),
        ]
        for c in candidates:
            if c.strip():
                return c.strip()[:10]
        return None

    def _infer_subcategory(self, url: str) -> str:
        path = url.lower()
        for kw in self.content_path_keywords:
            if kw in path:
                return kw
        return "document"

    def _is_legal_document_url(self, url: str) -> bool:
        if "assemblee-nationale.tg" not in url:
            return False
        path = url.split("assemblee-nationale.tg")[-1].lower()
        legal_keywords = ["loi", "decret", "ordonnance", "resolution", "texte"]
        return any(kw in path for kw in legal_keywords)

    def _is_article_url(self, url: str) -> bool:
        if "assemblee-nationale.tg" not in url:
            return False
        path = url.split("assemblee-nationale.tg")[-1].lower()
        if any(path.startswith(p) for p in self.denied_paths):
            return False
        has_keyword = any(kw in path for kw in self.content_path_keywords)
        has_slug = len(path.strip("/").split("/")) >= 2
        return has_keyword and has_slug

    def _should_follow(self, url: str) -> bool:
        if "assemblee-nationale.tg" not in url:
            return False
        path = url.split("assemblee-nationale.tg")[-1].lower()
        return not any(path.startswith(p) for p in self.denied_paths)
