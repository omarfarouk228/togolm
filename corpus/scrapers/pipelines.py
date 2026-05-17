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
    """Append each item as a JSON line to a per-spider output file."""

    @classmethod
    def from_crawler(cls, crawler):
        instance = cls()
        instance.spider_name = crawler.spider.name if crawler.spider else "output"
        return instance

    def open_spider(self):
        output_dir = Path(__file__).parent.parent / "datasets"
        output_dir.mkdir(exist_ok=True)
        self.file = open(output_dir / f"{self.spider_name}.jsonl", "a", encoding="utf-8")

    def close_spider(self):
        self.file.close()

    def process_item(self, item):
        self.file.write(json.dumps(dict(item), ensure_ascii=False) + "\n")
        return item
