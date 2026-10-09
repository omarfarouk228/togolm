from scrapy import signals


class TogoLMSpiderMiddleware:
    @classmethod
    def from_crawler(cls, crawler):
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_output(self, response, result, spider):
        yield from result

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s", spider.name)


class TogoLMDownloaderMiddleware:
    @classmethod
    def from_crawler(cls, crawler):
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
        return None

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s", spider.name)


def normalize_url(url: str) -> str:
    """Scheme-, www- and trailing-slash-insensitive form of a URL."""
    u = url.strip().split("#", 1)[0]
    u = u.split("://", 1)[-1]
    if u.startswith("www."):
        u = u[4:]
    return u.rstrip("/")


class SkipKnownUrlsMiddleware:
    """Skip downloading pages already stored as documents (incremental crawl).

    News spiders re-crawled every article of their site daily and ran into the
    50-minute subprocess limit before reaching new ones (icilome alone has
    22k articles). With SKIP_KNOWN_URLS enabled (corpus.tasks sets it for news
    spiders), article URLs already in the documents table are never fetched
    again; listing and sitemap pages still are, so new articles are found.
    Published news articles rarely change, and the weekly full crawl of other
    sources is unaffected.
    """

    def __init__(self, enabled: bool):
        self.enabled = enabled
        self.known: set[str] = set()
        self.skipped = 0

    @classmethod
    def from_crawler(cls, crawler):
        mw = cls(crawler.settings.getbool("SKIP_KNOWN_URLS"))
        crawler.signals.connect(mw.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(mw.spider_closed, signal=signals.spider_closed)
        return mw

    def spider_opened(self, spider):
        source = getattr(spider, "source", "")
        if not self.enabled or not source:
            return
        try:
            self.known = self._load_known_urls(source)
        except Exception as e:  # DB unreachable: crawl everything, as before
            spider.logger.warning("SkipKnownUrls disabled, could not load URLs: %s", e)
            self.known = set()
        spider.logger.info("SkipKnownUrls: %d known URLs for %s", len(self.known), source)

    def spider_closed(self, spider):
        if self.enabled:
            spider.logger.info("SkipKnownUrls: skipped %d known pages", self.skipped)

    @staticmethod
    def _load_known_urls(source: str) -> set[str]:
        import os

        import psycopg2

        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            dbname=os.getenv("POSTGRES_DB", "togolm"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD") or None,
            connect_timeout=10,
        )
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT url FROM documents WHERE source = %s AND url IS NOT NULL", (source,)
                )
                return {normalize_url(r[0]) for r in cur.fetchall()}
        finally:
            conn.close()

    def process_request(self, request, spider=None):
        if not self.known or request.url.endswith(".xml"):
            return None
        if normalize_url(request.url) in self.known:
            from scrapy.exceptions import IgnoreRequest

            self.skipped += 1
            raise IgnoreRequest("already ingested")
        return None
