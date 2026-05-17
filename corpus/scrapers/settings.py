BOT_NAME = "togolm"
SPIDER_MODULES = ["scrapers.spiders"]

# Respectful scraping defaults
ROBOTSTXT_OBEY = True
CONCURRENT_REQUESTS = 4
DOWNLOAD_DELAY = 1.5
RANDOMIZE_DOWNLOAD_DELAY = True
CONCURRENT_REQUESTS_PER_DOMAIN = 2

# Retry on failures
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

USER_AGENT = "TogoLM-Bot/0.1 (+https://github.com/togolm/togolm)"

ITEM_PIPELINES = {
    "scrapers.pipelines.CleanTextPipeline": 100,
    "scrapers.pipelines.JsonWriterPipeline": 200,
}

# Output format
FEEDS = {}  # Configured per-run via -o flag

REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"

LOG_LEVEL = "INFO"
