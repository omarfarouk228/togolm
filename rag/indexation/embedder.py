"""
Embedding backend for TogoLM.

Priority:
  1. sentence-transformers (local, no API key, default)
  2. Gemini Embeddings API (when GEMINI_API_KEY is set — for production)

Both produce 384-dim vectors compatible with the pgvector schema.
"""

import os

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"  # 384-dim, multilingual, ~120 MB

# The local model silently truncates inputs past max_seq_length, so chunks MUST be
# sized to fit or their tail is never embedded. Sizing always targets the local
# budget because embed_batch falls back to the local model when the Gemini quota
# is exhausted mid-run.
LOCAL_MAX_TOKENS = 128  # paraphrase-multilingual-MiniLM-L12-v2 max_seq_length
_SPECIAL_TOKENS = 2  # [CLS] + [SEP]
# Worst-case subword-per-word ratio measured on French Togo text for this model
# (observed 1.6–2.0). Using the upper bound guarantees no truncation.
_TOKENS_PER_WORD = 2.1


def max_chunk_words(max_tokens: int = LOCAL_MAX_TOKENS) -> int:
    """Largest word count whose embedding fits within the model's token window."""
    return max(16, int((max_tokens - _SPECIAL_TOKENS) / _TOKENS_PER_WORD))


class LocalEmbedder:
    """Sentence-transformers local embedder. Downloaded once, then cached."""

    def __init__(self, model_name: str = MODEL_NAME):
        self.model_name = model_name
        self._model = None

    def _best_device(self) -> str:
        try:
            import torch

            if torch.backends.mps.is_available():
                return "mps"
            if torch.cuda.is_available():
                return "cuda"
        except ImportError:
            pass
        return "cpu"

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            device = self._best_device()
            print(f"Loading embedding model '{self.model_name}' on {device}...")
            self._model = SentenceTransformer(self.model_name, device=device)
        return self._model

    def encode(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vectors]

    def encode_one(self, text: str) -> list[float]:
        return self.encode([text])[0]


class GeminiEmbedder:
    """Gemini text-embedding-004 via google-genai SDK — requires GEMINI_API_KEY."""

    MODEL = "gemini-embedding-001"  # 3072 dims by default, can be truncated to 768

    TARGET_DIMS = 384

    def __init__(self):
        from google import genai
        from google.genai import types

        self._client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        self._types = types

    def encode(self, texts: list[str]) -> list[list[float]]:
        result = self._client.models.embed_content(
            model=self.MODEL,
            contents=texts,
            config=self._types.EmbedContentConfig(
                output_dimensionality=self.TARGET_DIMS,
                task_type="RETRIEVAL_DOCUMENT",
            ),
        )
        return [e.values for e in result.embeddings]

    def encode_one(self, text: str) -> list[float]:
        return self.encode([text])[0]


def _has_valid_gemini_key() -> bool:
    key = os.getenv("GEMINI_API_KEY", "")
    return bool(key) and len(key) > 10


def get_embedder() -> LocalEmbedder | GeminiEmbedder:
    """Return the best available embedder."""
    if _has_valid_gemini_key():
        return GeminiEmbedder()
    return LocalEmbedder()
