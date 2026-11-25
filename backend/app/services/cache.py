"""Small in-process cache for season data, which only changes when an ingest script runs."""

import threading
import time

_store: dict = {}
_locks: dict = {}
_guard = threading.Lock()
SECONDS = 1800


def cached(key, loader):
    hit = _store.get(key)
    if hit and time.monotonic() - hit[0] < SECONDS:
        return hit[1]
    with _guard:
        lock = _locks.setdefault(key, threading.RLock())
    with lock:  # only one request pays for a cold value
        hit = _store.get(key)
        if hit and time.monotonic() - hit[0] < SECONDS:
            return hit[1]
        value = loader()
        _store[key] = (time.monotonic(), value)
        return value


def rows(db, sql, params=None):
    return [dict(r) for r in db.execute(sql, params or {}).mappings()]
