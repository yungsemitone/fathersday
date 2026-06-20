"""Sports — Lakers, Dodgers, USC via ESPN's keyless public JSON.

Two layers:
  • fetch_sports()        -> the four home cards (3 ESPN teams + the WSL summary)
  • fetch_team_detail(k)  -> a full page for one team: record/standing, news,
                             roster, season stats, and recent + upcoming schedule

ESPN's endpoints are undocumented and field names occasionally shift, so every
parser is defensive (lots of .get()) and returns partial data rather than
blowing up. WSL lives in wsl.py (no ESPN coverage).
"""
from __future__ import annotations

from cache import cached
from config import TTL_SPORTS, TTL_SPORTS_DETAIL
from httpc import get_json
from . import wsl

ESPN = "https://site.api.espn.com/apis/site/v2/sports"

# key -> everything we need to address ESPN + brand the card.
TEAMS = {
    "lakers": {
        "sport": "basketball", "league": "nba", "path": "lal", "id": "13",
        "name": "Lakers", "league_label": "NBA", "color": "#FDB927", "badge": "LAL",
    },
    "dodgers": {
        "sport": "baseball", "league": "mlb", "path": "lad", "id": "19",
        "name": "Dodgers", "league_label": "MLB", "color": "#005A9C", "badge": "LAD",
    },
    "usc": {
        "sport": "football", "league": "college-football", "path": "30", "id": "30",
        "name": "USC Trojans", "league_label": "NCAA", "color": "#990000", "badge": "USC",
    },
}

# Ordered, curated team season stats: (ESPN stat name, label, format).
# Labels are sport-neutral so they read right for hoops and baseball alike.
# We show the first STAT_CAP of these that the team actually reports.
STAT_ORDER = [
    ("winPercent", "Win %", "pct"),
    ("avgPointsFor", "Scored / game", "f1"),
    ("avgPointsAgainst", "Allowed / game", "f1"),
    ("pointDifferential", "Scoring margin", "signint"),
    ("streak", "Streak", "streak"),
    ("gamesBehind", "Games behind", "num"),
    ("playoffSeed", "Seed", "int"),
]
STAT_CAP = 6


def _fmt_stat(value, display, kind: str) -> str:
    if isinstance(value, (int, float)):
        if kind == "pct":
            return f"{value:.3f}".lstrip("0") or "0"   # .646
        if kind == "f1":
            return f"{value:.1f}"
        if kind == "signint":
            return f"{int(value):+d}" if value else "0"
        if kind == "int":
            return str(int(value))
        if kind == "streak":
            n = int(value)
            return f"W{n}" if n > 0 else f"L{abs(n)}" if n < 0 else "—"
    # num: ESPN's displayValue is best ("+2.5" games behind, etc.)
    if display is not None:
        return str(display)
    if isinstance(value, (int, float)):
        return str(int(value)) if float(value).is_integer() else str(value)
    return "—"


def _base(team: dict) -> str:
    return f"{ESPN}/{team['sport']}/{team['league']}"


# --------------------------------------------------------------------------
# Event parsing (shared by home card + schedule)
# --------------------------------------------------------------------------
def _parse_event(ev: dict, our_id: str, our_name: str) -> dict | None:
    comp = (ev.get("competitions") or [{}])[0]
    competitors = comp.get("competitors", [])
    if not competitors:
        return None

    def is_us(c):
        t = c.get("team") or {}
        return str(t.get("id")) == our_id or t.get("displayName", "") in our_name

    us = next((c for c in competitors if is_us(c)), None)
    them = next((c for c in competitors if c is not us), {})
    if us is None:
        return None

    them_team = them.get("team") or {}
    status = (comp.get("status") or {}).get("type", {}) or {}
    completed = bool(status.get("completed"))
    home_away = us.get("homeAway", "")
    prefix = "vs" if home_away == "home" else "@"

    out = {
        "date": ev.get("date", "")[:10],
        "opp": them_team.get("abbreviation") or them_team.get("displayName", "?"),
        "opp_name": them_team.get("displayName", ""),
        "where": prefix,
        "completed": completed,
        "result": None,
        "res": "",
    }
    if completed:
        try:
            ours = int(us.get("score", {}).get("value", us.get("score", 0)) if isinstance(us.get("score"), dict) else us.get("score", 0))
            theirs = int(them.get("score", {}).get("value", them.get("score", 0)) if isinstance(them.get("score"), dict) else them.get("score", 0))
            won = us.get("winner", ours > theirs)
            out["res"] = "win" if won else "loss"
            out["result"] = f"{'W' if won else 'L'} {ours}–{theirs}"
        except (TypeError, ValueError):
            pass
    return out


# --------------------------------------------------------------------------
# Home cards
# --------------------------------------------------------------------------
def _team_card(key: str, team: dict) -> dict | None:
    data = get_json(f"{_base(team)}/teams/{team['path']}")
    t = (data or {}).get("team") if isinstance(data, dict) else None
    if not t:
        return None

    # Record summary, e.g. "53-29"
    rec = ""
    for item in (t.get("record") or {}).get("items", []):
        if item.get("type") == "total":
            rec = item.get("summary", "")
            break
    standing = t.get("standingSummary", "")
    line = " · ".join([p for p in [rec, standing] if p]) or team["name"]

    # Next game from nextEvent
    detail = "Season complete — check back next season"
    nxt = (t.get("nextEvent") or [])
    if nxt:
        ev = _parse_event(nxt[0], team["id"], team["name"])
        if ev:
            detail = f"Next: {ev['where']} {ev['opp']} · {ev['date']}"

    return {
        "key": key, "league": team["league_label"], "team": team["name"],
        "color": team["color"], "abbr": team["badge"],
        "line": line, "detail": detail, "res": "",
    }


@cached(ttl_seconds=TTL_SPORTS)
def fetch_sports():
    cards = []
    for key, team in TEAMS.items():
        card = _team_card(key, team)
        if card:
            cards.append(card)
    cards.append(wsl.wsl_card())
    return cards or None


# --------------------------------------------------------------------------
# Per-team detail page
# --------------------------------------------------------------------------
def _detail_news(team: dict) -> list[dict]:
    data = get_json(f"{_base(team)}/news", params={"team": team["id"], "limit": 12})
    arts = (data or {}).get("articles", []) if isinstance(data, dict) else []
    out = []
    for a in arts:
        link = (((a.get("links") or {}).get("web") or {}).get("href")) or ""
        if not link:
            links = a.get("links") or []
            link = links[0].get("href") if links and isinstance(links, list) else ""
        if not link:
            continue
        img = ""
        imgs = a.get("images") or []
        if imgs and isinstance(imgs, list):
            img = imgs[0].get("url", "")
        out.append({
            "h": a.get("headline", ""),
            "s": (a.get("description", "") or "")[:240],
            "url": link,
            "img": img,
        })
        if len(out) >= 8:
            break
    return out


def _detail_roster(team: dict) -> list[dict]:
    data = get_json(f"{_base(team)}/teams/{team['path']}/roster")
    raw = (data or {}).get("athletes", []) if isinstance(data, dict) else []
    # MLB groups by position ({position, items:[...]}); NBA is a flat list.
    athletes = []
    for a in raw:
        if isinstance(a, dict) and "items" in a:
            athletes.extend(a.get("items", []))
        else:
            athletes.append(a)

    out = []
    for a in athletes:
        pos = (a.get("position") or {}).get("abbreviation") or (a.get("position") or {}).get("name", "")
        out.append({
            "name": a.get("displayName") or a.get("fullName", ""),
            "num": a.get("jersey", ""),
            "pos": pos,
            "age": a.get("age", ""),
            "ht": a.get("displayHeight", ""),
            "wt": a.get("displayWeight", ""),
            "headshot": (a.get("headshot") or {}).get("href", ""),
        })
    return out


def _detail_stats(record: dict) -> dict:
    """Pull season team stats + home/road splits from the team record block."""
    items = (record or {}).get("items", [])
    total = next((i for i in items if i.get("type") == "total"), {})
    splits = {i.get("type"): i.get("summary", "") for i in items if i.get("type") in ("home", "road", "vsconf")}
    by_name = {s.get("name"): s for s in total.get("stats", [])}

    stats = []
    for name, label, kind in STAT_ORDER:
        s = by_name.get(name)
        if not s:
            continue
        stats.append({"k": label, "v": _fmt_stat(s.get("value"), s.get("displayValue"), kind)})
        if len(stats) >= STAT_CAP:
            break

    return {
        "overall": total.get("summary", ""),
        "home": splits.get("home", ""),
        "road": splits.get("road", ""),
        "stats": stats,
    }


def _detail_schedule(team: dict) -> list[dict]:
    data = get_json(f"{_base(team)}/teams/{team['path']}/schedule")
    events = (data or {}).get("events", []) if isinstance(data, dict) else []
    parsed = [e for e in (_parse_event(ev, team["id"], team["name"]) for ev in events) if e]
    completed = [e for e in parsed if e["completed"]]
    upcoming = [e for e in parsed if not e["completed"]]
    # Last 6 results + next 6 games, in reading order.
    return completed[-6:] + upcoming[:6]


@cached(ttl_seconds=TTL_SPORTS_DETAIL)
def fetch_team_detail(key: str):
    if key == "wsl":
        return wsl.fetch_wsl()
    team = TEAMS.get(key)
    if not team:
        return None

    data = get_json(f"{_base(team)}/teams/{team['path']}")
    t = (data or {}).get("team", {}) if isinstance(data, dict) else {}

    rec = ""
    for item in (t.get("record") or {}).get("items", []):
        if item.get("type") == "total":
            rec = item.get("summary", "")
            break
    logo = ""
    logos = t.get("logos") or []
    if logos:
        logo = logos[0].get("href", "")

    return {
        "kind": "team",
        "key": key,
        "name": team["name"],
        "league": team["league_label"],
        "color": team["color"],
        "abbr": team["badge"],
        "record": rec,
        "standing": t.get("standingSummary", ""),
        "logo": logo,
        "news": _detail_news(team),
        "roster": _detail_roster(team),
        "stats": _detail_stats(t.get("record") or {}),
        "schedule": _detail_schedule(team),
    }
