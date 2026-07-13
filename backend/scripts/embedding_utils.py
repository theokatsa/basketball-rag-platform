from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def get_embedding_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer("all-MiniLM-L6-v2")


def build_embedding(text: str) -> str:
    model = get_embedding_model()
    vector = model.encode(text, normalize_embeddings=True)
    return "[" + ",".join(f"{value:.6f}" for value in vector.tolist()) + "]"