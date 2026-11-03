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


# Inline images (data URIs) and other long base64 blobs copied from a page's
# HTML. One edusup.gouv.tg article carried a 1.95 M-character base64 image in
# its text: the chunk exceeded the embedding API's tokens-per-minute quota on
# its own and blocked the whole embedding backlog for weeks (2026-11-03).
_DATA_URI_RE = re.compile(r"data:[\w.+-]+/[\w.+-]+(?:;[\w=.+-]+)*;base64,[A-Za-z0-9+/=\s]*")
_BASE64_BLOB_RE = re.compile(r"[A-Za-z0-9+/]{200,}={0,2}")


def remove_binary_blobs(text: str) -> str:
    text = _DATA_URI_RE.sub(" ", text)
    return _BASE64_BLOB_RE.sub(" ", text)


def clean_document(raw_content: str) -> str:
    """Full cleaning pipeline for a scraped document."""
    text = raw_content
    text = remove_control_characters(text)
    text = remove_binary_blobs(text)
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
