"""Refresh data.js with daily US spot ETF net flows for BTC, ETH, SOL and XRP.

Source: cryptoetf.today's per-fund daily history API (AUM from its flow pages).
Values are US$ millions. Run: python3 update_data.py
"""
import datetime as dt
import http.client
import os
import json
import re
import sys
import time
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/128 Safari/537.36"

# page slug, source field -> (ticker, issuer)
COINS = {
    "BTC": ("bitcoin", [
        ("blackrock", "IBIT", "BlackRock"), ("fidelity", "FBTC", "Fidelity"),
        ("grayscale", "GBTC", "Grayscale"), ("grayscaleBtc", "BTC", "Grayscale Mini"),
        ("bitwise", "BITB", "Bitwise"), ("twentyOneShares", "ARKB", "ARK 21Shares"),
        ("vanEck", "HODL", "VanEck"), ("morganStanley", "MSBT", "Morgan Stanley"),
        ("valkyrie", "BRRR", "CoinShares Valkyrie"), ("franklin", "EZBC", "Franklin"),
        ("invesco", "BTCO", "Invesco Galaxy"), ("wisdomTree", "BTCW", "WisdomTree"),
    ]),
    "ETH": ("ethereum", [
        ("blackrock", "ETHA", "BlackRock"), ("blackrock2", "ETHB", "BlackRock Staked"),
        ("fidelity", "FETH", "Fidelity"), ("grayscale", "ETHE", "Grayscale"),
        ("grayscaleCrypto", "ETH", "Grayscale Mini"), ("bitwise", "ETHW", "Bitwise"),
        ("vanEck", "ETHV", "VanEck"), ("franklin", "EZET", "Franklin"),
        ("twentyOneShares", "TETH", "21Shares"), ("morganStanleyEth", "MSSE", "Morgan Stanley"),
        ("invesco", "QETH", "Invesco Galaxy"),
    ]),
    "SOL": ("solana", [
        ("bitwise", "BSOL", "Bitwise"), ("fidelity", "FSOL", "Fidelity"),
        ("grayscale", "GSOL", "Grayscale"), ("vanEck", "VSOL", "VanEck"),
        ("twentyOneShares", "TSOL", "21Shares"), ("morganStanley", "MSOL", "Morgan Stanley"),
        ("franklin", "SOEZ", "Franklin"), ("canary", "SOLC", "Canary"),
        ("invesco", "QSOL", "Invesco Galaxy"),
    ]),
    "XRP": ("xrp", [
        ("bitwise", "XRP", "Bitwise"), ("canary", "XRPC", "Canary"),
        ("franklin", "XRPZ", "Franklin"), ("grayscale", "GXRP", "Grayscale"),
        ("twentyOneShares", "TOXR", "21Shares"),
    ]),
}


class SourceDown(Exception):
    """cryptoetf.today kept failing with errors that usually clear up on their own."""


def get(url):
    # The source has short outages (502s, connections cut mid-download); retry
    # those, and report anything else (e.g. a page layout change) as an error.
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429:
                raise
            err = e
        except (urllib.error.URLError, http.client.IncompleteRead, TimeoutError, ConnectionError) as e:
            err = e
        time.sleep(15 * (attempt + 1))
    raise SourceDown(f"{url}: {err}")


def fetch(slug):
    return get(f"https://cryptoetf.today/en/{slug}-etf-flows")


def history(slug):
    return json.loads(get(f"https://api.cryptoetf.today/api/etf-flow/{slug}"))


def aum(page):
    text = re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S))
    # The page labelled this "AUM" until Oct 2026, then "Net assets".
    m = re.search(r"(?:AUM|Net assets)\D{0,40}?\$([\d.]+)([BM])", text)
    return round(float(m.group(1)) * (1000 if m.group(2) == "B" else 1), 1) if m else None


OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.js")
PREFIX = "window.FLOWS = "


def previous():
    try:
        with open(OUT) as f:
            return json.loads(f.read().strip()[len(PREFIX):].rstrip(";"))
    except (OSError, ValueError):
        return None


def main():
    out = {"asOf": None, "updatedAt": None, "coins": {}}
    last_dates = []
    for sym, (slug, funds) in COINS.items():
        page = fetch(slug)
        rows = []
        for r in sorted(history(slug), key=lambda r: r["date"]):
            vals = [round(r.get(k) or 0, 3) for k, _, _ in funds]
            total = round(r.get("total") or 0, 3)
            if dt.date.fromisoformat(r["date"]).weekday() >= 5:
                # weekend-dated rows: fold any reported flow into the prior session
                if rows and (total or any(vals)):
                    prev = rows[-1]
                    prev[1] = round(prev[1] + total, 3)
                    for i, v in enumerate(vals):
                        prev[2 + i] = round(prev[2 + i] + v, 3)
                continue
            rows.append([r["date"], total] + vals)
        # drop trailing all-zero rows (today's session not yet reported)
        while rows and rows[-1][1] == 0 and not any(rows[-1][2:]):
            rows.pop()
        last_dates.append(rows[-1][0])
        out["coins"][sym] = {
            "funds": [[t, i] for _, t, i in funds],
            "aum": aum(page),
            "rows": rows,
        }
        print(sym, len(rows), rows[0][0], "->", rows[-1][0])
    out["asOf"] = max(last_dates)
    prev = previous()
    if prev and prev.get("coins") == out["coins"] and prev.get("asOf") == out["asOf"]:
        print("No new flows since", prev.get("updatedAt"))
        return
    out["updatedAt"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(OUT, "w") as f:
        f.write(PREFIX + json.dumps(out, separators=(",", ":")) + ";\n")
    print("Wrote", OUT)


if __name__ == "__main__":
    try:
        main()
    except SourceDown as e:
        # Keep the current data.js; the next scheduled run will catch up.
        print(f"::warning::Source unavailable, skipping this refresh: {e}")
        sys.exit(0)
