# Contributing to TogoLM

Thank you for helping build the first open-source AI infrastructure for Togo.

## Types of contributions

- **New sources** — report Togolese websites not yet covered
- **Scrapers** — write spiders for new sources
- **Corpus corrections** — flag incorrect or low-quality data
- **API** — improve endpoints, add features
- **Documentation** — improve guides, add examples
- **Fine-tuning** — propose instruction/response pairs for the training dataset

## Workflow

1. **Fork** the repository
2. Create a branch: `git checkout -b feat/my-scraper`
3. Make your changes
4. **Test**: `pytest api/tests/`
5. Open a **Pull Request** with a clear description

## Issue labels

| Label | Meaning |
|-------|---------|
| `corpus` | Data addition or correction |
| `api` | Endpoint or API logic |
| `finetuning` | Training scripts or datasets |
| `vitrine` | Next.js showcase interface |
| `bug` | Something is broken |
| `enhancement` | Improvement to an existing feature |

## Adding a corpus source

1. Open an Issue with the `corpus` label
2. Include: URL, content type, language, update frequency
3. The maintainer validates the source before scraping
4. Write your spider in `corpus/scrapers/spiders/`
5. Follow the `service_public_spider.py` template

## Code standards

- Python 3.11+ with type hints
- Formatting: `ruff format`
- Linting: `ruff check`
- Tests required for all new scrapers

## Code of conduct

This project follows the [Contributor Covenant](https://www.contributor-covenant.org/).
Be respectful, constructive, and welcoming.

---

**Contact:** omar@kofcorporation.com | GitHub Issues
