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

`fly.toml` already sets `STOCK_API_BASE = https://stockdashboard.fly.dev` (your
live backend), so you usually don't need the command above. It also has a
`STOCK_DASHBOARD_URL` placeholder — set that to your **Vercel dashboard URL** so
the Markets tab's "Open the full Stock Dashboard" button works:

```bash
fly secrets set STOCK_DASHBOARD_URL=https://<your-dashboard>.vercel.app
```

## Live wine (K&L auctions via Scrapfly)

The wine section reads **live K&L auction lots** and enriches each with a critic
score + market price from Wine-Searcher, through the Scrapfly unblocker (K&L and
Wine-Searcher both block plain servers via Cloudflare).

```bash
# 1. The Scrapfly key is a secret:
fly secrets set SCRAPER_API_KEY=scp-live-xxxxxxxx   # SCRAPER_PROVIDER=scrapfly is in fly.toml

# 2. A small volume persists the score cache so scores aren't re-bought each deploy
#    (create it once, same region as the app):
fly volumes create data --size 1 --region lax -a dad-dashboard
```

Credit budgeting (free Scrapfly tier = 1,000 credits/month, ~6 credits/lookup):
`fly.toml`/env knobs `WINE_SCORE_PER_REFRESH` (default 12) and
`WINE_SCORE_BUDGET_MONTH` (default 100) cap spend so it never overruns. Every lot
still shows live; critic scores fill in within budget and are cached forever.
To score **every** lot on every refresh, bump those and move to a paid Scrapfly
tier (~$30/mo = 200k credits). Without a key, the section uses the curated cellar.

## Deploy

```bash
fly deploy
fly open            # opens the live URL
fly logs            # watch it boot / debug
```

Re-deploy any time with `fly deploy`. To change the curated wine list or WSL
data, edit the files and re-deploy.

## Auto-deploy (push to deploy — no manual `fly deploy`)

`.github/workflows/fly-deploy.yml` deploys on every push to `main`. One-time setup:

```bash
# 1. Create a Fly deploy token scoped to this app:
fly tokens create deploy -a dad-dashboard
```

```
# 2. Add it to GitHub:  repo  ->  Settings  ->  Secrets and variables  ->  Actions
#    ->  New repository secret  ->  name: FLY_API_TOKEN, value: (the token, incl. the "FlyV1 ..." prefix)
```

After that, `git push` deploys automatically (watch it in the repo's **Actions** tab).
The volume + secrets persist across deploys, so you set those once.

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
