# Contributing to TogoLM

Thank you for helping build the first open-source AI infrastructure for Togo.

---

## Types of contributions

| Area | Examples |
|------|----------|
| **New sources** | Report Togolese websites not yet in the corpus |
| **Scrapers** | Write Scrapy spiders for new sources |
| **Corpus fixes** | Flag incorrect, duplicate, or low-quality documents |
| **API** | New endpoints, performance improvements, bug fixes |
| **Showcase** | UI components, new pages, accessibility improvements |
| **Fine-tuning** | New Q&A instruction pairs for the training dataset |
| **Documentation** | Guides, examples, translations |

---

## Setup (local development)

```bash
# 1. Fork and clone
git clone https://github.com/<your-username>/togolm.git
cd togolm

# 2. Create a branch
git checkout -b feat/my-spider

# 3. Install Python dependencies (uv required)
uv sync

# 4. Copy and configure environment
cp .env.example .env
# Set POSTGRES_USER, POSTGRES_DB, POSTGRES_HOST

# 5. Initialize the database
psql -U $POSTGRES_USER -d $POSTGRES_DB -f scripts/init.sql

# 6. Run tests
uv run pytest api/tests/ -v
```

---

## Workflow

1. Open an **Issue** first to discuss the change (especially for new corpus sources)
2. Create a branch: `git checkout -b feat/source-name` or `fix/bug-description`
3. Make your changes following the code standards below
4. Run tests: `uv run pytest api/tests/`
5. Open a **Pull Request** with a clear description of what and why

---

## Writing a spider

All spiders live in `corpus/scrapers/spiders/`. Use `base_spider.py` as a foundation.

### Minimal template

```python
"""Spider for example-site.tg — brief description of the source."""

import re
from urllib.parse import urljoin
import scrapy
from scrapers.spiders.base_spider import BaseTogoSpider

ARTICLE_URL_RE = re.compile(r"/\d{4}/\d{2}/.+/$")  # adapt to the site

ENTRY_URLS = [
    "https://example-site.tg/category/news/",
    "https://example-site.tg/",
]


class ExampleSpider(BaseTogoSpider):
    name = "example"           # unique spider name (used in scrapy crawl <name>)
    source = "example-site.tg" # displayed in the corpus UI
    category = "press"         # one of: legal, administrative, education,
                               #         economy, agriculture, health, politics, press
    language = "fr"

    start_urls = ENTRY_URLS

    def parse(self, response):
        # Follow article links
        for href in response.css("a::attr(href)").getall():
            url = urljoin(response.url, href)
            if self._is_article(url):
                yield scrapy.Request(url, callback=self.parse_article, priority=10)
        # Follow pagination
        next_pg = response.css("a[rel='next']::attr(href)").get()
        if next_pg:
            yield scrapy.Request(urljoin(response.url, next_pg), callback=self.parse)

    def parse_article(self, response):
        title = response.css("h1::text").get("").strip()
        if not title:
            return

        body_html = response.css(".entry-content, article").get("")
        raw_content = self.html_to_text(body_html)

        if len(raw_content.split()) < 30:
            return  # skip stub pages

        published_at = response.css("time::attr(datetime)").get("")

        yield self.make_document(
            response=response,
            title=title,
            raw_content=raw_content,
            subcategory="news",
            published_at=published_at[:10] if published_at else None,
            metadata={"word_count": len(raw_content.split())},
        )

    def _is_article(self, url: str) -> bool:
        if "example-site.tg" not in url:
            return False
        path = url.split("example-site.tg")[-1]
        return bool(ARTICLE_URL_RE.search(path))
```

### Running your spider

```bash
# From the project root
uv run scrapy crawl example \
  -o corpus/datasets/example.jsonl \
  --logfile corpus/.crawls/example.log

# Check the output
wc -l corpus/datasets/example.jsonl
head -n 2 corpus/datasets/example.jsonl | python3 -m json.tool
```

### Ingest the result

```bash
uv run python -m corpus.processors.ingestor corpus/datasets/example.jsonl
```

---

## Adding a corpus source (without writing the spider yourself)

1. Open an Issue with the label `corpus`
2. Include: URL, content type (laws / press / admin / ...), language, estimated article count, update frequency
3. Maintainer validates and schedules the spider

---

## Code standards

- **Language**: all code, comments, variable names, and docstrings must be in **English**
- **Python**: 3.11+ with type hints
- **Formatting**: `uv run ruff format .`
- **Linting**: `uv run ruff check .`
- **Tests**: `uv run pytest api/tests/` — add tests for new API routes

---

## Issue labels

| Label | Meaning |
|-------|---------|
| `corpus` | New data source or corpus correction |
| `api` | API endpoint or backend logic |
| `finetuning` | Training scripts or instruction datasets |
| `showcase` | Next.js frontend |
| `bug` | Something is broken |
| `enhancement` | Improvement to an existing feature |
| `good first issue` | Good for first-time contributors |

---

## Code of conduct

This project follows the [Contributor Covenant](https://www.contributor-covenant.org/).
Be respectful, constructive, and welcoming to contributors from all backgrounds.

---

**Contact:** komarf28@gmail.com · [GitHub Issues](https://github.com/togolm/togolm/issues)
