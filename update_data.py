"""Refresh data.js with daily US spot ETF net flows for BTC, ETH, SOL and XRP.

Source: the per-fund daily history embedded in cryptoetf.today's flow pages.
Values are US$ millions. Run: python3 update_data.py
"""
import datetime as dt
import os
import json
import re
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


def fetch(slug):
    req = urllib.request.Request(f"https://cryptoetf.today/en/{slug}-etf-flows", headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8")


def history(page):
    t = page.replace('\\"', '"')
    start = t.index('"historical":[') + len('"historical":')
    depth = 0
    for end in range(start, len(t)):
        if t[end] == "[":
            depth += 1
        elif t[end] == "]":
            depth -= 1
            if depth == 0:
                return json.loads(t[start:end + 1])
    raise ValueError("historical array not closed")


def aum(page):
    text = re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S))
    m = re.search(r"AUM\s+\$([\d.]+)([BM])", text)
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
        for r in sorted(history(page), key=lambda r: r["date"]):
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
    main()
