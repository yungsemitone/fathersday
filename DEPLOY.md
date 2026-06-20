# Deploy — The Morning Desk on Fly.io (always-on)

One Fly app runs the whole thing: the FastAPI backend serves both the API and
the frontend, so Dad gets a single URL. `fly.toml` is set to keep one machine
running 24/7 (`auto_stop_machines = false`, `min_machines_running = 1`) so it's
instant every morning.

> You run these — they need *your* Fly login. I can't deploy for you.

## One-time setup

```bash
# 1. Install + log in (once on your machine)
brew install flyctl          # or: curl -L https://fly.io/install.sh | sh
fly auth login

# 2. From the project root (this folder), create the app.
#    Say NO if it offers to deploy immediately — set the env var first.
cd "/Users/adenjuda/Documents/Morning Desk"
fly launch --no-deploy
#   - pick a unique app name (e.g. dads-morning-desk) -> updates fly.toml
#   - region: lax (Los Angeles) is already set
#   - no Postgres, no Redis, no volumes needed
```

## Point Markets at the Stock Scraper backend

The Markets tab reads from your deployed Stock Scraper API. Set its URL (either
edit `STOCK_API_BASE` in `fly.toml [env]`, or set it as a config value):

```bash
fly secrets set STOCK_API_BASE=https://<your-stock-backend>.fly.dev
```

If you skip this, the app still deploys — Markets just shows sample data until
the URL is set. (Sports, Wine, News are live regardless.)

## Deploy

```bash
fly deploy
fly open            # opens the live URL
fly logs            # watch it boot / debug
```

Re-deploy any time with `fly deploy`. To change the curated wine list or WSL
data, edit the files and re-deploy.

## Hand-off

Print a little card with the URL for Dad. That's the gift. 🎁

---

### Notes
- **No secrets required.** `STOCK_API_BASE` is just a URL. There are no API keys
  in this app — ESPN, Open-Meteo, and the RSS feeds are all keyless.
- **CORS** isn't needed in prod because the backend serves the frontend from the
  same origin.
- **Cost:** one `shared-cpu-1x` / 512MB machine, always-on, is comfortably in
  Fly's small-app range. The image is light (no pandas/numpy).
- **Prod caveat:** if you ever want live K&L wine data, the scrape must run from
  a non-blocked IP — a cloud server like Fly will get `403`. The curated cellar
  is the reliable path; treat the live scraper as a bonus.
