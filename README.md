# Spot Flow Desk

A dashboard for net inflows and outflows of US spot Bitcoin, Ethereum, Solana and XRP ETFs. You can view flows by day, week, month or year, compare all four assets, or open one asset to see a breakdown by fund.

**Live:** https://jtroshani.github.io/spot-flow-desk/

## How it stays current

- A GitHub Action runs every hour. It runs `update_data.py` and commits `data.js` only when there are new flows.
- The page reloads `data.js` every hour. The bar at the top shows when it last checked and counts down to the next check. **Refresh** checks right away.
- ETF issuers report flows once per trading day, after the US market closes. Most hourly checks therefore find no change, and you'll see "Up to date".

## Run locally

```sh
python3 serve.py        # serves http://localhost:8000 and refreshes data.js every hour
```

You can also open `index.html` directly. It reads whatever `data.js` is on disk; run `python3 update_data.py` to update it.

## Files

| File | Purpose |
|---|---|
| `index.html` | The dashboard (plain HTML/JS, no build step) |
| `data.js` | Daily per-fund net flows in US$ millions |
| `update_data.py` | Downloads the latest flows into `data.js` |
| `serve.py` | Local server with hourly refresh |
| `.github/workflows/refresh.yml` | Hourly data refresh on GitHub |

Data source: [cryptoetf.today](https://cryptoetf.today/en/bitcoin-etf-flows).
