from functools import lru_cache
from pathlib import Path

from app.core.config import EMBEDDING_MODEL as MODEL_NAME

MODELS = Path(__file__).resolve().parents[2] / "models"


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer

    local = MODELS / MODEL_NAME
    return SentenceTransformer(str(local) if local.exists() else MODEL_NAME)


def to_literal(vector) -> str:
    """The text form pgvector accepts for a vector value."""
    return "[" + ",".join(f"{float(item):.6f}" for item in vector) + "]"


def encode(values: list[str]):
    """Unit-length vectors, so a dot product is the cosine similarity."""
    return _get_model().encode(values, normalize_embeddings=True, batch_size=64)


@lru_cache(maxsize=512)
def embed_query(value: str) -> str:
    """Questions and documents must be embedded by the same model to be comparable."""
    return to_literal(encode([value])[0])


def embed_documents(values: list[str]) -> list[str]:
    return [to_literal(vector) for vector in encode(values)]


def warm_up() -> None:
    """Load the model ahead of the first question, which would otherwise wait for it."""
    embed_query("warm up")
