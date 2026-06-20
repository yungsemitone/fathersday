"""The Morning Desk — backend entrypoint.

Run locally:
    cd backend
    pip install -r requirements.txt
    cp .env.example .env          # then set STOCK_API_BASE
    uvicorn main:app --reload --port 8001
Then open http://localhost:8001

Markets are pulled from Dad's Stock Scraper app (STOCK_API_BASE); the other
sections fetch live where they can and fall back to curated data otherwise, so
the page is always presentable.
"""
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from config import CORS_ORIGINS, STOCK_DASHBOARD_URL
from sources.markets import fetch_markets
from sources.news import fetch_news
from sources.sports import TEAMS, fetch_player_detail, fetch_sports, fetch_team_detail
from sources.wine import fetch_wine
from sources.wsl import fetch_wsl

app = FastAPI(title="The Morning Desk")

_origins = ["*"] if CORS_ORIGINS.strip() == "*" else [o.strip() for o in CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
VALID_TEAMS = set(TEAMS) | {"wsl"}


def _safe(fn, *args):
    try:
        return fn(*args)
    except Exception as e:  # noqa: BLE001 - one bad section shouldn't 500 the page
        print(f"[{getattr(fn, '__name__', fn)}] failed:", e)
        return None


@app.get("/api/dashboard")
def dashboard():
    """Everything the home + section tabs need, in one cached call."""
    return JSONResponse({
        "markets": _safe(fetch_markets),
        "sports": _safe(fetch_sports),
        "wine": _safe(fetch_wine),
        "news": _safe(fetch_news),
        "dashboardUrl": STOCK_DASHBOARD_URL,
    })


@app.get("/api/markets")
def markets():
    return JSONResponse(_safe(fetch_markets) or {})


@app.get("/api/news")
def news():
    return JSONResponse({"news": _safe(fetch_news)})


@app.get("/api/sports")
def sports():
    return JSONResponse({"cards": _safe(fetch_sports)})


@app.get("/api/sports/{team}")
def sports_detail(team: str):
    if team not in VALID_TEAMS:
        raise HTTPException(404, f"Unknown team '{team}'")
    data = _safe(fetch_team_detail, team)
    if data is None:
        raise HTTPException(502, "Upstream sports data unavailable")
    return JSONResponse(data)


@app.get("/api/sports/{team}/player/{player_id}")
def player_detail(team: str, player_id: str):
    if team not in TEAMS:
        raise HTTPException(404, f"Unknown team '{team}'")
    data = _safe(fetch_player_detail, team, player_id)
    if data is None:
        raise HTTPException(502, "Player data unavailable")
    return JSONResponse(data)


@app.get("/api/wsl")
def wsl():
    return JSONResponse(_safe(fetch_wsl) or {})


@app.get("/api/wine")
def wine():
    return JSONResponse({"wine": _safe(fetch_wine)})


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve the frontend (index.html at /, plus app.js and any future assets) from
# the same origin. Mounted last so it never shadows the /api routes above.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")
