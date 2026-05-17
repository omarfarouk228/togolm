"""
Spider for service-public.gouv.tg — Togolese administrative procedures portal.

Crawls procedure pages and extracts:
  - title, description, required steps, required documents, contact info
  - category (from site navigation)
  - URL and metadata
"""

from urllib.parse import urljoin

import scrapy

from scrapers.items import DocumentItem
from scrapers.spiders.base_spider import BaseTogoSpider


class ServicePublicSpider(BaseTogoSpider):
    name = "service_public"
    source = "service-public.gouv.tg"
    category = "administrative"
    language = "fr"

    start_urls = ["https://www.service-public.gouv.tg/"]

    # Patterns to follow (procedure & category pages)
    allowed_path_prefixes = [
        "/actualite",
        "/demarche",
        "/service",
        "/categorie",
        "/fiche",
    ]

    # Patterns to skip (login, search, assets, etc.)
    denied_path_prefixes = [
        "/login",
        "/logout",
        "/admin",
        "/search",
        "/api",
        "/static",
        "/media",
    ]

    def parse(self, response):
        """Entry point: extract procedure links from homepage / category pages."""
        yield from self._extract_procedure_links(response)
        yield from self._follow_navigation_links(response)

    def _follow_navigation_links(self, response):
        """Follow category/nav links to reach more procedure pages."""
        nav_links = response.css(
            "nav a::attr(href), "
            ".menu a::attr(href), "
            ".categories a::attr(href), "
            ".sidebar a::attr(href)"
        ).getall()

        for href in nav_links:
            url = urljoin(response.url, href)
            if self._should_follow(url):
                yield scrapy.Request(url, callback=self.parse_category)

    def _extract_procedure_links(self, response):
        """Extract and follow individual procedure page links."""
        procedure_links = response.css(
            "a[href*='/demarche']::attr(href), "
            "a[href*='/fiche']::attr(href), "
            "a[href*='/service']::attr(href), "
            ".procedure-list a::attr(href), "
            ".card a::attr(href), "
            "article a::attr(href)"
        ).getall()

        for href in set(procedure_links):
            url = urljoin(response.url, href)
            if self._should_follow(url):
                yield scrapy.Request(url, callback=self.parse_procedure)

    def parse_category(self, response):
        """Parse a category/listing page — follow child links."""
        yield from self._extract_procedure_links(response)

        # Pagination
        next_page = response.css(
            "a.next::attr(href), "
            "a[rel='next']::attr(href), "
            ".pagination .next a::attr(href)"
        ).get()
        if next_page:
            yield scrapy.Request(
                urljoin(response.url, next_page),
                callback=self.parse_category,
            )

    def parse_procedure(self, response):
        """Parse an individual administrative procedure page."""
        title = self._extract_title(response)
        if not title:
            return

        content_parts = []

        # Main description / intro
        description = self._extract_text(
            response,
            selectors=[
                ".procedure-description",
                ".fiche-description",
                ".intro",
                "article .description",
                ".content-main p",
            ],
        )
        if description:
            content_parts.append(description)

        # Required documents
        documents_section = self._extract_section(response, "documents", "required documents")
        if documents_section:
            content_parts.append(f"Required documents: {documents_section}")

        # Steps / procedure
        steps_section = self._extract_section(response, "steps", "procedure", "etapes", "demarche")
        if steps_section:
            content_parts.append(f"Steps: {steps_section}")

        # Costs / delays
        cost = self._extract_text(
            response,
            selectors=[".cost", ".cout", ".frais", ".tarif"],
        )
        if cost:
            content_parts.append(f"Cost: {cost}")

        # Contact info
        contact = self._extract_text(
            response,
            selectors=[".contact", ".where-to-go", ".ou-sadresser"],
        )
        if contact:
            content_parts.append(f"Contact: {contact}")

        # Fallback: grab all main content text
        if not content_parts:
            main_html = response.css(
                "main, article, .content, .main-content, #content"
            ).get("")
            content_parts.append(self.html_to_text(main_html))

        raw_content = " | ".join(part for part in content_parts if part.strip())
        if not raw_content.strip():
            return

        subcategory = self._extract_subcategory(response)

        yield self.make_document(
            response=response,
            title=title,
            raw_content=raw_content,
            subcategory=subcategory,
            metadata={
                "word_count": len(raw_content.split()),
            },
        )

        # Follow related procedure links found on this page
        yield from self._extract_procedure_links(response)

    def _extract_title(self, response) -> str:
        candidates = [
            response.css("h1::text").get(""),
            response.css(".procedure-title::text").get(""),
            response.css(".fiche-title::text").get(""),
            response.css(".card-title::text").get(""),
            response.css("h2.title::text").get(""),
        ]
        generic = "service public de l'administration togolaise"
        for candidate in candidates:
            cleaned = candidate.strip()
            if cleaned and cleaned.lower() != generic:
                return cleaned

        # Fallback: derive title from the URL slug (skip raw IDs)
        parts = response.url.rstrip("/").split("/")
        for slug in reversed(parts):
            # Skip segments that look like hex IDs or alphanumeric IDs
            if slug and "-" in slug and not slug.replace("-", "").isalnum():
                continue
            if slug and len(slug) > 8 and "-" in slug:
                return slug.replace("-", " ").title()
        return ""

    def _extract_text(self, response, selectors: list[str]) -> str:
        for selector in selectors:
            element = response.css(selector)
            if element:
                html = element.get("")
                text = self.html_to_text(html)
                if text:
                    return text
        return ""

    def _extract_section(self, response, *keywords: str) -> str:
        for kw in keywords:
            selectors = [
                f".{kw}",
                f"#{kw}",
                f"[class*='{kw}']",
                f"[id*='{kw}']",
            ]
            text = self._extract_text(response, selectors)
            if text:
                return text

        # Try heading-based extraction: find heading containing keyword, grab sibling content
        for kw in keywords:
            for heading in response.css("h2, h3, h4"):
                if kw.lower() in heading.css("::text").get("").lower():
                    sibling_html = heading.xpath("following-sibling::*[1]").get("")
                    if sibling_html:
                        return self.html_to_text(sibling_html)
        return ""

    def _extract_subcategory(self, response) -> str:
        breadcrumbs = response.css(
            ".breadcrumb a::text, "
            ".breadcrumbs a::text, "
            "nav[aria-label='breadcrumb'] a::text"
        ).getall()
        # Take the second-to-last breadcrumb as subcategory (last is current page)
        if len(breadcrumbs) >= 2:
            return breadcrumbs[-2].strip()
        return ""

    def _should_follow(self, url: str) -> bool:
        if "service-public.gouv.tg" not in url:
            return False
        path = url.split("service-public.gouv.tg", 1)[-1].lower()
        if any(path.startswith(p) for p in self.denied_path_prefixes):
            return False
        return True
