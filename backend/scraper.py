"""Fetch a URL through a Cloudflare-solving "unblocker" service.

K&L's auction pages (shop.klwines.com) sit behind a Cloudflare JS challenge, so
an always-on server can't read them directly. These services route the request
through a real browser on a residential IP that passes the challenge, and hand
back the rendered HTML. Set SCRAPER_PROVIDER + SCRAPER_API_KEY; without a key
this returns None and the wine section falls back to the curated cellar.

Be a good citizen: this is for one person's morning dashboard — keep the cache
long (a few hits a day), not a scraper farm.
"""
from __future__ import annotations

import time

import httpx

from config import SCRAPER_API_KEY, SCRAPER_PROVIDER

# Each provider: (endpoint, param-builder). All enable JS rendering + the
# anti-bot/residential mode needed to clear Cloudflare's challenge.
def _request(url: str):
    key, p = SCRAPER_API_KEY, SCRAPER_PROVIDER.lower()
    if p == "scraperapi":
        return "https://api.scraperapi.com/", {
            "api_key": key, "url": url, "render": "true", "ultra_premium": "true",
        }
    if p == "scrapingbee":
        return "https://app.scrapingbee.com/api/v1/", {
            "api_key": key, "url": url, "render_js": "true", "stealth_proxy": "true",
        }
    if p == "scrapfly":
        return "https://api.scrapfly.io/scrape", {
            "key": key, "url": url, "asp": "true", "render_js": "true",
        }
    if p == "zenrows":
        return "https://api.zenrows.com/v1/", {
            "apikey": key, "url": url, "js_render": "true", "antibot": "true",
        }
    return None, None


def fetch_unblocked(url: str, timeout: float = 130.0, attempts: int = 2) -> str | None:
    """Return the page's rendered HTML/text, or None if unavailable.

    Retries transient failures (timeouts, 422/429/5xx) — the unblocker is
    occasionally flaky on heavy pages, and providers don't charge for errors.
    """
    if not SCRAPER_API_KEY:
        return None
    base, params = _request(url)
    if not base:
        print(f"[scraper] unknown SCRAPER_PROVIDER '{SCRAPER_PROVIDER}'")
        return None
    last = None
    for i in range(attempts):
        try:
            r = httpx.get(base, params=params, timeout=timeout)
            r.raise_for_status()
            # Scrapfly wraps the page in JSON: {"result": {"content": "..."}}
            if SCRAPER_PROVIDER.lower() == "scrapfly":
                return (r.json().get("result") or {}).get("content")
            return r.text
        except Exception as e:  # noqa: BLE001 - fail soft to curated cellar
            last = e
            if i + 1 < attempts:
                time.sleep(3 * (i + 1))
    print(f"[scraper] {SCRAPER_PROVIDER} failed for {url} after {attempts} tries: {last}")
    return None
