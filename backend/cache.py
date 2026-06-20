"""Minimal in-memory TTL cache, keyed by the call's arguments.

A morning dashboard doesn't need real-time data, and several upstreams
(ESPN, RSS, Open-Meteo) prefer you don't hammer them. Wrap any fetch with
@cached(ttl_seconds=...) and it only hits the network when the value is stale.

Unlike a single-slot cache, this keys on *args/**kwargs, so
fetch_team_detail("lakers") and fetch_team_detail("dodgers") cache separately.
"""
import functools
import threading
import time


def cached(ttl_seconds: int):
    def decorator(fn):
        store: dict = {}
        lock = threading.Lock()

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.time()
            with lock:
                hit = store.get(key)
                if hit is not None and (now - hit[1]) < ttl_seconds:
                    return hit[0]
            value = fn(*args, **kwargs)
            with lock:
                store[key] = (value, now)
            return value

        wrapper.cache_clear = store.clear  # handy in tests
        return wrapper

    return decorator
