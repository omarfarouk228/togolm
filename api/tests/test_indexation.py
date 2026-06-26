"""
Tests for chunk sizing.

The local embedding model truncates inputs past 128 tokens, so chunks must be
sized to fit. These tests lock that invariant so a future bump of CHUNK_SIZE
cannot silently reintroduce truncation.
"""

from pathlib import Path

import pytest

from rag.indexation.chunker import chunk_by_words
from rag.indexation.embedder import LOCAL_MAX_TOKENS, MODEL_NAME, max_chunk_words

# Representative French Togo sentences (token-hungry: legal/administrative vocab).
_FR_SAMPLES = [
    "Le Togo est une République présidée par le Chef de l'État, et l'Assemblée "
    "nationale vote les lois de finances chaque année budgétaire au profit des citoyens.",
    "Pour créer une société à responsabilité limitée au Togo, il faut s'immatriculer "
    "au registre du commerce et du crédit mobilier auprès du guichet unique compétent.",
    "L'Office togolais des recettes collecte les impôts directs et les taxes douanières "
    "pour le compte de l'État afin de financer les services publics et les infrastructures.",
]


def test_max_chunk_words_fits_token_budget():
    words = max_chunk_words()
    # At the worst measured French ratio (~2.0 tok/word) plus special tokens,
    # the chunk must still fit the model window with headroom.
    assert words >= 16
    assert words * 2.0 + 2 <= LOCAL_MAX_TOKENS


def test_chunk_size_is_not_the_old_oversized_default():
    # Regression guard: the old 400-word chunks were ~512 tokens, 4x the model limit.
    assert max_chunk_words() < 100


def test_chunker_respects_word_budget():
    text = "mot " * 500
    chunks = chunk_by_words(text, "doc-1", chunk_size=max_chunk_words(), overlap=8)
    assert chunks
    assert all(c.word_count <= max_chunk_words() for c in chunks)


def _model_cached() -> bool:
    try:
        import sentence_transformers  # noqa: F401
    except ImportError:
        return False
    cache = Path.home() / ".cache" / "huggingface" / "hub"
    return any(cache.glob(f"models--*{MODEL_NAME.split('/')[-1]}*")) if cache.exists() else False


@pytest.mark.skipif(not _model_cached(), reason="embedding model not cached locally")
def test_real_tokenizer_never_truncates_a_full_chunk():
    """Ground truth: chunks of CHUNK_SIZE French words stay within the model window."""
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(MODEL_NAME, device="cpu")
    budget = max_chunk_words()
    for sample in _FR_SAMPLES:
        words = sample.split()
        # Build a chunk of exactly `budget` words by repeating the sample's words.
        chunk_words = (words * ((budget // len(words)) + 1))[:budget]
        token_count = len(model.tokenizer.encode(" ".join(chunk_words)))
        assert token_count <= model.max_seq_length, (
            f"{budget} words -> {token_count} tokens > {model.max_seq_length}"
        )
