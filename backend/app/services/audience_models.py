"""Ways of learning which players belong together from what people open.

All of them start from a visit x player matrix (1 when a player was opened in a visit) and return
a player x player matrix of scores; row i ranks what to show next to player i. numpy only: the
catalogue has a few hundred players, so closed forms are exact and take milliseconds.
"""

from __future__ import annotations

import numpy as np


def counts(x: np.ndarray) -> np.ndarray:
    """In how many visits (weighted) two players were opened together."""
    c = x.T @ x
    np.fill_diagonal(c, 0)
    return c


def popularity(x: np.ndarray) -> np.ndarray:
    return np.tile(x.sum(axis=0), (x.shape[1], 1))


def cosine(x: np.ndarray, shrink: float = 0.0) -> np.ndarray:
    """Together, over the root of both audiences; shrink mistrusts pairs seen rarely."""
    c, n = counts(x), x.sum(axis=0)
    return c / (np.sqrt(np.outer(n, n)) + shrink + 1e-9)


def jaccard(x: np.ndarray) -> np.ndarray:
    c, n = counts(x), x.sum(axis=0)
    return c / (n[:, None] + n[None, :] - c + 1e-9)


def ppmi(x: np.ndarray, power: float = 0.75) -> np.ndarray:
    """Positive pointwise mutual information: together more often than chance."""
    c = counts(x)
    row, context = c.sum(axis=1), c.sum(axis=0) ** power
    with np.errstate(divide="ignore", invalid="ignore"):
        value = np.log(c * context.sum() / (row[:, None] * context[None, :]))
    return np.where(np.isfinite(value) & (value > 0), value, 0.0)


def item2vec(x: np.ndarray, size: int = 48) -> np.ndarray:
    """Embeddings of players from their company: a factorised PPMI matrix, which is what
    word2vec with negative sampling approximates (Levy and Goldberg, 2014)."""
    u, s, _ = np.linalg.svd(ppmi(x))
    e = u[:, :size] * np.sqrt(s[:size])
    e /= np.linalg.norm(e, axis=1, keepdims=True) + 1e-9
    return e @ e.T


def ease(x: np.ndarray, reg: float = 50.0) -> np.ndarray:
    """Predicts each player from all the others by ridge regression (EASE, Steck 2019), so two
    players that only share a popular third one are not linked."""
    g = x.T @ x
    p = np.linalg.inv(g + reg * np.eye(len(g)))
    b = -p / np.diag(p)[None, :]
    np.fill_diagonal(b, 0)
    return b


def walk(x: np.ndarray, restart: float = 0.4, steps: int = 20) -> np.ndarray:
    """Personalised PageRank: a walk over the graph of shared visits that keeps returning home.
    Reaches players two steps away when direct evidence is thin."""
    c = counts(x)
    t = c / (c.sum(axis=1, keepdims=True) + 1e-9)
    home = np.eye(len(c))
    p = home.copy()
    for _ in range(steps):
        p = restart * home + (1 - restart) * p @ t
    # Dividing by the root of popularity keeps the hubs from winning everywhere.
    return p / np.sqrt(c.sum(axis=0) + 1.0)[None, :]


def scaled(m: np.ndarray) -> np.ndarray:
    """Each row as ranks between 0 and 1, so that different scores can be mixed."""
    order = m.argsort(axis=1).argsort(axis=1).astype(float)
    return order / (m.shape[1] - 1)


def standardised(m: np.ndarray) -> np.ndarray:
    """Each row with mean 0 and spread 1; unlike ranks, a clear winner keeps its lead."""
    return np.clip((m - m.mean(axis=1, keepdims=True)) / (m.std(axis=1, keepdims=True) + 1e-9), -3, 12)
