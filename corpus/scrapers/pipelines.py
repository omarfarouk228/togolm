import json
import re
from pathlib import Path

from itemadapter import ItemAdapter


class CleanTextPipeline:
    def process_item(self, item):
        adapter = ItemAdapter(item)
        raw = adapter.get("raw_content", "")
        adapter["raw_content"] = re.sub(r"\s+", " ", raw).strip()
        return item


class JsonWriterPipeline:
    """
    Write each item as a JSON line to a per-spider output file.

    File is opened in WRITE mode (truncate) each run so the JSONL stays
    lean — ingestor uses ON CONFLICT DO UPDATE anyway, so re-runs are safe.
    Within-run URL deduplication is applied to avoid processing the same
    article twice when multiple entry points lead to the same URL.
    """

    @classmethod
    def from_crawler(cls, crawler):
        instance = cls()
        instance.spider_name = crawler.spider.name if crawler.spider else "output"
        return instance

    def open_spider(self, *_args, **_kwargs):
        output_dir = Path(__file__).parent.parent / "datasets"
        output_dir.mkdir(exist_ok=True)
        # Truncate on each run — keeps JSONL compact; duplicates from previous
        # runs are handled by the ingestor's ON CONFLICT DO UPDATE.
        self.file = open(output_dir / f"{self.spider_name}.jsonl", "w", encoding="utf-8")
        self._seen_urls: set[str] = set()

    def close_spider(self):
        self.file.close()

    def process_item(self, item):
        url = dict(item).get("url", "")
        if url and url in self._seen_urls:
            return item  # silently skip duplicates within this run
        if url:
            self._seen_urls.add(url)
        self.file.write(json.dumps(dict(item), ensure_ascii=False) + "\n")
        return item
