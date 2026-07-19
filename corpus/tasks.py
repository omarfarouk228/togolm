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
    "primature",  # presidenceduconseil.gouv.tg — full crawl, plus complet que sitemap
    "inseed",
    "gouv_ministry",
    "journal_officiel",
    "otr",
    "legal_pdf",
    "droit_afrique",  # droit-afrique.com — textes juridiques Togo
    "international",
    "beta_sources",
    "togofirst",
    "icilome",
    "republicoftogo",
    "republiquetogolaise",
    "letogolais",
    "savoirnews",
    "wikipedia",
    "lomeinfos",
    "togoactualite",
    # Nouvelles sources — actualités & institutions
    "togo24",
    "anpe",
    "yas",
    "moov_africa",
    "edusup",
    # Éducation supérieure
    "univ_lome",
    "campus_togo",
    # Organisations régionales (BCEAO, OHADA, UEMOA)
    "bceao",
    "ohada",
    "uemoa",
]

NEWS_SPIDERS = [
    "togofirst",
    "icilome",
    "republicoftogo",
    "republiquetogolaise",
    "letogolais",
    "savoirnews",
    "lomeinfos",
    "togoactualite",
    "presidence",
]


# Spider subprocess budget. The corpus has grown enough (68k+ docs) that most
# spiders now run past the old 1790s ceiling and get killed mid-crawl every
# time — raised so a full crawl actually has room to finish. Revisit if the
# corpus keeps growing and this stops being enough.
SPIDER_TIMEOUT_S = 2990


@app.task(bind=True, max_retries=0, soft_time_limit=3000, time_limit=3060)
def run_spider(self, spider_name: str) -> dict:
    """
    Run a single Scrapy spider. Returns {spider, success, output_kb}.
    Soft limit = 50 min, hard limit = 51 min.
    """
    output_file = DATASETS_DIR / f"{spider_name}.jsonl"
    DATASETS_DIR.mkdir(exist_ok=True)

    cmd = [
        PYTHON,
        "-m",
        "scrapy",
        "crawl",
        spider_name,
        "--logfile",
        str(DATASETS_DIR / f"{spider_name}.log"),
        "-L",
        "WARNING",
    ]

    result = subprocess.run(cmd, cwd=str(SCRAPY_DIR), timeout=SPIDER_TIMEOUT_S)
    size_kb = output_file.stat().st_size / 1024 if output_file.exists() else 0

    return {
        "spider": spider_name,
        "success": result.returncode == 0,
        "output_kb": round(size_kb, 1),
    }


@app.task(bind=True, max_retries=0, time_limit=86400)
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


@app.task(bind=True, max_retries=0, time_limit=21600)
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


# Per-file ingest budget. Previously all ~26 dataset files were ingested in a
# single subprocess call with one global timeout — on a corpus this size that
# call reliably ran past the limit and got killed mid-file, silently leaving
# every document after the cutoff (and any partially-embedded one) without an
# embedding. Ingesting one file per subprocess means a slow/stuck source
# (e.g. icilome.jsonl, ~22k docs) can time out without blocking the other 25,
# and each run makes real incremental progress instead of restarting from
# scratch. Combined with the unchanged-content skip in the ingestor, repeat
# runs only pay for what actually changed.
INGEST_FILE_TIMEOUT_S = 1800


@app.task(bind=True, max_retries=0, soft_time_limit=21000, time_limit=21600)
def ingest_datasets(self, embed: bool = True) -> dict:
    """
    Ingest all JSONL files in corpus/datasets/ into PostgreSQL, one subprocess
    per file so a single slow file can't block the rest of the batch.
    """
    jsonl_files = sorted(DATASETS_DIR.glob("*.jsonl"))
    non_empty = [f for f in jsonl_files if f.stat().st_size > 0]

    if not non_empty:
        return {"success": False, "reason": "no JSONL files found"}

    results = []
    for f in non_empty:
        cmd = [PYTHON, "-m", "rag.indexation.ingestor", str(f)]
        if not embed:
            cmd.append("--no-embed")
        try:
            result = subprocess.run(cmd, cwd=str(ROOT), timeout=INGEST_FILE_TIMEOUT_S)
            results.append({"file": f.name, "success": result.returncode == 0, "timed_out": False})
        except subprocess.TimeoutExpired:
            results.append({"file": f.name, "success": False, "timed_out": True})

    return {
        "success": all(r["success"] for r in results),
        "files_processed": len(non_empty),
        "results": results,
    }
