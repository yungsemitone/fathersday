"""Fetch a URL through a Cloudflare-solving "unblocker" service.

K&L's auction pages (shop.klwines.com) and Wine-Searcher sit behind a Cloudflare
JS challenge, so an always-on server can't read them directly. These services
route the request through a real browser on a residential IP that passes the
challenge, and hand back the rendered HTML.

Default provider is Bright Data Web Unlocker (pay-as-you-go, ~$1.5/1k requests):
set SCRAPER_PROVIDER=brightdata + BRIGHTDATA_API_TOKEN + BRIGHTDATA_ZONE. The
credit-based providers (scrapfly/scraperapi/...) are still supported via
SCRAPER_API_KEY. Without credentials this returns None.

Be a good citizen: this is for one person's morning dashboard — keep the refresh
interval modest, not a scraper farm.
"""
from __future__ import annotations

import time

import httpx

from config import (
    BRIGHTDATA_API_TOKEN,
    BRIGHTDATA_ZONE,
    SCRAPER_API_KEY,
    SCRAPER_PROVIDER,
)


def _configured() -> bool:
    if SCRAPER_PROVIDER.lower() == "brightdata":
        return bool(BRIGHTDATA_API_TOKEN and BRIGHTDATA_ZONE)
    return bool(SCRAPER_API_KEY)


# Credit-based providers use a simple GET API with these params (JS render +
# the anti-bot/residential mode needed to clear Cloudflare).
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


def _fetch_brightdata(url: str, timeout: float, attempts: int) -> str | None:
    """Bright Data Web Unlocker API — a POST that returns the raw unblocked HTML."""
    last = None
    for i in range(attempts):
        try:
            r = httpx.post(
                "https://api.brightdata.com/request",
                headers={"Authorization": f"Bearer {BRIGHTDATA_API_TOKEN}"},
                json={"zone": BRIGHTDATA_ZONE, "url": url, "format": "raw"},
                timeout=timeout,
            )
            r.raise_for_status()
            return r.text
        except Exception as e:  # noqa: BLE001
            last = e
            if i + 1 < attempts:
                time.sleep(3 * (i + 1))
    print(f"[scraper] brightdata failed for {url} after {attempts} tries: {last}")
    return None


def fetch_unblocked(url: str, timeout: float = 130.0, attempts: int = 2) -> str | None:
    """Return the page's unblocked HTML/text, or None if unavailable.

    Retries transient failures — the unblockers are occasionally flaky on heavy
    pages, and don't charge for errors.
    """
    if not _configured():
        return None
    if SCRAPER_PROVIDER.lower() == "brightdata":
        return _fetch_brightdata(url, timeout, attempts)

    base, params = _request(url)
    if not base:
        print(f"[scraper] unknown SCRAPER_PROVIDER '{SCRAPER_PROVIDER}'")
        return None
    last = None
    for i in range(attempts):
        try:
            r = httpx.get(base, params=params, timeout=timeout)
            r.raise_for_status()
            if SCRAPER_PROVIDER.lower() == "scrapfly":   # Scrapfly wraps in JSON
                return (r.json().get("result") or {}).get("content")
            return r.text
        except Exception as e:  # noqa: BLE001
            last = e
            if i + 1 < attempts:
                time.sleep(3 * (i + 1))
    print(f"[scraper] {SCRAPER_PROVIDER} failed for {url} after {attempts} tries: {last}")
    return None
