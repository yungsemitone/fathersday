"""Wine — live K&L auction lots, enriched with critic scores + market price.

What Dad wanted: real, updating K&L auction lots, each with a critic rating, and
the good ones (90+) surfaced as deals vs. their market price.

How it works now:
  1. Read the live K&L auctions page (shop.klwines.com) through the Cloudflare
     unblocker (Scrapfly). It's a Next.js app, so every lot is in a clean
     embedded JSON feed: name, vintage, current bid, # bids, end time, link.
  2. For each lot, look up the wine on Wine-Searcher (also via the unblocker) to
     get its aggregated **critic score** and **average market price**. These
     never change, so they're cached *permanently* — each wine is only ever paid
     for once — and the whole thing is capped to a monthly credit budget so the
     free Scrapfly tier is never overrun.
  3. We surface only genuine *deals*: wines from Dad's regions (France, Italy,
     Spain, Australia) scored 95+ whose per-bottle bid is below Wine-Searcher's
     market price, still live (not ended), sorted by discount.

Filtering to those countries happens BEFORE scoring, so credits are only spent
on relevant lots. No SCRAPER_API_KEY (or K&L unreachable) -> curated cellar.
"""
from __future__ import annotations

import csv
import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from urllib.parse import quote_plus

from config import (
    DATA_DIR,
    KL_AUCTION_URL,
    TTL_WINE,
    WINE_COUNTRIES,
    WINE_MIN_DISCOUNT,
    WINE_MIN_SCORE,
    WINE_SCORE_BUDGET_MONTH,
    WINE_SCORE_PER_REFRESH,
)
from scraper import fetch_unblocked

_HERE = os.path.dirname(__file__)
CELLAR_CSV = os.path.join(_HERE, "..", "data", "wine_cellar.csv")
SCORES_PATH = os.path.join(DATA_DIR or os.path.join(_HERE, "..", "data"), "wine_scores.json")

MIN_DISCOUNT = WINE_MIN_DISCOUNT   # ≥X% below market to count as a deal
MIN_SCORE = WINE_MIN_SCORE         # critic-score floor (Dad: 95+)
COUNTRIES = set(WINE_COUNTRIES)    # only these origins (Dad: FR/IT/ES/AU)
MAX_DEALS = 15                     # cap the displayed deals

_lock = threading.Lock()


def _country_ok(country: str) -> bool:
    return (country or "").strip().lower() in COUNTRIES


# ---------------------------------------------------------------------------
# Curated fallback (used when there's no scraper key / K&L is unreachable)
# ---------------------------------------------------------------------------
def _kl_search_url(name: str) -> str:
    return f"https://www.klwines.com/Products?searchText={quote_plus(name)}"


def _load_cellar() -> list[dict]:
    out = []
    try:
        with open(CELLAR_CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                try:
                    bid, mkt, score = float(r["bid"]), float(r["market_avg"]), int(r["score"])
                    if score < MIN_SCORE or bid >= mkt * (1 - MIN_DISCOUNT):
                        continue
                    if not _country_ok(r.get("country", "")):
                        continue
                    name = f"{r['name'].strip()} {r['vintage'].strip()}".strip()
                    out.append({
                        "name": name,
                        "region": f"{r['region'].strip()} · 750ml",
                        "bid": round(bid), "mkt": round(mkt),
                        "endDT": None, "left": r.get("time_left", "").strip() or "—",
                        "nbids": None, "score": score, "critic": r.get("critic", "").strip(),
                        "disc": round((1 - bid / mkt) * 100),
                        "url": _kl_search_url(name),
                    })
                except (KeyError, ValueError):
                    continue
    except FileNotFoundError:
        pass
    out.sort(key=lambda w: w["disc"], reverse=True)
    return out


# ---------------------------------------------------------------------------
# Persistent score cache + monthly credit budget
# ---------------------------------------------------------------------------
def _load_scores() -> dict:
    try:
        with open(SCORES_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, ValueError):
        data = {}
    data.setdefault("scores", {})
    meta = data.setdefault("_meta", {"month": "", "lookups": 0})
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    if meta.get("month") != month:           # reset the budget each calendar month
        meta["month"], meta["lookups"] = month, 0
    return data


def _save_scores(data: dict) -> None:
    try:
        os.makedirs(os.path.dirname(SCORES_PATH), exist_ok=True)
        tmp = SCORES_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, SCORES_PATH)
    except OSError as e:
        print("[wine] could not persist scores:", e)


# ---------------------------------------------------------------------------
# Wine-Searcher: aggregated critic score + average market price
# ---------------------------------------------------------------------------
def _ws_query(name: str) -> str:
    q = name.split(",")[0]                    # drop the trailing ", Pauillac" etc.
    q = q.replace('"', " ").replace("'", " ")
    q = re.sub(r"\b(tasting lot|lot|owc|magnum|\d+ ?x ?\d+ml|750ml)\b", " ", q, flags=re.I)
    return re.sub(r"\s+", " ", q).strip()


def _ws_lookup(name: str) -> tuple[int | None, float | None]:
    """Return (critic_score, avg_price) for a wine, or (None, None)."""
    q = _ws_query(name)
    if not q:
        return None, None
    html = fetch_unblocked(f"https://www.wine-searcher.com/find/{quote_plus(q)}")
    if not html:
        return None, None
    m = (re.search(r'"criticScore"\s*:\s*"?(\d{2,3})', html)
         or re.search(r'"aggregateRating".*?"ratingValue"\s*:\s*"?(\d{2,3})', html, re.S))
    score = int(m.group(1)) if m else None
    p = re.search(r"Avg Price[^$]*\$([0-9,]+)", html)
    price = float(p.group(1).replace(",", "")) if p else None
    return score, price


# ---------------------------------------------------------------------------
# Live K&L auction listing (Next.js __NEXT_DATA__ -> Algolia records)
# ---------------------------------------------------------------------------
def _kl_lots() -> list[dict] | None:
    html = fetch_unblocked(KL_AUCTION_URL, timeout=180.0)
    if not html:
        return None
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
        queries = data["props"]["pageProps"]["dehydratedState"]["queries"]
    except (KeyError, ValueError, TypeError):
        return None

    records = None
    for q in queries:
        d = (q.get("state") or {}).get("data")
        if isinstance(d, dict) and isinstance(d.get("records"), list):
            records = d["records"]
            break
    if not records:
        return None

    lots = []
    for w in records:
        r = w.get("record") if isinstance(w, dict) else None
        if not isinstance(r, dict) or not r.get("sku"):
            continue
        bid = r.get("winningBidAmount") or r.get("listPrice")
        if not bid:
            continue
        # Fold the vintage into the name when itemName omits it (helps WS match).
        iname = (r.get("itemName") or "").strip()
        vp = (r.get("lotVintagePrefix") or "").strip()
        if vp and not iname[:4].strip().isdigit() and not iname.lower().startswith(vp.lower()):
            iname = f"{vp} {iname}"
        count = int(r.get("lotItemCount") or 1) or 1
        region = " · ".join([p for p in [
            r.get("specificAppellation") or r.get("subRegion") or r.get("country"),
            r.get("varietal"), r.get("containerType"),
        ] if p])
        lots.append({
            "sku": str(r["sku"]),
            "name": iname,
            "region": region,
            "country": (r.get("country") or "").strip(),
            "bid": round(float(bid)),
            "count": count,
            "nbids": r.get("numberBids") or 0,
            "endDT": r.get("auctionEndDT"),
            "url": f"https://shop.klwines.com/auctions/bidding/{r['sku']}",
        })
    return lots or None


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def _active(lot: dict) -> bool:
    """True if the auction hasn't ended yet."""
    end = lot.get("endDT")
    if not end:
        return True
    try:
        return datetime.fromisoformat(end.replace("Z", "+00:00")) > datetime.now(timezone.utc)
    except ValueError:
        return True


def _build_live() -> list[dict] | None:
    """The slow path: live K&L listing + Wine-Searcher enrichment. Runs in a
    background thread (it can take minutes), never on the request path.

    Returns a list of qualifying deals (possibly empty) on success, or None if
    the listing couldn't be fetched at all (so the caller can fall back)."""
    lots = _kl_lots()
    if lots is None:
        return None

    # Only Dad's regions + still-live auctions, BEFORE we spend any score
    # lookups. (The ending-soonest feed is ~85% US, so this matters.)
    candidates = [l for l in lots if _country_ok(l["country"]) and _active(l)]
    candidates.sort(key=lambda l: l.get("endDT") or "")

    with _lock:
        store = _load_scores()
        scores, meta = store["scores"], store["_meta"]
        looked = 0
        for lot in candidates:
            key = re.sub(r"\s+", " ", lot["name"].lower()).strip()
            hit = scores.get(key)
            if hit is None and looked < WINE_SCORE_PER_REFRESH and meta["lookups"] < WINE_SCORE_BUDGET_MONTH:
                sc, pr = _ws_lookup(lot["name"])
                hit = scores[key] = {"score": sc, "price": pr, "ts": int(time.time())}
                meta["lookups"] += 1
                looked += 1
            if hit:
                lot["score"] = hit.get("score")
                lot["mkt"] = round(hit["price"]) if hit.get("price") else None
        _save_scores(store)

    # Keep only genuine deals: 95+ AND per-bottle bid meaningfully below the
    # Wine-Searcher market price (lots can be multi-bottle).
    deals = []
    for lot in candidates:
        score, mkt = lot.get("score"), lot.get("mkt")
        if not (score and score >= MIN_SCORE and mkt):
            continue
        per_bottle = lot["bid"] / max(lot.get("count", 1), 1)
        if per_bottle >= mkt * (1 - MIN_DISCOUNT):
            continue
        lot["disc"] = round((1 - per_bottle / mkt) * 100)
        lot["critic"] = "WS"
        deals.append(lot)

    deals.sort(key=lambda l: l["disc"], reverse=True)
    return deals[:MAX_DEALS]


# ---------------------------------------------------------------------------
# Public entry — non-blocking. Serves the last live result instantly and
# refreshes in the background (the live build can take minutes).
# ---------------------------------------------------------------------------
_RESULT_PATH = os.path.join(DATA_DIR or os.path.join(_HERE, "..", "data"), "wine_result.json")
_RESULT: dict = {"data": None, "at": 0.0, "tried": 0.0}
_refresh_lock = threading.Lock()


def _load_result() -> None:
    """Restore the last good result at startup so restarts/deploys don't re-scrape."""
    try:
        with open(_RESULT_PATH, encoding="utf-8") as f:
            saved = json.load(f)
        if isinstance(saved.get("data"), list):
            _RESULT["data"], _RESULT["at"] = saved["data"], float(saved.get("at", 0))
    except (FileNotFoundError, ValueError, OSError):
        pass


def _save_result() -> None:
    try:
        os.makedirs(os.path.dirname(_RESULT_PATH), exist_ok=True)
        tmp = _RESULT_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"data": _RESULT["data"], "at": _RESULT["at"]}, f)
        os.replace(tmp, _RESULT_PATH)
    except OSError as e:
        print("[wine] could not persist result:", e)


def _refresh() -> None:
    if not _refresh_lock.acquire(blocking=False):
        return                              # a refresh is already running
    try:
        _RESULT["tried"] = time.time()       # mark the attempt (success or not)
        data = _build_live()
        if data is not None:                 # [] (no deals) is a valid result
            _RESULT["data"], _RESULT["at"] = data, time.time()
            _save_result()
    except Exception as e:                   # noqa: BLE001
        print("[wine] refresh failed:", e)
    finally:
        _refresh_lock.release()


def warm() -> None:
    """Refresh in the background only if our last good result is stale. Survives
    restarts via the persisted file, so deploys don't burn credits re-scraping.
    The 'tried' timestamp throttles retries when the scraper is down."""
    last = max(_RESULT["at"], _RESULT["tried"])
    if time.time() - last > TTL_WINE and not _refresh_lock.locked():
        threading.Thread(target=_refresh, daemon=True).start()


def fetch_wine():
    warm()
    data = _RESULT["data"]
    fresh = (time.time() - _RESULT["at"]) < TTL_WINE * 2
    if data is not None and fresh:
        return [d for d in data if _active(d)]   # live deals, minus any that ended
    return _load_cellar()                          # scraper down / cold -> curated


_load_result()  # at import, restore the last good result from the volume
