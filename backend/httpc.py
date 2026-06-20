"""Shared HTTP helper.

A single httpx client with a real browser User-Agent (several upstreams 403
the default Python UA), sane timeouts, and small JSON/text helpers that never
raise — callers get None on failure and fall back to sample/curated data.
"""
from __future__ import annotations

import httpx

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/html, application/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_client = httpx.Client(
    headers=HEADERS,
    timeout=httpx.Timeout(12.0, connect=6.0),
    follow_redirects=True,
)


def get_json(url: str, params: dict | None = None) -> dict | list | None:
    try:
        r = _client.get(url, params=params)
        r.raise_for_status()
        return r.json()
    except Exception as e:  # noqa: BLE001 - fail soft by design
        print(f"[http] GET json failed {url}: {e}")
        return None


def get_text(url: str, params: dict | None = None) -> str | None:
    try:
        r = _client.get(url, params=params)
        r.raise_for_status()
        return r.text
    except Exception as e:  # noqa: BLE001
        print(f"[http] GET text failed {url}: {e}")
        return None
