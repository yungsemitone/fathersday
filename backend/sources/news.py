"""News — financial-markets headlines from keyless RSS.

Each story carries a title, a short summary, and a link to the original article
(the frontend makes the whole card clickable). Feeds were chosen for market
relevance and because they serve cleanly with a browser User-Agent.

Returns items shaped: { src, h, s, url }
"""
from __future__ import annotations

import html
import re
import time

import feedparser

from cache import cached
from config import TTL_NEWS
from httpc import HEADERS

# (source label, feed url). All verified to return clean XML with a browser UA.
# Markets-focused first; these drive what's "moving things" for Dad.
FEEDS = [
    ("WSJ Markets", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
    ("Yahoo Finance", "https://finance.yahoo.com/news/rssindex"),
    ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
]

# Drop personal-finance / advice-column fluff — Dad wants market movers, not
# "Should I retire at 60?" These markers are common in general topstories feeds.
EXCLUDE = re.compile(
    r"\bretire(?:ment|d|s)?\b|social security|\b401\(?k\)?\b|\bira\b|moneyist|"
    r"\bmy (?:\w+ ){0,2}(?:husband|wife|son|daughter|mother|father|mom|dad|sister|brother|partner|parents?|kids?|in-laws?)\b|"
    r"\bi (?:spent|inherited|paid|owe)\b|\bshould i\b|\bi'?m \d{2}\b|\bdear \b|"
    r"inherit|personal finance|how to (?:save|retire|budget|pay off)",
    re.I,
)

# Per-feed cap so one chatty source can't dominate, plus an overall cap.
PER_FEED = 5
MAX_STORIES = 8


def _clean(text: str, limit: int = 260) -> str:
    text = re.sub(r"<[^>]+>", "", text or "")        # strip tags
    text = html.unescape(text).strip()
    text = re.sub(r"\s+", " ", text)
    return (text[: limit - 1] + "…") if len(text) > limit else text


@cached(ttl_seconds=TTL_NEWS)
def fetch_news():
    stories, seen = [], set()
    for src, url in FEEDS:
        try:
            feed = feedparser.parse(url, request_headers=HEADERS)
        except Exception as e:  # noqa: BLE001
            print(f"[news] {src} failed: {e}")
            continue
        for entry in feed.entries[:PER_FEED]:
            title = _clean(entry.get("title", ""), 160)
            key = title.lower()
            if not title or key in seen or EXCLUDE.search(title):
                continue
            seen.add(key)
            stories.append({
                "src": src,
                "h": title,
                "s": _clean(entry.get("summary", entry.get("description", ""))),
                "url": entry.get("link", ""),
                "_t": entry.get("published_parsed") or entry.get("updated_parsed"),
            })

    if not stories:
        return None

    # Newest first where timestamps exist (fall back to the epoch).
    epoch = time.gmtime(0)
    stories.sort(key=lambda s: s.get("_t") or epoch, reverse=True)
    return [{k: s[k] for k in ("src", "h", "s", "url")} for s in stories[:MAX_STORIES]]
