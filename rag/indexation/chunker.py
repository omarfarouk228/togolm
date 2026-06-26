"""
Split cleaned documents into overlapping chunks for embedding.
"""

from dataclasses import dataclass


@dataclass
class Chunk:
    document_id: str
    chunk_index: int
    text: str
    word_count: int


def chunk_by_words(
    text: str,
    document_id: str,
    chunk_size: int = 400,
    overlap: int = 50,
) -> list[Chunk]:
    """
    Split text into word-based chunks with overlap.
    chunk_size and overlap are in words, not tokens.
    At ~1.3 tokens/word, 400 words ≈ 512 tokens.
    """
    words = text.split()
    if not words:
        return []

    chunks: list[Chunk] = []
    start = 0
    index = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]
        chunk_text = " ".join(chunk_words)

        chunks.append(
            Chunk(
                document_id=document_id,
                chunk_index=index,
                text=chunk_text,
                word_count=len(chunk_words),
            )
        )

        if end == len(words):
            break

        start = end - overlap
        index += 1

    return chunks


