"""
Text cleaning utilities for raw scraped content.
"""

import re
import unicodedata


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def remove_control_characters(text: str) -> str:
    return "".join(
        ch for ch in text if not unicodedata.category(ch).startswith("C") or ch in "\n\t"
    )


def clean_document(raw_content: str) -> str:
    """Full cleaning pipeline for a scraped document."""
    text = raw_content
    text = remove_control_characters(text)
    # Remove repeated punctuation artifacts
    text = re.sub(r"[|]{2,}", "|", text)
    text = re.sub(r"[-]{3,}", "—", text)
    text = re.sub(r"[.]{4,}", "...", text)
    # Remove URLs (keep surrounding text)
    text = re.sub(r"https?://\S+", "", text)
    text = normalize_whitespace(text)
    return text


def is_useful(text: str, min_words: int = 20) -> bool:
    """Filter out near-empty or boilerplate documents."""
    words = text.split()
    return len(words) >= min_words
