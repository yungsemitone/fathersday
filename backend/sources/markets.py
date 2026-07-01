"""Markets — sourced from Dad's *Stock Scraper* app, not re-fetched here.

The whole point: Dad already curates watchlists in the Stock Scraper dashboard.
This pulls those same lists (plus the broad "tape" and the macro backdrop) from
that app's API, so the two stay in sync. Point STOCK_API_BASE at it.

Endpoints consumed (all already exist in the Stock Scraper backend):
  GET /api/watchlists  -> {"lists":[{"name","symbols","quotes":[{symbol,name,price,change,change_pct}]}]}
  GET /api/overview    -> {"<class>":[{symbol,name,price,change_pct}, ...]}
  GET /api/economy     -> {"indicators":[{id,label,unit,value,prev,as_of}, ...]}

Returns the shape the frontend expects:
  {"watchlist":[{t,name,px,chg}], "indices":[{t,px,chg,unit}], "macro":[{k,v,d,dir}],
   "listName": str}
Any sub-section may be None if that upstream call fails; the frontend fills the
gap with its built-in sample so the page always renders.
"""
from __future__ import annotations

from cache import cached
from config import FEATURED_WATCHLIST, STOCK_API_BASE, TTL_MARKETS
from httpc import get_json

# --- The "tape": which broad instruments to show, and how to label them. ----
# Yahoo symbol -> (display label, unit). Levels (yields, VIX) get no $; "%" for rates.
TAPE = [
    ("^GSPC", "S&P 500", ""),
    ("^IXIC", "Nasdaq", ""),
    ("^DJI", "Dow", ""),
    ("^RUT", "Russell 2000", ""),
    ("^VIX", "VIX", ""),
    ("GC=F", "Gold", ""),
    ("CL=F", "WTI Crude", ""),
    ("^TNX", "10Y Yield", "%"),
]

# --- Macro strip: which FRED indicators, short label, and good/bad direction.
# id -> (short label). Direction is inferred from value vs prev.
MACRO_PICKS = {
    "FEDFUNDS": "Fed funds",
    "CPILFESL": "Core CPI",
    "UNRATE": "Unemployment",
    "T10Y2Y": "10Y–2Y",
}
MACRO_ORDER = ["FEDFUNDS", "CPILFESL", "UNRATE", "T10Y2Y"]


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _watchlists():
    """All of Dad's lists as [{name, rows}], plus the default list's name."""
    data = get_json(f"{STOCK_API_BASE}/api/watchlists")
    lists = (data or {}).get("lists") if isinstance(data, dict) else None
    if not lists:
        return None, None

    out = []
    for l in lists:
        rows = []
        for q in l.get("quotes", []):
            px, chg = _num(q.get("price")), _num(q.get("change_pct"))
            if px is None:
                continue
            rows.append({
                "t": q.get("symbol", "?"),
                "name": q.get("name", ""),
                "px": px,
                "chg": chg if chg is not None else 0.0,
            })
        if rows:
            out.append({"name": l.get("name", ""), "rows": rows})
    if not out:
        return None, None
    default = next((l["name"] for l in out if l["name"] == FEATURED_WATCHLIST), out[0]["name"])
    return out, default


def _tape():
    data = get_json(f"{STOCK_API_BASE}/api/overview")
    if not isinstance(data, dict):
        return None
    # Flatten every class into one symbol -> quote map.
    by_symbol = {}
    for quotes in data.values():
        if isinstance(quotes, list):
            for q in quotes:
                if isinstance(q, dict) and q.get("symbol"):
                    by_symbol[q["symbol"]] = q

    rows = []
    for sym, label, unit in TAPE:
        q = by_symbol.get(sym)
        if not q:
            continue
        px, chg = _num(q.get("price")), _num(q.get("change_pct"))
        if px is None:
            continue
        rows.append({"t": label, "px": px, "chg": chg if chg is not None else 0.0, "unit": unit})
    return rows or None


def _macro():
    data = get_json(f"{STOCK_API_BASE}/api/economy")
    inds = (data or {}).get("indicators") if isinstance(data, dict) else None
    if not inds:
        return None
    by_id = {i.get("id"): i for i in inds if isinstance(i, dict)}

    out = []
    for fred_id in MACRO_ORDER:
        ind = by_id.get(fred_id)
        if not ind:
            continue
        val, prev = _num(ind.get("value")), _num(ind.get("prev"))
        unit = ind.get("unit", "")
        suffix = "%" if unit == "%" else ""
        v = f"{val:.2f}{suffix}" if val is not None else "—"
        # Direction + a short delta note vs the prior print.
        direction, note = "neutral", "—"
        if val is not None and prev is not None:
            diff = val - prev
            if abs(diff) < 1e-9:
                note = "unch"
            else:
                direction = "up" if diff > 0 else "down"
                note = f"{'+' if diff > 0 else ''}{diff:.2f} vs prior"
        out.append({"k": MACRO_PICKS[fred_id], "v": v, "d": note, "dir": direction})
    return out or None


@cached(ttl_seconds=TTL_MARKETS)
def fetch_markets():
    lists, default_name = _watchlists()
    indices = _tape()
    macro = _macro()

    # If literally nothing came back, the Stock Scraper API is unreachable —
    # let the frontend show its sample. Otherwise return partial (None sections
    # are sample-filled client-side).
    if lists is None and indices is None and macro is None:
        return None

    # The default list's rows also power the home dispatch + a simple fallback.
    default_rows = None
    if lists:
        d = next((l for l in lists if l["name"] == default_name), lists[0])
        default_rows = d["rows"]

    return {
        "lists": lists,
        "watchlist": default_rows,
        "listName": default_name,
        "indices": indices,
        "macro": macro,
    }
