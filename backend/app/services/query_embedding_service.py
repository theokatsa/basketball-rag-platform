from functools import lru_cache


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer("all-MiniLM-L6-v2")


def embed_query(value: str) -> str:
    """Embed queries with the same model used to index player profiles."""
    vector = _get_model().encode(value, normalize_embeddings=True)
    return "[" + ",".join(f"{item:.6f}" for item in vector.tolist()) + "]"
