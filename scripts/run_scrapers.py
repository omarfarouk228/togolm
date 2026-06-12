"""
Master scraping script for TogoLM.

Runs all (or selected) Scrapy spiders sequentially, then ingests the
collected JSONL files into PostgreSQL + pgvector.

Usage:
    # Run all spiders then ingest
    python scripts/run_scrapers.py

    # Run specific spiders only
    python scripts/run_scrapers.py --spiders service_public togofirst

    # Scrape only (no DB ingestion)
    python scripts/run_scrapers.py --no-ingest

    # Ingest existing JSONL files only (no scraping)
    python scripts/run_scrapers.py --no-scrape

    # Skip embedding generation (faster, useful without Gemini key)
    python scripts/run_scrapers.py --no-embed
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent.parent
SCRAPY_DIR = ROOT / "corpus"
DATASETS_DIR = ROOT / "corpus" / "datasets"

# Use the project venv Python if available (needed when system Python lacks scrapy)
_venv_python = ROOT / ".venv" / "Scripts" / "python.exe"  # Windows
if not _venv_python.exists():
    _venv_python = ROOT / ".venv" / "bin" / "python"  # Linux/macOS
PYTHON = str(_venv_python) if _venv_python.exists() else sys.executable

# All available spiders — ordered from most critical to supplementary
ALL_SPIDERS = [
    # Institutionnel & gouvernemental
    "service_public",
    "presidence",
    "inseed",
    "gouv_ministry",
    # Juridique
    "journal_officiel",
    "otr",
    "legal_pdf",          # PDF extraction from legitogo.gouv.tg and otr.tg
    # International organisations (World Bank, IMF, AfDB, UNDP…)
    "international",
    # Beta sources (ul.tg, api.tg, ceet.tg, cour-constitutionnelle.tg, inam.tg)
    "beta_sources",
    # Presse
    "togofirst",
    "icilome",
    "republicoftogo",
    "letogolais",
    "savoirnews",
    # Encyclopédique
    "wikipedia",
    # Presse supplémentaire
    "lomeinfos",
    "togoactualite",
]

# Spiders that are permanently or temporarily broken (skip by default)
# assemblee_nationale → Cloudflare bot protection / incompatible site structure
# mef               → DNS resolution failure (mef.gouv.tg unreachable via Python)
# atp               → DNS resolution failure (site unreachable)
# haac              → DNS resolution failure (site unreachable)
# togoinfos         → DNS resolution failure (site unreachable)
# togopress         → DNS resolution failure (site unreachable)
BROKEN_SPIDERS = ["assemblee_nationale", "mef", "atp", "haac", "togoinfos", "togopress"]


def run_spider(spider_name: str) -> bool:
    """Run a single Scrapy spider. Returns True on success."""
    print(f"\n{'=' * 60}")
    print(f"  Spider : {spider_name}")
    print(f"{'=' * 60}")

    output_file = DATASETS_DIR / f"{spider_name}.jsonl"
    # Use append mode so re-runs accumulate without overwriting
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

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(SCRAPY_DIR),
            timeout=600,  # 10 min max per spider
        )
        elapsed = time.time() - start
        size = output_file.stat().st_size / 1024 if output_file.exists() else 0
        if result.returncode == 0:
            print(f"  ✅ Done in {elapsed:.0f}s — output: {size:.1f} KB")
            return True
        else:
            print(f"  ❌ Exit code {result.returncode} after {elapsed:.0f}s")
            return False
    except subprocess.TimeoutExpired:
        print("  ⏱  Timeout (10 min) — spider may still have partial results")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def run_ingestor(no_embed: bool) -> bool:
    """Run the ingestor on all JSONL files in corpus/datasets/."""
    jsonl_files = sorted(DATASETS_DIR.glob("*.jsonl"))
    if not jsonl_files:
        print("\n[INGESTOR] No JSONL files found in corpus/datasets/ — skipping.")
        return False

    print(f"\n{'=' * 60}")
    print(f"  Ingestor — {len(jsonl_files)} file(s)")
    print(f"{'=' * 60}")

    cmd = [PYTHON, "-m", "corpus.processors.ingestor"] + [str(f) for f in jsonl_files]
    if no_embed:
        cmd.append("--no-embed")

    result = subprocess.run(cmd, cwd=str(ROOT))
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="TogoLM master scraping pipeline")
    parser.add_argument(
        "--spiders",
        nargs="+",
        metavar="SPIDER",
        help="Spiders to run (default: all)",
    )
    parser.add_argument("--no-scrape", action="store_true", help="Skip scraping, ingest only")
    parser.add_argument("--no-ingest", action="store_true", help="Scrape only, skip ingestion")
    parser.add_argument("--no-embed", action="store_true", help="Skip embedding generation")
    args = parser.parse_args()

    spiders = args.spiders or ALL_SPIDERS

    # ── Scraping ──────────────────────────────────────────────
    if not args.no_scrape:
        print(f"\nTogoLM Scraper — {len(spiders)} spider(s) to run")
        ok = failed = 0
        for spider in spiders:
            if spider not in ALL_SPIDERS:
                print(f"  ⚠️  Unknown spider: {spider} — skipping")
                continue
            success = run_spider(spider)
            if success:
                ok += 1
            else:
                failed += 1

        print(f"\nScraping done: {ok} OK, {failed} failed")

    # ── Ingestion ─────────────────────────────────────────────
    if not args.no_ingest:
        run_ingestor(no_embed=args.no_embed)

    print("\n✅ Pipeline complete.")


if __name__ == "__main__":
    main()
