from datetime import datetime

import scrapy
from bs4 import BeautifulSoup
from scrapers.items import DocumentItem


class BaseTogoSpider(scrapy.Spider):
    """
    Base spider for all TogoLM scrapers.

    Subclasses must define:
      - name: spider identifier
      - source: human-readable source name
      - start_urls: seed URLs
      - category: corpus category (legal, education, economy, health, politics, press)

    Subclasses should override parse() and implement extract_document().
    """

    source: str = ""
    category: str = ""
    language: str = "fr"

    custom_settings = {
        "DOWNLOAD_DELAY": 1.5,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
    }

    def make_document(
        self,
        response,
        title: str,
        raw_content: str,
        subcategory: str = "",
        published_at: str | None = None,
        metadata: dict | None = None,
    ) -> DocumentItem:
        return DocumentItem(
            source=self.source,
            url=response.url,
            title=title.strip(),
            raw_content=raw_content,
            category=self.category,
            subcategory=subcategory,
            language=self.language,
            published_at=published_at,
            metadata={
                "scraped_at": datetime.utcnow().isoformat(),
                **(metadata or {}),
            },
        )

    @staticmethod
    def html_to_text(html: str) -> str:
        """Convert HTML fragment to clean plain text."""
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)
