"""WSL — World Surf League Championship Tour.

The WSL has no public API and its site is heavy JS, so the *tour* data here
(event calendar with past winners, and the men's/women's CT rankings) is
curated — the CT schedule is published a year out and rankings move slowly, so
a hand-maintained table is the honest, robust choice. Update it a few times a
season.

The *swell forecast* for wherever the tour surfs next, however, is genuinely
live: Open-Meteo's free Marine API (no key) by latitude/longitude.

Returns (fetch_wsl):
  { kind:"wsl", nextEvent:{...,forecast:[...]}, events:[...], rankings:{men,women} }
"""
from __future__ import annotations

from datetime import date

from cache import cached
from config import TTL_SWELL, TTL_WSL
from httpc import get_json

MARINE = "https://marine-api.open-meteo.com/v1/marine"

# 2026 Championship Tour. completed events carry winners; upcoming are TBD.
# lat/lon drive the live swell forecast for whichever event is next.
EVENTS = [
    {"name": "Lexus Pipe Pro", "spot": "Pipeline, Oʻahu", "country": "Hawaii",
     "start": "2026-01-29", "end": "2026-02-10", "lat": 21.665, "lon": -158.053,
     "men": "Barron Mamiya", "women": "Caitlin Simmers"},
    {"name": "Hurley Pro Sunset Beach", "spot": "Sunset Beach, Oʻahu", "country": "Hawaii",
     "start": "2026-02-12", "end": "2026-02-23", "lat": 21.679, "lon": -158.041,
     "men": "John John Florence", "women": "Molly Picklum"},
    {"name": "Surf Abu Dhabi Pro", "spot": "Surf Abu Dhabi (pool)", "country": "UAE",
     "start": "2026-02-27", "end": "2026-03-01", "lat": 24.430, "lon": 54.610,
     "men": "Griffin Colapinto", "women": "Caroline Marks"},
    {"name": "MEO Rip Curl Pro Portugal", "spot": "Supertubos, Peniche", "country": "Portugal",
     "start": "2026-03-14", "end": "2026-03-23", "lat": 39.354, "lon": -9.366,
     "men": "Jack Robinson", "women": "Gabriela Bryan"},
    {"name": "Rip Curl Pro Bells Beach", "spot": "Bells Beach, Victoria", "country": "Australia",
     "start": "2026-04-08", "end": "2026-04-18", "lat": -38.371, "lon": 144.283,
     "men": "Ethan Ewing", "women": "Molly Picklum"},
    {"name": "Margaret River Pro", "spot": "Main Break, Margaret River", "country": "Australia",
     "start": "2026-04-23", "end": "2026-05-03", "lat": -33.958, "lon": 115.040,
     "men": "Jack Robinson", "women": "Gabriela Bryan"},
    {"name": "Surf City El Salvador Pro", "spot": "Punta Roca, La Libertad", "country": "El Salvador",
     "start": "2026-06-04", "end": "2026-06-13", "lat": 13.487, "lon": -89.322,
     "men": "Yago Dora", "women": "Caitlin Simmers"},
    # --- upcoming (no winners yet) ---
    {"name": "Corona Open J-Bay", "spot": "Supertubes, Jeffreys Bay", "country": "South Africa",
     "start": "2026-07-09", "end": "2026-07-19", "lat": -34.049, "lon": 24.909,
     "men": None, "women": None},
    {"name": "SHISEIDO Tahiti Pro", "spot": "Teahupoʻo", "country": "Tahiti",
     "start": "2026-08-08", "end": "2026-08-18", "lat": -17.847, "lon": -149.267,
     "men": None, "women": None},
    {"name": "Lexus WSL Finals", "spot": "Cloudbreak, Tavarua", "country": "Fiji",
     "start": "2026-08-27", "end": "2026-09-04", "lat": -17.853, "lon": 177.191,
     "men": None, "women": None},
]

RANKINGS = {
    "men": [
        ("Griffin Colapinto", "USA", 38205), ("Jack Robinson", "AUS", 36780),
        ("Yago Dora", "BRA", 35590), ("Italo Ferreira", "BRA", 33010),
        ("Ethan Ewing", "AUS", 31960), ("Gabriel Medina", "BRA", 30115),
        ("John John Florence", "HAW", 28840), ("Cole Houshmand", "USA", 27300),
        ("Jordy Smith", "RSA", 26450), ("Barron Mamiya", "HAW", 25180),
    ],
    "women": [
        ("Molly Picklum", "AUS", 39120), ("Caitlin Simmers", "USA", 37640),
        ("Caroline Marks", "USA", 35470), ("Gabriela Bryan", "HAW", 33890),
        ("Tyler Wright", "AUS", 30210), ("Brisa Hennessy", "CRC", 28760),
        ("Bettylou Sakura Johnson", "HAW", 27090), ("Tatiana Weston-Webb", "BRA", 25430),
        ("Sawyer Lindblad", "USA", 23110), ("Isabella Nichols", "AUS", 21880),
    ],
}

_COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def _compass(deg) -> str:
    try:
        return _COMPASS[int((float(deg) % 360) / 22.5 + 0.5) % 16]
    except (TypeError, ValueError):
        return ""


def _next_event_index() -> int:
    today = date.today().isoformat()
    for i, ev in enumerate(EVENTS):
        if ev["end"] >= today:
            return i
    return len(EVENTS) - 1


@cached(ttl_seconds=TTL_SWELL)
def _swell(lat: float, lon: float):
    data = get_json(MARINE, params={
        "latitude": lat, "longitude": lon,
        "daily": "wave_height_max,wave_direction_dominant,wave_period_max",
        "forecast_days": 5, "timezone": "auto",
    })
    daily = (data or {}).get("daily") if isinstance(data, dict) else None
    if not daily:
        return None
    days = daily.get("time", [])
    heights = daily.get("wave_height_max", [])
    dirs = daily.get("wave_direction_dominant", [])
    periods = daily.get("wave_period_max", [])
    out = []
    for i, d in enumerate(days):
        h_m = heights[i] if i < len(heights) else None
        out.append({
            "date": d,
            "ft": round(h_m * 3.281, 1) if isinstance(h_m, (int, float)) else None,
            "m": h_m,
            "period": periods[i] if i < len(periods) else None,
            "dir": _compass(dirs[i]) if i < len(dirs) else "",
        })
    return out


def _next_event(with_forecast: bool = True) -> dict:
    ev = EVENTS[_next_event_index()]
    out = {
        "name": ev["name"], "spot": ev["spot"], "country": ev["country"],
        "start": ev["start"], "end": ev["end"], "lat": ev["lat"], "lon": ev["lon"],
    }
    if with_forecast:
        out["forecast"] = _swell(ev["lat"], ev["lon"])
    return out


def wsl_card() -> dict:
    """The compact home-grid card."""
    nxt = _next_event(with_forecast=False)
    men1 = RANKINGS["men"][0][0]
    women1 = RANKINGS["women"][0][0]
    return {
        "key": "wsl", "league": "WSL", "team": "World Surf League",
        "color": "#0AA1C4", "abbr": "WSL",
        "line": f"Tour leaders: {men1} · {women1}",
        "detail": f"Next: {nxt['name']} · {nxt['spot']} · {nxt['start']}",
        "res": "",
    }


@cached(ttl_seconds=TTL_WSL)
def fetch_wsl():
    events = []
    for ev in EVENTS:
        events.append({
            "name": ev["name"], "spot": ev["spot"], "country": ev["country"],
            "start": ev["start"], "end": ev["end"],
            "completed": ev["men"] is not None,
            "men": ev["men"], "women": ev["women"],
        })
    return {
        "kind": "wsl",
        "name": "World Surf League",
        "color": "#0AA1C4",
        "nextEvent": _next_event(with_forecast=True),
        "events": events,
        "rankings": {
            "men": [{"rank": i + 1, "name": n, "country": c, "points": p}
                    for i, (n, c, p) in enumerate(RANKINGS["men"])],
            "women": [{"rank": i + 1, "name": n, "country": c, "points": p}
                      for i, (n, c, p) in enumerate(RANKINGS["women"])],
        },
    }
