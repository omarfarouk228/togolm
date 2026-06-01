"""
Celery tasks for TogoLM scraping pipeline.

Tasks:
  - run_spider(name)           : Run a single Scrapy spider
  - run_all_spiders(embed)     : Run all working spiders, then ingest
  - run_news_spiders(embed)    : Run only news/press spiders
  - ingest_datasets(embed)     : Ingest all JSONL files in corpus/datasets/
"""

import subprocess
import sys
from pathlib import Path

from corpus.celery_app import app

ROOT = Path(__file__).resolve().parent.parent
SCRAPY_DIR = ROOT / "corpus"
DATASETS_DIR = ROOT / "corpus" / "datasets"

# Use project venv Python if available
_venv_python = ROOT / ".venv" / "Scripts" / "python.exe"
if not _venv_python.exists():
    _venv_python = ROOT / ".venv" / "bin" / "python"
PYTHON = str(_venv_python) if _venv_python.exists() else sys.executable

# Working spiders (broken ones excluded)
WORKING_SPIDERS = [
    "service_public",
    "presidence",
    "inseed",
    "gouv_ministry",
    "journal_officiel",
    "otr",
    "togofirst",
    "icilome",
    "republicoftogo",
    "letogolais",
    "savoirnews",
    "wikipedia",
    "lomeinfos",
    "togoactualite",
]

NEWS_SPIDERS = [
    "togofirst",
    "icilome",
    "republicoftogo",
    "letogolais",
    "savoirnews",
    "lomeinfos",
    "togoactualite",
    "presidence",
]


@app.task(bind=True, max_retries=0, soft_time_limit=600, time_limit=660)
def run_spider(self, spider_name: str) -> dict:
    """
    Run a single Scrapy spider. Returns {spider, success, output_kb}.
    Soft limit = 10 min, hard limit = 11 min.
    """
    output_file = DATASETS_DIR / f"{spider_name}.jsonl"
    DATASETS_DIR.mkdir(exist_ok=True)

    cmd = [
        PYTHON, "-m", "scrapy", "crawl", spider_name,
        "--logfile", str(DATASETS_DIR / f"{spider_name}.log"),
        "-L", "WARNING",
    ]

    result = subprocess.run(cmd, cwd=str(SCRAPY_DIR), timeout=590)
    size_kb = output_file.stat().st_size / 1024 if output_file.exists() else 0

    return {
        "spider": spider_name,
        "success": result.returncode == 0,
        "output_kb": round(size_kb, 1),
    }


@app.task(bind=True, max_retries=0, time_limit=7200)
def run_all_spiders(self, embed: bool = True) -> dict:
    """
    Run all working spiders sequentially, then ingest into PostgreSQL.
    """
    results = []
    for spider in WORKING_SPIDERS:
        r = run_spider.apply(args=[spider])
        results.append(r.result)

    ingest_result = ingest_datasets.apply(args=[embed])
    return {
        "spiders": results,
        "ingest": ingest_result.result,
    }


@app.task(bind=True, max_retries=0, time_limit=3600)
def run_news_spiders(self, embed: bool = False) -> dict:
    """
    Run only news/press spiders, then ingest new JSONL entries.
    """
    results = []
    for spider in NEWS_SPIDERS:
        r = run_spider.apply(args=[spider])
        results.append(r.result)

    ingest_result = ingest_datasets.apply(args=[embed])
    return {
        "spiders": results,
        "ingest": ingest_result.result,
    }


@app.task(bind=True, max_retries=0, time_limit=3600)
def ingest_datasets(self, embed: bool = True) -> dict:
    """
    Ingest all JSONL files in corpus/datasets/ into PostgreSQL.
    """
    jsonl_files = sorted(DATASETS_DIR.glob("*.jsonl"))
    non_empty = [f for f in jsonl_files if f.stat().st_size > 0]

    if not non_empty:
        return {"success": False, "reason": "no JSONL files found"}

    cmd = [PYTHON, "-m", "corpus.processors.ingestor"] + [str(f) for f in non_empty]
    if not embed:
        cmd.append("--no-embed")

    result = subprocess.run(cmd, cwd=str(ROOT), timeout=3590)
    return {
        "success": result.returncode == 0,
        "files_processed": len(non_empty),
    }
