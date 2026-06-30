/* =====================================================================
   THE MORNING DESK — frontend logic
   Fetches /api/dashboard on load; falls back to SAMPLE so the page always
   renders. Sports cards open in-depth detail views fetched on demand.
   ===================================================================== */

/* Leave "" when the backend serves this file (same origin). If hosted
   separately, set e.g. "https://your-desk.fly.dev". */
const API_BASE = "";

/* ---------------------------------------------------------------------
   SAMPLE DATA — fallback only; the backend returns the same shapes.
   --------------------------------------------------------------------- */
const SAMPLE = {
  markets: {
    listName: "Watchlist",
    watchlist: [
      { t: "AAPL", name: "Apple", px: 232.18, chg: +1.24 },
      { t: "MSFT", name: "Microsoft", px: 471.05, chg: +0.62 },
      { t: "NVDA", name: "Nvidia", px: 138.55, chg: +2.41 },
      { t: "JPM", name: "JPMorgan", px: 281.77, chg: +0.88 },
      { t: "XOM", name: "Exxon", px: 118.92, chg: -1.07 },
    ],
    indices: [
      { t: "S&P 500", px: 6128.40, chg: +0.43 },
      { t: "Nasdaq", px: 19840.2, chg: +0.71 },
      { t: "Dow", px: 43512.9, chg: +0.18 },
      { t: "WTI Crude", px: 71.84, chg: -0.92 },
      { t: "Gold", px: 2684.10, chg: +0.35 },
      { t: "10Y Yield", px: 4.21, chg: +0.03, unit: "%" },
    ],
    macro: [
      { k: "Fed funds", v: "3.63%", d: "held", dir: "neutral" },
      { k: "Core CPI", v: "3.1%", d: "-0.2 vs prior", dir: "down" },
      { k: "Unemployment", v: "4.3%", d: "unch", dir: "neutral" },
      { k: "10Y–2Y", v: "+0.34", d: "steepening", dir: "up" },
    ],
  },
  sports: [
    { key: "lakers", league: "NBA", team: "Lakers", color: "#FDB927", abbr: "LAL", line: "53–29 · 1st in Pacific", detail: "Next: vs OKC · May 12", res: "" },
    { key: "dodgers", league: "MLB", team: "Dodgers", color: "#005A9C", abbr: "LAD", line: "49–27 · 1st NL West", detail: "Next: vs BAL · Jun 21", res: "" },
    { key: "usc", league: "NCAA", team: "USC Trojans", color: "#990000", abbr: "USC", line: "Football · preseason", detail: "Season opens late August", res: "" },
    { key: "wsl", league: "WSL", team: "World Surf League", color: "#0AA1C4", abbr: "WSL", line: "Leaders: Colapinto · Picklum", detail: "Next: Corona Open J-Bay · Jul 9", res: "" },
  ],
  wine: [],   // no curated stand-in — wine is live-only (or an honest empty state)
  news: [
    { src: "Reuters", h: "Fed holds rates, signals patience on cuts", s: "The committee kept its benchmark steady, citing still-elevated services inflation and a labor market that has cooled only gradually.", url: "#" },
    { src: "Bloomberg", h: "Semiconductor shares slip on demand worries", s: "A pullback led by the chip complex weighed on the Nasdaq, with traders trimming exposure into quarter-end.", url: "#" },
    { src: "WSJ", h: "Oil eases as supply picture loosens", s: "Crude gave back gains as inventories built more than expected and the demand outlook softened into summer.", url: "#" },
  ],
};

/* ---------------------------------------------------------------------
   Helpers
   --------------------------------------------------------------------- */
const fmt = n => Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const sign = n => (n >= 0 ? "+" : "") + Number(n).toFixed(2);
const cls = n => (n >= 0 ? "up" : "down");
const esc = s => String(s == null ? "" : s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const discPct = w => Math.round((1 - w.bid / w.mkt) * 100);

function mdy(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  if (!d) return iso;
  return `${Number(m)}/${Number(d)}`;
}
function weekday(iso) {
  const dt = new Date(iso + "T12:00:00");
  return isNaN(dt) ? iso : dt.toLocaleDateString("en-US", { weekday: "short" });
}
function endsIn(iso) {
  const ms = new Date(iso) - new Date();
  if (isNaN(ms)) return "—";
  if (ms <= 0) return "Ended";
  const h = Math.floor(ms / 3.6e6), m = Math.floor((ms % 3.6e6) / 6e4);
  if (h >= 24) return Math.floor(h / 24) + "d " + (h % 24) + "h";
  if (h >= 1) return h + "h " + m + "m";
  return m + "m";
}

function quoteRow(o) {
  const unit = o.unit || "";
  const chg = (o.chg == null) ? "" : `<span class="chg ${cls(o.chg)}">${sign(o.chg)}%</span>`;
  return `<div class="row">
    <div><span class="tick">${esc(o.t)}</span>${o.name ? `<span class="name">${esc(o.name)}</span>` : ""}</div>
    <div style="display:flex; gap:14px; align-items:baseline;">
      <span class="num">${fmt(o.px)}${unit}</span>${chg}
    </div>
  </div>`;
}

let CARDS = SAMPLE.sports;   // current sports cards (for re-render)
let DASH_URL = "";           // the full Stock Dashboard URL (from backend config)
let ECON_URL = "";           // the Economic Calendar app URL (from backend config)
let WINE_FETCHED_AT = 0;     // unix ts of the last live wine fetch

function linkButton(id, url) {
  const btn = document.getElementById(id);
  if (!btn) return;
  if (url) { btn.href = url; btn.style.display = "inline-flex"; }
  else { btn.style.display = "none"; }
}
function renderTopButtons() {
  linkButton("dashboard-link", DASH_URL);
  linkButton("calendar-link", ECON_URL);
}

const sleep = ms => new Promise(r => setTimeout(r, ms));
function agoText(ts) {
  if (!ts) return "";
  const s = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (s < 60) return "just now";
  if (s < 3600) return Math.floor(s / 60) + "m ago";
  if (s < 86400) return Math.floor(s / 3600) + "h ago";
  return Math.floor(s / 86400) + "d ago";
}
function updateWineStamp() {
  const el = document.getElementById("wine-updated");
  if (el) el.textContent = WINE_FETCHED_AT ? "updated " + agoText(WINE_FETCHED_AT) : "";
}

/* Wine table: null = not fetched yet (checking), [] = nothing at a discount,
   [..] = real deals. No curated stand-in. */
function renderWine(wine) {
  updateWineStamp();
  const body = document.getElementById("wine-body");
  if (wine == null) {
    body.innerHTML = `<tr><td colspan="5" class="wine-msg">Checking K&amp;L auctions…</td></tr>`;
    return;
  }
  const wines = wine.filter(w => !w.endDT || endsIn(w.endDT) !== "Ended");
  if (!wines.length) {
    body.innerHTML = `<tr><td colspan="5" class="wine-msg">No 95+ wine from France, Italy, Spain or Australia is bidding below market right now. Hit refresh to check again.</td></tr>`;
    return;
  }
  body.innerHTML = wines.map(w => {
    const href = w.url || ("https://www.klwines.com/Products?searchText=" + encodeURIComponent(w.name));
    const chip = w.score ? `<span class="score-chip">${esc(w.score)} ${esc(w.critic || "WS")}</span>` : "";
    const count = w.count || 1;
    const cnt = (count > 1) ? ` <span style="color:var(--ink-3)">×${count}</span>` : "";
    const ends = w.endDT ? endsIn(w.endDT) : (w.left || "—");
    const mktLot = w.mkt ? Math.round(w.mkt * count) : null;   // lot value = per-btl × bottles
    const mktCell = mktLot
      ? `$${mktLot}${count > 1 ? `<div class="wine-sub">$${w.mkt}/btl</div>` : ""}`
      : "—";
    return `
      <tr>
        <td><a class="wine-name" href="${esc(href)}" target="_blank" rel="noopener">${esc(w.name)}</a>${chip}<div class="wine-sub">${esc(w.region)}</div></td>
        <td class="mono">$${w.bid}${cnt}</td>
        <td class="mono" style="color:var(--ink-3)">${mktCell}</td>
        <td class="mono" style="color:var(--ink-3)">${esc(ends)}</td>
        <td>${w.disc != null ? `<span class="disc">−${w.disc}%</span>` : '<span style="color:var(--ink-3)">—</span>'}</td>
      </tr>`;
  }).join("");
}

/* Manual refresh button: kick a re-scrape, then poll until fresh data lands. */
async function refreshWine() {
  const btn = document.getElementById("wine-refresh");
  const startAt = WINE_FETCHED_AT;
  if (btn) { btn.disabled = true; btn.textContent = "↻ Refreshing…"; }
  try { await fetch(API_BASE + "/api/wine/refresh", { method: "POST" }); } catch (e) { /* ignore */ }
  const deadline = Date.now() + 110000;     // give the scrape up to ~110s
  let got = false;
  while (Date.now() < deadline) {
    await sleep(4000);
    try {
      const j = await (await fetch(API_BASE + "/api/wine", { cache: "no-store" })).json();
      if ((j.fetchedAt || 0) > startAt) { WINE_FETCHED_AT = j.fetchedAt; renderWine(j.wine); got = true; break; }
    } catch (e) { /* keep polling */ }
  }
  if (!got && !WINE_FETCHED_AT) {
    const body = document.getElementById("wine-body");
    if (body) body.innerHTML = `<tr><td colspan="5" class="wine-msg">Couldn't reach K&amp;L just now — try Refresh again in a moment.</td></tr>`;
  }
  if (btn) { btn.disabled = false; btn.textContent = "↻ Refresh"; }
  updateWineStamp();
}

/* ---------------------------------------------------------------------
   Render the dashboard (home + markets + wine + news + sports grid)
   --------------------------------------------------------------------- */
function render(data) {
  const m = data.markets;
  document.getElementById("watchlist").innerHTML = m.watchlist.map(quoteRow).join("");
  document.getElementById("indices").innerHTML = m.indices.map(quoteRow).join("");
  document.getElementById("watchlist-label").textContent = m.listName ? `Watchlist · ${m.listName}` : "Watchlist";

  document.getElementById("macro-strip").innerHTML = m.macro.map(x => `
    <div class="stat">
      <div class="k">${esc(x.k)}</div>
      <div class="v">${esc(x.v)}</div>
      <div class="d" style="color:${x.dir === 'up' ? 'var(--up)' : x.dir === 'down' ? 'var(--down)' : 'var(--ink-3)'}">${esc(x.d)}</div>
    </div>`).join("");

  CARDS = data.sports;
  renderSportsGrid(data.sports);

  WINE_FETCHED_AT = data.wineFetchedAt || 0;
  renderWine(data.wine);

  document.getElementById("news-body").innerHTML = data.news.map(n => {
    const href = n.url && n.url !== "#" ? esc(n.url) : null;
    const inner = `
      <div class="src"><span>${esc(n.src)}</span>${href ? '<span class="arrow">Read →</span>' : ""}</div>
      <h4>${esc(n.h)}</h4>
      <p>${esc(n.s)}</p>`;
    return href
      ? `<a class="story" href="${href}" target="_blank" rel="noopener">${inner}</a>`
      : `<div class="story">${inner}</div>`;
  }).join("");

  // home dispatch summaries (derived)
  const topGainer = [...m.watchlist].sort((a, b) => (b.chg || 0) - (a.chg || 0))[0];
  const spx = m.indices.find(i => /S&P/i.test(i.t)) || m.indices[0];
  const tenY = m.indices.find(i => /10Y/i.test(i.t));
  document.getElementById("d-markets").textContent =
    `${spx.t} ${sign(spx.chg)}%. ${topGainer.t} leads your list, ${sign(topGainer.chg)}%.` + (tenY ? ` 10Y at ${fmt(tenY.px)}%.` : "");
  document.getElementById("d-sports").textContent =
    data.sports.map(s => `${s.team.replace(" Trojans", "").replace("World Surf League", "WSL")}: ${s.line}`).slice(0, 2).join(" · ") + ".";
  const deals = (data.wine || []).filter(w => w.disc != null && (!w.endDT || endsIn(w.endDT) !== "Ended"));
  if (deals.length) {
    const best = deals[0]; // backend puts the best discount first
    document.getElementById("d-wine").textContent =
      `${deals.length} K&L deal${deals.length > 1 ? "s" : ""} (95+, EU/Aus) below market. Best: ${best.name.split(" ").slice(0, 3).join(" ")}… −${best.disc}%.`;
  } else {
    document.getElementById("d-wine").textContent =
      "No 95+ deals from France, Italy, Spain or Australia below market right now.";
  }
  document.getElementById("d-news").textContent =
    `${data.news[0].h}. ${data.news.length} stories on the wire.`;
}

/* ---------------------------------------------------------------------
   Sports — home grid
   --------------------------------------------------------------------- */
function renderSportsGrid(cards) {
  document.getElementById("sports-grid").innerHTML = cards.map(s => `
    <div class="card link" tabindex="0" data-team="${esc(s.key)}">
      <div class="score">
        <div class="team">
          <div class="badge" style="background:${esc(s.color)}">${esc(s.abbr)}</div>
          <div>
            <div style="font-family:'Fraunces',serif; font-weight:600; font-size:17px;">${esc(s.team)}</div>
            <div class="result ${esc(s.res)}">${esc(s.line)}</div>
          </div>
        </div>
        <span class="chip">${esc(s.league)}</span>
      </div>
      <div class="meta">${esc(s.detail)}</div>
    </div>`).join("");

  document.querySelectorAll("#sports-grid [data-team]").forEach(c => {
    const go = () => openTeam(c.dataset.team);
    c.addEventListener("click", go);
    c.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
  });
}

/* ---------------------------------------------------------------------
   Sports — detail view
   --------------------------------------------------------------------- */
async function openTeam(key, subIndex = 0) {
  const home = document.getElementById("sports-home");
  const detail = document.getElementById("sports-detail");
  home.style.display = "none";
  detail.style.display = "block";
  detail.innerHTML = `<button class="backlink" onclick="closeTeam()">← All teams</button><p class="empty">Loading…</p>`;
  window.scrollTo({ top: 0, behavior: "smooth" });

  try {
    const path = key === "wsl" ? "/api/wsl" : "/api/sports/" + key;
    const res = await fetch(API_BASE + path, { cache: "no-store" });
    if (!res.ok) throw new Error("bad status " + res.status);
    const d = await res.json();
    detail.innerHTML = (d.kind === "wsl" || key === "wsl") ? renderWsl(d) : renderTeam(d);
    wireSubtabs(detail);
    wireRoster(detail);
    if (subIndex > 0) {
      const st = detail.querySelector(`.subtab[data-sub="${subIndex}"]`);
      if (st) st.click();
    }
  } catch (e) {
    const card = CARDS.find(c => c.key === key) || {};
    detail.innerHTML = `<button class="backlink" onclick="closeTeam()">← All teams</button>
      <div class="detail-head"><div class="badge" style="background:${esc(card.color || '#888')}">${esc(card.abbr || '?')}</div>
      <div><h2>${esc(card.team || key)}</h2><div class="rec">${esc(card.line || '')}</div></div></div>
      <p class="empty">Couldn't load live detail right now. ${esc(card.detail || '')}</p>`;
  }
}

function closeTeam() {
  document.getElementById("sports-detail").style.display = "none";
  document.getElementById("sports-home").style.display = "block";
  window.scrollTo({ top: 0, behavior: "smooth" });
}
window.closeTeam = closeTeam;
window.openTeam = openTeam;

function detailHead(d) {
  const rec = [d.record, d.standing].filter(Boolean).join(" · ");
  return `<button class="backlink" onclick="closeTeam()">← All teams</button>
    <div class="detail-head">
      <div class="badge" style="background:${esc(d.color)}">${esc(d.abbr || "")}</div>
      <div><h2>${esc(d.name)}</h2>${rec ? `<div class="rec">${esc(rec)}</div>` : ""}</div>
    </div>`;
}

function subNav(tabs) {
  const btns = tabs.map((t, i) =>
    `<button class="subtab" role="tab" data-sub="${i}" aria-selected="${i === 0}">${esc(t)}</button>`).join("");
  return `<nav class="subtabs" role="tablist">${btns}</nav>`;
}

function renderTeam(d) {
  // News
  const news = (d.news || []).length ? d.news.map(n => `
    <a class="story" href="${esc(n.url)}" target="_blank" rel="noopener">
      <div class="src"><span>ESPN</span><span class="arrow">Read →</span></div>
      <h4>${esc(n.h)}</h4>${n.s ? `<p>${esc(n.s)}</p>` : ""}
    </a>`).join("") : `<p class="empty">No recent stories.</p>`;

  // Roster
  const roster = (d.roster || []).length ? `<div class="roster-grid">` + d.roster.map(p => {
    const meta = [p.num ? "#" + p.num : "", p.pos, p.ht, p.age ? p.age + "y" : ""].filter(Boolean).join(" · ");
    const pic = p.headshot
      ? `<img src="${esc(p.headshot)}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">`
      : `<div class="badge" style="width:42px;height:42px;border-radius:50%;background:${esc(d.color)}">${esc(p.pos || "")}</div>`;
    const tappable = p.id != null;
    const nameCls = tappable ? "pname tap" : "pname";
    const attrs = tappable ? ` data-player="${esc(p.id)}" data-team="${esc(d.key)}"` : "";
    const arrow = tappable ? `<span class="go">→</span>` : "";
    return `<div class="player">${pic}<div><div class="${nameCls}"${attrs}>${esc(p.name)}</div><div class="pmeta">${esc(meta)}</div></div>${arrow}</div>`;
  }).join("") + `</div>` : `<p class="empty">Roster not posted yet.</p>`;

  // Stats
  const s = d.stats || {};
  const splits = [["Overall", s.overall], ["Home", s.home], ["Away", s.road]].filter(x => x[1]);
  const statCards = (s.stats || []).map(x => `<div class="stat"><div class="k">${esc(x.k)}</div><div class="v">${esc(x.v)}</div></div>`).join("");
  const splitCards = splits.map(x => `<div class="stat"><div class="k">${esc(x[0])}</div><div class="v">${esc(x[1])}</div></div>`).join("");
  const stats = (statCards || splitCards)
    ? `<div class="statgrid">${splitCards}${statCards}</div>`
    : `<p class="empty">Season stats appear once games are played.</p>`;

  // Schedule — full window, scrollable, with a divider + highlight at "next"
  let sched;
  if ((d.schedule || []).length) {
    let markedNext = false;
    const rows = d.schedule.map(g => {
      let pre = "", cls = "sched-row";
      if (!g.completed && !markedNext) { pre = `<div class="sched-divider">Upcoming</div>`; cls += " is-next"; markedNext = true; }
      const res = g.completed
        ? `<span class="sched-res ${g.res}">${esc(g.result || "")}</span>`
        : `<span class="sched-res"><span class="upcoming-tag">Upcoming</span></span>`;
      return pre + `<div class="${cls}">
        <span class="sched-when">${weekday(g.date)} ${mdy(g.date)}</span>
        <span class="sched-match"><span class="opp">${esc(g.where)} ${esc(g.opp_name || g.opp)}</span></span>
        ${res}</div>`;
    });
    sched = `<div class="scrolllist">${rows.join("")}</div>`;
  } else {
    sched = `<p class="empty">No games on the schedule yet — offseason.</p>`;
  }

  return detailHead(d) + subNav(["News", "Roster", "Stats", "Schedule"]) +
    `<div class="subpanel active">${news}</div>
     <div class="subpanel">${roster}</div>
     <div class="subpanel"><div class="card">${stats}</div></div>
     <div class="subpanel"><div class="card">${sched}</div></div>`;
}

function renderWsl(d) {
  const ne = d.nextEvent || {};
  const fc = ne.forecast || [];
  const head = `<button class="backlink" onclick="closeTeam()">← All teams</button>
    <div class="detail-head"><div class="badge" style="background:${esc(d.color || '#0AA1C4')}">WSL</div>
    <div><h2>${esc(d.name || "World Surf League")}</h2><div class="rec">Championship Tour 2026</div></div></div>`;

  // Forecast
  const swell = fc.length ? `<div class="swell-grid">` + fc.map(f => `
    <div class="swell-day">
      <div class="day">${weekday(f.date)}</div>
      <div class="ht">${f.ft != null ? f.ft : "—"}<small>ft</small></div>
      <div class="det">${f.period != null ? Math.round(f.period) + "s " : ""}${esc(f.dir || "")}</div>
    </div>`).join("") + `</div>` : `<p class="empty">Forecast unavailable right now.</p>`;
  const forecast = `<div class="card">
      <p class="eyebrow" style="margin:0 0 4px;">Next event</p>
      <h3 style="font-family:'Fraunces',serif;font-weight:600;font-size:20px;margin:0 0 2px;">${esc(ne.name || "")}</h3>
      <p class="section-note" style="margin:0 0 16px;">${esc(ne.spot || "")}${ne.country ? " · " + esc(ne.country) : ""} · ${esc(ne.start || "")}</p>
      ${swell}
      <p class="footnote" style="margin-top:16px;">Live wave forecast (daily max) from Open-Meteo's Marine API for the event location.</p>
    </div>`;

  // Schedule + winners — scrollable, divider + highlight at the next event
  let markedNext = false;
  const events = (d.events || []).map(ev => {
    let pre = "", cls = "sched-row";
    if (!ev.completed && !markedNext) { pre = `<div class="sched-divider">Upcoming</div>`; cls += " is-next"; markedNext = true; }
    const win = ev.completed
      ? `<span class="sched-res" style="text-align:right;min-width:auto"><span style="color:var(--gold)">🏆 ${esc(ev.men || "")}${ev.women ? " · " + esc(ev.women) : ""}</span></span>`
      : `<span class="sched-res"><span class="upcoming-tag">Upcoming</span></span>`;
    return pre + `<div class="${cls}">
      <span class="sched-when">${esc(mdy(ev.start))}</span>
      <span class="sched-match"><span class="opp">${esc(ev.name)}</span><div class="meta" style="margin-top:2px">${esc(ev.spot)} · ${esc(ev.country)}</div></span>
      ${win}</div>`;
  }).join("");
  const schedule = `<div class="card"><div class="scrolllist">${events}</div></div>`;

  // Rankings
  const rk = d.rankings || { men: [], women: [] };
  const rankList = arr => arr.map(r => `
    <div class="rank-row">
      <span class="rank-no">${r.rank}</span>
      <span class="rank-name">${esc(r.name)} <span class="rank-ctry">${esc(r.country)}</span></span>
      <span class="rank-pts">${Number(r.points).toLocaleString()}</span>
    </div>`).join("");
  const rankings = `<div class="cols-2">
      <div class="card"><p class="eyebrow" style="margin:0 0 10px;">Men's CT</p>${rankList(rk.men || [])}</div>
      <div class="card"><p class="eyebrow" style="margin:0 0 10px;">Women's CT</p>${rankList(rk.women || [])}</div>
    </div>`;

  return head + subNav(["Forecast", "Schedule", "Rankings"]) +
    `<div class="subpanel active">${forecast}</div>
     <div class="subpanel">${schedule}</div>
     <div class="subpanel">${rankings}</div>`;
}

function wireSubtabs(root) {
  const tabs = [...root.querySelectorAll(".subtab")];
  const panels = [...root.querySelectorAll(".subpanel")];
  tabs.forEach(t => t.addEventListener("click", () => {
    tabs.forEach(x => x.setAttribute("aria-selected", String(x === t)));
    panels.forEach((p, i) => p.classList.toggle("active", i === Number(t.dataset.sub)));
    // When a scrollable schedule opens, jump it to the next game/event.
    const active = panels[Number(t.dataset.sub)];
    const list = active && active.querySelector(".scrolllist");
    const marker = list && (list.querySelector(".is-next") || list.querySelector(".sched-divider"));
    if (list && marker) list.scrollTop = Math.max(0, marker.offsetTop - 54);
  }));
}

/* Roster names -> player page */
function wireRoster(root) {
  root.querySelectorAll("[data-player]").forEach(el =>
    el.addEventListener("click", () => openPlayer(el.dataset.team, el.dataset.player)));
}

async function openPlayer(teamKey, playerId) {
  const detail = document.getElementById("sports-detail");
  const back = `<button class="backlink" onclick="openTeam('${teamKey}', 1)">← Back to roster</button>`;
  detail.innerHTML = back + `<p class="empty">Loading…</p>`;
  window.scrollTo({ top: 0, behavior: "smooth" });
  try {
    const res = await fetch(API_BASE + `/api/sports/${teamKey}/player/${playerId}`, { cache: "no-store" });
    if (!res.ok) throw new Error("bad status " + res.status);
    detail.innerHTML = renderPlayer(await res.json());
  } catch (e) {
    detail.innerHTML = back + `<p class="empty">Couldn't load this player right now.</p>`;
  }
}
window.openPlayer = openPlayer;

function renderPlayer(d) {
  const pic = d.headshot
    ? `<img src="${esc(d.headshot)}" alt="" onerror="this.style.visibility='hidden'">`
    : `<div class="badge" style="width:72px;height:72px;border-radius:50%;background:${esc(d.color)}">${esc(d.pos || "")}</div>`;
  const num = d.num ? "#" + String(d.num).replace(/^#/, "") : "";
  const sub = [num, d.pos, d.teamName].filter(Boolean).join(" · ");
  const bio = (d.bio || []).map(b => `<div class="stat"><div class="k">${esc(b.k)}</div><div class="v">${esc(b.v)}</div></div>`).join("");
  const season = (d.season && (d.season.stats || []).length)
    ? `<p class="eyebrow" style="margin:22px 0 10px;">${esc(d.season.label)} · per game</p>
       <div class="statgrid">` + d.season.stats.map(s => `<div class="stat"><div class="k">${esc(s.k)}</div><div class="v">${esc(s.v)}</div></div>`).join("") + `</div>`
    : `<p class="empty">No season stats yet — offseason, or a role without box-score stats.</p>`;
  const link = d.link ? `<a class="espn-link" href="${esc(d.link)}" target="_blank" rel="noopener">Full profile on ESPN →</a>` : "";
  return `<button class="backlink" onclick="openTeam('${esc(d.teamKey)}', 1)">← Back to roster</button>
    <div class="player-head">${pic}<div><h2>${esc(d.name)}</h2><div class="psub">${esc(sub)}</div></div></div>
    <div class="card">
      <p class="eyebrow" style="margin:0 0 12px;">Player info</p>
      <div class="bio-grid">${bio}</div>
      ${season}${link}
    </div>`;
}

/* ---------------------------------------------------------------------
   Boot: try live, fall back to sample
   --------------------------------------------------------------------- */
async function boot() {
  let data = SAMPLE, live = false;
  try {
    const res = await fetch(API_BASE + "/api/dashboard", { cache: "no-store" });
    if (res.ok) {
      const j = await res.json();
      const mk = j.markets || {};
      data = {
        markets: {
          listName: mk.listName || SAMPLE.markets.listName,
          watchlist: mk.watchlist || SAMPLE.markets.watchlist,
          indices: mk.indices || SAMPLE.markets.indices,
          macro: mk.macro || SAMPLE.markets.macro,
        },
        sports: j.sports || SAMPLE.sports,
        wine: ("wine" in j) ? j.wine : SAMPLE.wine,  // pass through null/[]: no curated stand-in
        wineFetchedAt: j.wineFetchedAt || 0,
        news: j.news || SAMPLE.news,
      };
      DASH_URL = j.dashboardUrl || "";
      ECON_URL = j.econCalendarUrl || "";
      live = !!(j.markets || j.sports || j.wine || j.news);
    }
  } catch (e) { /* backend not up — keep sample */ }

  render(data);
  renderTopButtons();
  document.getElementById("data-status").textContent = live
    ? "Live data connected."
    : "Showing sample data — start the backend to go live. See README.";

  // Cold start: the live wine fetch warms in the background — poll it in.
  if (data.wine == null) refreshWine();
}

/* ---- clock + greeting ---- */
function refreshTime() {
  const now = new Date();
  const h = now.getHours();
  const greet = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  document.getElementById("greet").textContent = greet + ", Dad";
  const dateStr = now.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
  const timeStr = now.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  document.getElementById("asof").textContent = "as of " + timeStr;
  document.getElementById("hero-stamp").textContent = dateStr + " · " + timeStr + " PT";
  updateWineStamp();   // keep the "updated Xm ago" label ticking
}

/* ---- tabs ---- */
const tabs = [...document.querySelectorAll(".tab")];
const panels = [...document.querySelectorAll(".panel")];
function show(id) {
  tabs.forEach(t => t.setAttribute("aria-selected", String(t.dataset.tab === id)));
  panels.forEach(p => p.classList.toggle("active", p.id === id));
  if (id === "sports") closeTeam();   // always land on the team grid
  window.scrollTo({ top: 0, behavior: "smooth" });
}
tabs.forEach(t => t.addEventListener("click", () => show(t.dataset.tab)));
const wineRefreshBtn = document.getElementById("wine-refresh");
if (wineRefreshBtn) wineRefreshBtn.addEventListener("click", refreshWine);
document.querySelectorAll("[data-jump]").forEach(c => {
  const go = () => show(c.dataset.jump);
  c.addEventListener("click", go);
  c.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
});

refreshTime();
setInterval(refreshTime, 30000);
boot();
