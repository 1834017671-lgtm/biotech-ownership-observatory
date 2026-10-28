# Biotech Ownership Observatory

A private, static research dashboard built around 50 US-based healthcare specialist managers selected by reported 13F value from a researched pool of 60. The default candidate set is the union of each manager's five largest eligible company equity positions. All selected managers' holdings, including smaller positions, contribute to ownership and concentration metrics.

## Open on phone or desktop

Published site: https://1834017671-lgtm.github.io/biotech-ownership-observatory/

The dashboard is built for phone browsers as well as desktop: tabs and tables scroll sideways, the company column stays pinned, and filters use full-width touch-friendly controls.

## Run locally

Requires Python 3 and curl; no Python packages or paid API keys are required. Build the browser snapshot first if `dist/data.js` is missing: `python3 scripts/prepare.py`.

```sh
python3 -m http.server 8765 --bind 0.0.0.0 --directory dist
```

On this machine open http://127.0.0.1:8765/ . On a phone on the same Wi‑Fi, open `http://<your-computer-ip>:8765/` (find the IP with `hostname -I` or System Settings → Network). Binding `0.0.0.0` allows LAN access; use `--bind 127.0.0.1` if you only want local-machine access. The static site also contains a downloadable JSON snapshot and a CSV export of the current screen.

## Healthcare proxy baskets

The **Healthcare proxies** tab builds equal-weight equity baskets (no broad ETFs such as XLV/XBI as constituents):

- US Pharma
- EU Pharma (liquid US ADRs/ORDs)
- Life Science Tools (instruments, reagents, sequencing, labs)
- SMID Biotech (XBI-style liquid biotech names reconstructed by ticker, 30+ names)
- CXO / CDMO / CRO (outsourced development and manufacturing)
- Hospitals / providers / insurance

A name can sit in more than one basket when the business mix is genuinely dual (for example Thermo Fisher in tools and CXO). Constituents and inclusion rules live in `data/healthcare-proxies.json`. `scripts/proxies.py` averages completed daily member returns for 1D / 5D / 1M / 3M / YTD and a relative-return rotation matrix. Edit the JSON to change membership; the next `prepare.py` / daily refresh rebuilds the stats.

## Public website and daily updates

The site is published with GitHub Pages by `.github/workflows/daily.yml`. The open page checks `version.json` every second (paused while the tab is hidden) and loads new data in place, keeping the selected tab, filters and open company profile. Source data does not change every second: prices are refreshed once per US trading day and 13F holdings change quarterly.

The workflow runs at 03:00 UTC Tuesday–Saturday, on manual dispatch, and on every push to `main` (push runs only rebuild the site). A scheduled run calls `scripts/daily.py`, which:

- checks SEC EDGAR for new 13F-HR and 13F-HR/A filings by each tracked manager and re-collects only managers with new filings (amendments are listed for human review);
- refreshes prices and statistics for every candidate, keeping the last good observation, marked `carriedForward`, when a vendor request fails;
- refreshes broader institutional holders when a new quarter appears, or when `REFRESH_HOLDERS=1`;
- appends a run entry to `data/refresh-log.json`, rebuilds `dist/`, and commits the updated `data/` files.

One-time setup:

1. Create a public GitHub repository and push this folder to `main`.
2. Settings → Pages → Source: **GitHub Actions**.
3. Settings → Secrets and variables → Actions → new secret `SEC_USER_AGENT`, for example `Vanessa biotech research you@example.com`. SEC requires automated clients to identify themselves.
4. Actions → "Daily refresh and publish" → Run workflow.

Run the same job locally with `SEC_USER_AGENT="..." python3 scripts/daily.py`. Pacing is set with `COLLECT_DELAY`, `MARKET_DELAY`, `MARKET_WORKERS` and `HOLDERS_DELAY`.

Prices and statistics come from Yahoo Finance and Stock Analysis. Their terms of use may restrict republishing on a public website.

## Full refresh

```sh
python3 scripts/refresh.py
```

This archives the previous normalized datasets, checks the fund filing indexes, retains accession-specific raw data, attempts original SEC XML reconciliation, refreshes market data and broader institutional holders, and rebuilds the browser snapshot. It restores the previous normalized data if the run fails or fund coverage is incomplete. New-holdings amendments need human reconciliation before publication; the effective-quarter index supplies restatement selection. Public sources can block or rate-limit automated requests; failures are retained, never replaced with fabricated data.

Market and broader-holder data are collected for each fund's top 50 company equities by default (`CANDIDATE_DEPTH=50`, about 480 companies). Set a smaller value, e.g. `CANDIDATE_DEPTH=10 python3 scripts/refresh.py`, for a faster run. The dashboard's Data quality tab lists candidates still missing market data.

The hosted site does not refresh itself. Publish the updated static output through Sites after reviewing new filings and identity changes. No recurring task is scheduled. The full refresh can take several minutes.

## Data and formulas

- Historical SEC 13F reproductions: 13f.info. Latest quarter original SEC XML is used where retrieved and reconciled. The dashboard identifies provenance for every manager. Original raw XML and JSON are retained in `data/`.
- Weight denominator is the complete reported 13F value, including reported option-underlying values. It is not NAV. ETFs, options, preferred stock and warrants are excluded from company candidate selection.
- Maximum fund allocation = largest individual manager weight. Equal-manager average = sum of all manager weights divided by available managers; absent positions are zero. Dollar values do not weight managers in the average.
- Share-count changes compare consecutive filings only when CUSIPs match. IPOs, new reporting coverage, conversions and corporate actions can cause apparent entries and exits. Clinical programs and catalysts need separate diligence.
- Daily market data: Yahoo Finance chart data; final completed daily bars only. Moving averages and Wilder RSI use closing prices; returns use adjusted closes. 1/3/6/12 months = 21/63/126/252 sessions. RVOL uses the previous 20 sessions as its baseline. IPOs without sufficient history show missing long-window metrics.
- Shareholder, short-interest and financial snapshots: Stock Analysis, with retrieval date. Underlying observation dates are not provided in the extracted statistics tables. No float ownership is inferred by mixing these snapshots with June 13F share counts.
- Other institutional holders: 13f.info's CUSIP-specific quarterly tables. Largest other institutions from the available top 30; no assumption of exhaustive or deduplicated beneficial ownership across affiliated managers. These institutions do not join the screening universe.
- Known symbol corrections preserve original issuer names and CUSIPs. Remaining identifier gaps are shown. Sector classifications are provisional name/ticker rules, not licensed GICS data.

## Files

- `dist/`: deployable, dependency-free browser dashboard.
- `data/holdings.json`: up to nine quarters for 50 managers, original positions and filing metadata.
- `data/market.json`: technical indicators and vendor statistics.
- `data/holders.json`: broader institutional-holder context.
- `scripts/`: collection, normalization and refresh pipeline.

## Validation

The original three SEC XML files are reconciled to their reported totals. Browser checks cover ranking controls, company profiles and WebMCP valid/invalid inputs. Data checks cover fund coverage, quarter coverage, weight bounds and exclusion of options from candidates. Results reflect disclosed holdings, not fund performance or current trading identities.

## Expanded technical indicators

The concentration table includes RSI 14 and 3-month performance relative to XBI. The technical monitor provides momentum, trend, and volatility views: Wilder RSI 14; MACD (EMA 12 minus EMA 26, signal EMA 9); ATR 14 and ATR/price; Bollinger Bands (20-session mean plus/minus 2 population standard deviations), band width and %B; SMA 20/50/200, crossover state and 5-session SMA50 slope; RVOL, dollar volume, volatility and drawdown; and relative returns versus XBI and XLV. EMA series seed at the first observed close. Stale market observations are labeled.
