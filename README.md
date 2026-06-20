# The Morning Desk

A personal morning dashboard — markets, sports, wine, and news on one page,
built as a Father's Day gift. Warm newspaper look; one URL; always on.

```
Home      hero greeting + a dispatch summary of each section
Markets   Dad's watchlist (from his Stock Scraper app) + the tape + macro
Sports    Lakers · Dodgers · USC · WSL — tap any one for a full page
Wine      bottles mispriced at K&L auction, filtered to 90+ critic scores
News      market-moving headlines that link out to the source
```

## How it's wired

One FastAPI backend serves both the JSON API and the static frontend (so it's a
single app / single URL). Each section fetches live where it can and falls back
to curated/sample data otherwise, so the page is always presentable.

| Section | Source | Live? |
|---|---|---|
| **Markets** | Dad's **Stock Scraper** app API (`STOCK_API_BASE`) — his real watchlists, the tape, FRED macro | ✅ when that backend is reachable |
| **Sports** (Lakers/Dodgers/USC) | ESPN public JSON — record, news, roster, season stats, schedule | ✅ keyless |
| **Sports** (WSL) | Curated 2026 CT schedule + winners + men's/women's rankings, with a **live** Open-Meteo swell forecast for the next event | ✅ swell is live |
| **Wine** | K&L auction scrape *(blocked by their bot protection)* → curated cellar of 90+ wines with the same mispricing/rating logic | curated; scraper wired |
| **News** | Financial RSS (WSJ Markets, Yahoo Finance, CNBC, MarketWatch), advice-column noise filtered out | ✅ keyless |

### Markets ↔ Stock Scraper
The Markets tab does **not** re-fetch quotes. It calls the Stock Scraper backend
(`/api/watchlists`, `/api/overview`, `/api/economy`) so whatever Dad curates
there flows straight in. Point `STOCK_API_BASE` at it (local in dev, the
deployed URL in prod). If it's unreachable, Markets shows sample data.

### A note on the hard ones
- **K&L (wine):** `klwines.com` returns `403` to automated requests (bot
  protection) — including from cloud servers. So the live scraper in
  `sources/wine.py` is wired and ready, but the section runs off
  `backend/data/wine_cellar.csv`: real wines, real critic scores (≥90),
  realistic K&L price points. Edit that CSV to track the bottles Dad buys.
- **WSL:** no public API and a heavy JS site, so the tour calendar/winners and
  rankings are curated in `sources/wsl.py` (update a few times a season). The
  swell forecast is genuinely live.

## Run it locally

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # set STOCK_API_BASE (default http://localhost:8000)
uvicorn main:app --reload --port 8001
# open http://localhost:8001
```

Run the Stock Scraper backend on :8000 too and the Markets tab goes live with
Dad's watchlists. Without it, Markets shows sample data — everything else is
still live.

## Project layout

```
backend/
  main.py            FastAPI: /api/dashboard + per-section routes; serves frontend
  config.py          env (STOCK_API_BASE, cache TTLs)
  cache.py           tiny per-args TTL cache
  httpc.py           shared httpx client (browser UA, fails soft)
  data/wine_cellar.csv   curated 90+ wines
  sources/
    markets.py       pulls from the Stock Scraper API
    news.py          financial RSS + advice-column filter
    sports.py        ESPN cards + per-team detail (news/roster/stats/schedule)
    wsl.py           CT schedule/rankings + live Open-Meteo swell
    wine.py          K&L scrape (best-effort) + curated cellar + 90+ filter
frontend/
  index.html         the dashboard shell + styles
  app.js             rendering + sports detail views (no build step)
Dockerfile, fly.toml DEPLOY.md   one always-on Fly app
```

Deploy: see [DEPLOY.md](DEPLOY.md). One Fly app, always-on, near Los Angeles.
