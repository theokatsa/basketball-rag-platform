"""Which statistic a question is about when it does not name one ("who crashes the boards?").

A small classifier on top of the embeddings, trained by training/train_router.py on the phrases in
training/phrases.py. Its first guess is right too rarely to act on, but the right statistic is among
its first three about two times in three, so it is used to ask back.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np

from app.services.query_embedding_service import MODEL_NAME, encode

FILE = Path(__file__).resolve().parents[2] / "models" / "router.npz"


@lru_cache(maxsize=1)
def _load():
    if not FILE.exists():
        return None
    stored = np.load(FILE)
    info = json.loads(str(stored["info"]))
    # A classifier belongs to the embedding model it was trained on.
    return {"weights": stored["weights"], "bias": stored["bias"], **info} if info["model"] == MODEL_NAME else None


def suggest(question: str, count: int = 3) -> list[str]:
    """The statistics a question may be about, likeliest first; empty when it looks unrelated."""
    model = _load()
    if model is None:
        return []
    order = np.argsort(-(encode([question])[0] @ model["weights"].T + model["bias"]))
    words = [model["words"][i] for i in order[: count + 1]]
    return [] if not words[0] else [w for w in words if w][:count]
