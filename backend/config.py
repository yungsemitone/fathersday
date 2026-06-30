"""Configuration for The Morning Desk.

Everything is environment-driven (a local .env in dev). No secrets are needed
to run — every section degrades gracefully to sample/curated data.

The Markets section is special: instead of re-fetching quotes, it pulls from
your *Stock Scraper* app's API (so Dad's watchlists flow straight in). Point
STOCK_API_BASE at that backend — http://localhost:8000 in dev, or the deployed
Fly URL in production.
"""
import os

from dotenv import load_dotenv

load_dotenv()

# --- Markets: where the Stock Scraper backend lives -------------------------
# Local dev default; override with the deployed URL in production.
STOCK_API_BASE = os.getenv("STOCK_API_BASE", "http://localhost:8000").rstrip("/")

# Which of Dad's watchlists to feature on the Markets tab. Empty = first list.
FEATURED_WATCHLIST = os.getenv("FEATURED_WATCHLIST", "")

# The full Stock Dashboard UI (the Vercel frontend Dad uses). When set, the
# Markets tab shows an "Open the full dashboard" button linking here. This is
# the *frontend* URL, not STOCK_API_BASE (which is the backend API).
STOCK_DASHBOARD_URL = os.getenv("STOCK_DASHBOARD_URL", "")

# The Economic Calendar app — the Markets tab links to it next to the dashboard
# button. Defaults to the deployed Fly app; override if it moves.
ECON_CALENDAR_URL = os.getenv("ECON_CALENDAR_URL", "https://economic-calendar.fly.dev")

# --- Wine: K&L auctions sit behind Cloudflare, so fetch them through an
# unblocker service (scraperapi | scrapingbee | scrapfly | zenrows). Without a
# key, the wine section uses the curated cellar.
SCRAPER_PROVIDER = os.getenv("SCRAPER_PROVIDER", "brightdata")
SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY", "")
# Bright Data Web Unlocker (pay-as-you-go ~$1.5/1k requests): set the API token
# and the Web Unlocker zone name. Used when SCRAPER_PROVIDER=brightdata.
BRIGHTDATA_API_TOKEN = os.getenv("BRIGHTDATA_API_TOKEN", "")
BRIGHTDATA_ZONE = os.getenv("BRIGHTDATA_ZONE", "")
KL_AUCTION_URL = os.getenv("KL_AUCTION_URL", "https://shop.klwines.com/products/auctions")

# Critic scores + market price come from Wine-Searcher (via the unblocker), are
# cached permanently per wine, and are budget-capped so the free Scrapfly tier
# (1,000 credits/mo) is never overrun. Each lookup costs ~6 credits.
WINE_SCORE_PER_REFRESH = int(os.getenv("WINE_SCORE_PER_REFRESH", "10"))
WINE_SCORE_BUDGET_MONTH = int(os.getenv("WINE_SCORE_BUDGET_MONTH", "250"))

# What qualifies as a wine "deal" to surface (Dad's rules):
WINE_MIN_SCORE = int(os.getenv("WINE_MIN_SCORE", "95"))            # critic 95+
WINE_MIN_DISCOUNT = float(os.getenv("WINE_MIN_DISCOUNT", "0.05"))  # ≥5% below market
WINE_COUNTRIES = [c.strip().lower() for c in
                  os.getenv("WINE_COUNTRIES", "France,Italy,Spain,Australia").split(",")]

# --- CORS (only needed if the frontend is hosted on another origin) ---------
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

# --- Optional: where to write any persisted data (Fly volume in prod) -------
DATA_DIR = os.getenv("DATA_DIR", "")

# --- Cache TTLs (seconds) ---------------------------------------------------
TTL_MARKETS = 120     # markets move; keep it fresh-ish
TTL_NEWS = 600        # headlines every 10 min
TTL_SPORTS = 600      # scores/rosters change slowly intraday
TTL_SPORTS_DETAIL = 900
TTL_WSL = 3600        # tour data is stable; swell refetched within
TTL_SWELL = 3600      # marine forecast hourly is plenty
TTL_WINE = 10800      # 3h: frequent enough that Dad won't miss auctions, still cheap
