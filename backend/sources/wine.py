"""Wine — "mispriced 90+ at K&L".

The idea Dad asked for: find bottles on the K&L auction marketplace whose
current bid sits meaningfully below the wine's going market price — but only the
*good* ones, i.e. wines a critic scored 90+.

Reality check: klwines.com sits behind bot protection and returns 403 to
automated requests (including from cloud servers like Fly). So:
  • _scrape_kl_auction() is wired and ready — it lights up if this ever runs
    from an un-blocked IP (e.g. Dad's home machine / a residential proxy).
  • Until then we use a curated cellar (data/wine_cellar.csv): real wines, real
    critic scores (≥90), realistic K&L price points. Edit that file to track the
    bottles Dad actually buys.

Both paths run through the same filter — score ≥ 90 and bid ≥ MIN_DISCOUNT below
market — so the logic is identical whether data is live or curated.

Returns items shaped: { name, region, bid, mkt, left, score, critic }
(the frontend computes discount % and sorts.)
"""
from __future__ import annotations

import csv
import os
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from cache import cached
from config import TTL_WINE
from httpc import get_text


def _kl_search_url(name: str) -> str:
    """A K&L marketplace search for the bottle (used when we lack a live lot URL)."""
    return f"https://www.klwines.com/Products?searchText={quote_plus(name)}"

CELLAR_CSV = os.path.join(os.path.dirname(__file__), "..", "data", "wine_cellar.csv")
KL_AUCTION_URL = "https://www.klwines.com/auctions"

MIN_DISCOUNT = 0.12   # surface lots ≥12% below market
MIN_SCORE = 90        # Dad's bar: critic score 90+


def _load_cellar() -> list[dict]:
    rows = []
    try:
        with open(CELLAR_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    rows.append({
                        "name": f"{r['name'].strip()} {r['vintage'].strip()}".strip(),
                        "region": r["region"].strip(),
                        "bid": float(r["bid"]),
                        "mkt": float(r["market_avg"]),
                        "left": r.get("time_left", "").strip() or "—",
                        "score": int(r["score"]),
                        "critic": r.get("critic", "").strip(),
                    })
                except (KeyError, ValueError):
                    continue
    except FileNotFoundError:
        pass
    return rows


def _scrape_kl_auction() -> list[dict] | None:
    """Best-effort live scrape. Returns None if blocked (the usual case)."""
    html = get_text(KL_AUCTION_URL)
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    lots = []
    # Selectors are best-guess; confirm against the live markup when reachable.
    for el in soup.select(".auction-item, .lot, .result-item"):
        try:
            name = el.select_one(".lot-title, .auction-item-name, h2, h3").get_text(strip=True)
            bid_text = el.select_one(".current-bid, .price, .bid-amount").get_text(strip=True)
            bid = float(bid_text.replace("$", "").replace(",", "").split()[0])
            left_el = el.select_one(".time-left, .countdown, .ends")
            lots.append({
                "name": name,
                "region": "",
                "bid": bid,
                "left": left_el.get_text(strip=True) if left_el else "—",
                "score": None, "critic": "",
            })
        except (AttributeError, ValueError, IndexError):
            continue
    return lots or None


def _qualify(rows: list[dict]) -> list[dict]:
    """Keep 90+ scored lots trading ≥MIN_DISCOUNT below market."""
    out = []
    for r in rows:
        score = r.get("score")
        mkt = r.get("mkt")
        if score is None or score < MIN_SCORE:
            continue
        if not mkt or r["bid"] >= mkt * (1 - MIN_DISCOUNT):
            continue
        out.append({
            "name": r["name"],
            "region": f"{r['region']} · 750ml" if r.get("region") else "750ml",
            "bid": round(r["bid"]),
            "mkt": round(mkt),
            "left": r.get("left", "—"),
            "score": score,
            "critic": r.get("critic", ""),
            # Real lot URL when scraped live; otherwise a K&L search for the bottle.
            "url": r.get("url") or _kl_search_url(r["name"]),
        })
    out.sort(key=lambda w: (w["mkt"] - w["bid"]) / w["mkt"], reverse=True)
    return out


@cached(ttl_seconds=TTL_WINE)
def fetch_wine():
    # Live first (lights up when K&L is reachable); curated cellar otherwise.
    live = _scrape_kl_auction()
    if live:
        # Live lots have no score yet — match names against the cellar to attach
        # critic scores, then qualify. Anything we can't score is dropped.
        cellar = {r["name"].lower(): r for r in _load_cellar()}
        for lot in live:
            match = cellar.get(lot["name"].lower())
            if match:
                lot["score"] = match["score"]
                lot["critic"] = match["critic"]
                lot["mkt"] = match["mkt"]
                lot["region"] = match["region"]
        qualified = _qualify([l for l in live if l.get("mkt")])
        if qualified:
            return qualified

    return _qualify(_load_cellar()) or None
