"""
Spider for service-public.gouv.tg — Togolese administrative procedures portal.

The site renders category listings via JavaScript, but individual service pages
and the /service-online listing page are server-rendered.

Strategy:
  1. Start from /service-online and /professional (complete service listings)
  2. Parse each /service/... URL into a document
  3. Optionally follow /howto/... FAQ pages
"""

from urllib.parse import urljoin

import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

# Seed pages that contain static service listings
START_LISTING_PAGES = [
    "https://service-public.gouv.tg/service-online",
    "https://service-public.gouv.tg/professional",
]


class ServicePublicSpider(BaseTogoSpider):
    name = "service_public"
    source = "service-public.gouv.tg"
    category = "administrative"
    language = "fr"

    start_urls = START_LISTING_PAGES

    denied_path_prefixes = [
        "/login", "/logout", "/admin", "/search", "/api",
        "/static", "/media", "/user/auth", "/sharefiles",
        "/cdn-cgi",
    ]

    def parse(self, response):
        """Parse a listing page: follow all /service/ and /howto/ links."""
        for href in response.css("a::attr(href)").getall():
            url = urljoin(response.url, href)
            if not self._is_valid(url):
                continue
            path = url.split("service-public.gouv.tg")[-1]
            if path.startswith("/service/"):
                yield scrapy.Request(url, callback=self.parse_procedure, priority=10)
            elif path.startswith("/howto/"):
                yield scrapy.Request(url, callback=self.parse_howto)

    def parse_procedure(self, response):
        """Parse an individual administrative procedure/service page."""
        # Title: large bold div or h1
        title = (
            response.css("div.fs-2.fw-bold::text").get("").strip()
            or response.css("h1::text").get("").strip()
        )
        if not title:
            return

        content_parts = []

        # Structured content sections (server-rendered)
        section_selectors = [
            (".wp-description", "Description"),
            (".wp-who", "Personnes concernées"),
            (".wp-conditions", "Conditions"),
            (".wp-pieces", "Pièces à fournir"),
            (".wp-steps", "Étapes"),
        ]
        for selector, label in section_selectors:
            html = response.css(selector).get("")
            if html:
                text = self.html_to_text(html)
                if text:
                    content_parts.append(f"{label}: {text}")

        # Service features (delay, cost, validity)
        for feature in response.css(".service-features .bg-light-blue"):
            feature_title = feature.css("h4::text").get("").strip()
            feature_text = feature.css("span::text").get("").strip()
            if feature_title and feature_text:
                content_parts.append(f"{feature_title}: {feature_text}")

        # Service provider / contact info
        contact_html = response.css("#contactWidget").get("")
        if contact_html:
            contact_text = self.html_to_text(contact_html)
            if contact_text:
                content_parts.append(f"Contact: {contact_text}")

        # Fallback: grab all main content
        if not content_parts:
            main_html = response.css("main, .service-raw, .container").get("")
            if main_html:
                content_parts.append(self.html_to_text(main_html))

        raw_content = " | ".join(p for p in content_parts if p.strip())
        if not raw_content.strip() or len(raw_content.split()) < 20:
            return

        # Subcategory from breadcrumb
        subcategory = self._extract_subcategory(response)

        yield self.make_document(
            response=response,
            title=title,
            raw_content=raw_content,
            subcategory=subcategory,
            metadata={"word_count": len(raw_content.split())},
        )

    def parse_howto(self, response):
        """Parse a FAQ/how-to page."""
        title = (
            response.css("h1::text").get("").strip()
            or response.css("div.fs-2.fw-bold::text").get("").strip()
        )
        if not title:
            return

        main_html = response.css("main, .howto-content, .container").get("")
        raw_content = self.html_to_text(main_html) if main_html else ""

        if not raw_content or len(raw_content.split()) < 20:
            return

        yield self.make_document(
            response=response,
            title=title,
            raw_content=raw_content,
            subcategory="faq",
            metadata={"word_count": len(raw_content.split())},
        )

    def _extract_subcategory(self, response) -> str:
        """Extract subcategory from breadcrumb trail."""
        breadcrumbs = response.css(
            ".d-none.d-md-flex a::text, "
            "nav[aria-label='breadcrumb'] a::text"
        ).getall()
        # Second-to-last breadcrumb is the category
        if len(breadcrumbs) >= 2:
            return breadcrumbs[-2].strip()
        # Fallback: extract from URL path
        # e.g. /service/<id>/papiers-citoyennete/slug → "papiers-citoyennete"
        path = response.url.split("service-public.gouv.tg")[-1]
        parts = path.strip("/").split("/")
        if len(parts) >= 3:
            return parts[-2].replace("-", " ").title()
        return ""

    def _is_valid(self, url: str) -> bool:
        """Return True if this URL belongs to the site and isn't blocked."""
        if "service-public.gouv.tg" not in url:
            return False
        path = url.split("service-public.gouv.tg")[-1].lower()
        return not any(path.startswith(p) for p in self.denied_path_prefixes)
