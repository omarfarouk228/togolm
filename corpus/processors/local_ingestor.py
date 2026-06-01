"""
Ingest local files (PDF, TXT) into the corpus JSONL format.

Usage:
    uv run python -m corpus.processors.local_ingestor "assemble nationnale/" \
        --source "assemblee-nationale.tg" \
        --category legal \
        --output corpus/datasets/assemblee_nationale_local.jsonl
"""

import argparse
import json
import re
from pathlib import Path

from pdfminer.high_level import extract_text as pdf_extract_text

from corpus.processors.cleaner import clean_document, is_useful

DOCUMENT_TYPE_RE = re.compile(
    r"\b(loi|ordonnance|décret|arrêté|convention|code|règlement|résolution)\b",
    re.IGNORECASE,
)

DATE_RE = re.compile(r"\b(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})\b")


def extract_pdf(path: Path) -> str:
    """Extract text from a PDF file."""
    try:
        return pdf_extract_text(str(path))
    except Exception as e:
        print(f"  [WARN] Could not extract {path.name}: {e}")
        return ""


def extract_txt(path: Path) -> str:
    """Read a plain text file."""
    return path.read_text(encoding="utf-8", errors="replace")


HEADER_PATTERNS = re.compile(
    r"^(assemblee nationale|republique togolaise|premiere legislature|"
    r"travail.{0,5}libert|secretariat general|direction des services|"
    r"division des s|section des s|ann[eé]e \d{4}|s[eé]ance pl|"
    r"[-~=_*#]{3,}|loi n\W*$)",
    re.IGNORECASE,
)


def infer_title(text: str, filename: str) -> str:
    """
    Extract the document title from AN legislative PDF header structure.
    Skips institutional boilerplate, collects the ALL-CAPS title block,
    stops at the first article body line.
    """
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    # Find where the boilerplate ends (first line NOT matching header patterns)
    start = 0
    for i, line in enumerate(lines[:50]):
        if not HEADER_PATTERNS.match(line):
            start = i
            break

    def _is_garbage(line: str) -> bool:
        """Detect OCR artifacts and non-title lines."""
        if HEADER_PATTERNS.match(line):
            return True
        # Lines with consecutive special chars (OCR artifacts like ~~~, ===)
        if re.search(r"[~!|*=#]{2,}", line):
            return True
        # Lines where less than 55% of non-space characters are letters
        non_space = [c for c in line if not c.isspace()]
        if non_space:
            letter_ratio = sum(c.isalpha() for c in non_space) / len(non_space)
            if letter_ratio < 0.55:
                return True
        return False

    def _clean_line(line: str) -> str:
        """Strip leading tokens that are OCR artifacts (no real 2+ letter word)."""
        tokens = line.split()
        while tokens and not re.search(r"[A-Za-zÀ-ÿ]{3,}", tokens[0]):
            tokens.pop(0)
        return " ".join(tokens).strip()

    title_parts = []
    for line in lines[start:start + 25]:
        if re.match(r"^article\s+(premier|1|ier)\b", line, re.IGNORECASE):
            break
        if _is_garbage(line):
            continue
        cleaned = _clean_line(line)
        if len(cleaned) < 4:
            continue
        title_parts.append(cleaned)
        if len(" ".join(title_parts).split()) >= 6:
            break

    title = " ".join(title_parts).strip()

    if not title or len(title) < 8:
        stem = Path(filename).stem
        title = re.sub(r"[-_]", " ", stem).title()

    # Clean up OCR artifacts
    title = re.sub(r"\s+", " ", title).strip()
    return title


def infer_subcategory(text: str, filename: str) -> str:
    combined = f"{filename} {text[:500]}".lower()
    match = DOCUMENT_TYPE_RE.search(combined)
    return match.group(1).lower() if match else "document"


def infer_date(text: str) -> str | None:
    match = DATE_RE.search(text[:2000])
    if match:
        d, m, y = match.group(1), match.group(2), match.group(3)
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
    return None


def process_file(path: Path, source: str, category: str) -> dict | None:
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        raw_text = extract_pdf(path)
    elif suffix in (".txt", ".md"):
        raw_text = extract_txt(path)
    else:
        return None

    clean_text = clean_document(raw_text)

    if not is_useful(clean_text, min_words=30):
        print(f"  [SKIP] {path.name} — too short after cleaning")
        return None

    title = infer_title(raw_text, path.name)
    subcategory = infer_subcategory(raw_text, path.name)
    published_at = infer_date(raw_text)

    return {
        "source": source,
        "url": None,
        "title": title,
        "raw_content": clean_text,
        "category": category,
        "subcategory": subcategory,
        "language": "fr",
        "published_at": published_at,
        "metadata": {
            "filename": path.name,
            "file_type": suffix.lstrip("."),
            "word_count": len(clean_text.split()),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Ingest local PDF/TXT files into corpus JSONL")
    parser.add_argument("input", type=Path, help="File or directory to ingest")
    parser.add_argument("--source", default="local", help="Source identifier")
    parser.add_argument("--category", default="legal", help="Corpus category")
    parser.add_argument("--output", type=Path, required=True, help="Output JSONL path")
    args = parser.parse_args()

    target = args.input
    files: list[Path] = []

    if target.is_dir():
        files = [f for f in target.rglob("*") if f.suffix.lower() in (".pdf", ".txt", ".md")]
    elif target.is_file():
        files = [target]
    else:
        print(f"Error: {target} not found")
        return

    print(f"Found {len(files)} file(s) in {target}\n")

    results = []
    for f in sorted(files):
        print(f"Processing {f.name}...")
        doc = process_file(f, source=args.source, category=args.category)
        if doc:
            results.append(doc)
            print(f"  OK — '{doc['title'][:60]}' ({doc['metadata']['word_count']} words)")
        print()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as out:
        for doc in results:
            out.write(json.dumps(doc, ensure_ascii=False) + "\n")

    print(f"\nDone: {len(results)}/{len(files)} files ingested → {args.output}")


if __name__ == "__main__":
    main()
