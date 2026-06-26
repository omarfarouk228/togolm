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


def chunk_by_paragraphs(
    text: str,
    document_id: str,
    max_words: int = 400,
) -> list[Chunk]:
    """
    Split on paragraph boundaries, then merge small paragraphs up to max_words.
    Prefer semantic boundaries over fixed-size windows.
    """
    paragraphs = [p.strip() for p in text.split("|") if p.strip()]

    chunks: list[Chunk] = []
    buffer: list[str] = []
    buffer_words = 0
    index = 0

    for para in paragraphs:
        para_words = len(para.split())
        if buffer_words + para_words > max_words and buffer:
            chunks.append(
                Chunk(
                    document_id=document_id,
                    chunk_index=index,
                    text=" ".join(buffer),
                    word_count=buffer_words,
                )
            )
            buffer = []
            buffer_words = 0
            index += 1

        buffer.append(para)
        buffer_words += para_words

    if buffer:
        chunks.append(
            Chunk(
                document_id=document_id,
                chunk_index=index,
                text=" ".join(buffer),
                word_count=buffer_words,
            )
        )

    return chunks
