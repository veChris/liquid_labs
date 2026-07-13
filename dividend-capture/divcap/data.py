"""Data layer — stdlib only (urllib).

Two sources:
  * Yahoo Finance chart API  -> ex-dividend dates/amounts + underlying stock daily OHLC
  * Hyperliquid info API      -> equity-perp mark-price candles + funding history
                                 (equity perps live on the HIP-3 builder dex "xyz",
                                  e.g. the perp for MSFT is the coin "xyz:MSFT")

All responses are cached under cache/ so a run is reproducible offline and we
don't hammer the APIs. Delete the cache dir to force a refresh.
"""

import json
import os
import time
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(os.path.dirname(HERE), "cache")

HL_INFO = "https://api.hyperliquid.xyz/info"
YAHOO = "https://query2.finance.yahoo.com/v8/finance/chart/{sym}?range={rng}&interval=1d&events=div"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# Equity perps are deployed on this HIP-3 dex. coin id = "<DEX>:<TICKER>".
HL_EQUITY_DEX = "xyz"

MS_DAY = 86_400_000


def _cache_path(key):
    os.makedirs(CACHE_DIR, exist_ok=True)
    safe = key.replace("/", "_").replace(":", "_")
    return os.path.join(CACHE_DIR, safe + ".json")


def _cached(key, producer, ttl_hours=12):
    path = _cache_path(key)
    if os.path.exists(path):
        age_h = (time.time() - os.path.getmtime(path)) / 3600.0
        if age_h < ttl_hours:
            with open(path) as f:
                return json.load(f)
    data = producer()
    with open(path, "w") as f:
        json.dump(data, f)
    return data


def _http_json(url=None, post=None, headers=None, retries=4):
    """GET (url) or POST (url+post dict). Retries with backoff on transient errors."""
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers or {})
            if post is not None:
                req.data = json.dumps(post).encode()
                req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
            last = e
            time.sleep(2 ** i)
    raise RuntimeError(f"request failed after {retries} tries: {url} -> {last}")


# --------------------------------------------------------------------------- #
# Yahoo: dividends + stock daily OHLC
# --------------------------------------------------------------------------- #
def yahoo_chart(ticker, rng="2y"):
    def produce():
        return _http_json(YAHOO.format(sym=ticker, rng=rng), headers={"User-Agent": UA})
    return _cached(f"yahoo_{ticker}_{rng}", produce)


def stock_series(ticker, rng="2y"):
    """Returns (dividends, bars).

    dividends: list of {"ex_date": "YYYY-MM-DD", "ts": ms, "amount": float}
    bars:      dict "YYYY-MM-DD" -> {open, high, low, close, ts}  (regular-session daily)
    """
    d = yahoo_chart(ticker, rng)
    res = d["chart"]["result"][0]
    ts = res["timestamp"]
    q = res["indicators"]["quote"][0]
    bars = {}
    for i, t in enumerate(ts):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if c is None:
            continue
        day = time.strftime("%Y-%m-%d", time.gmtime(t))
        bars[day] = {"open": o, "high": h, "low": l, "close": c, "ts": t * 1000}
    divs = []
    for v in res.get("events", {}).get("dividends", {}).values():
        divs.append({
            "ex_date": time.strftime("%Y-%m-%d", time.gmtime(v["date"])),
            "ts": v["date"] * 1000,
            "amount": float(v["amount"]),
        })
    divs.sort(key=lambda x: x["ts"])
    return divs, bars


# --------------------------------------------------------------------------- #
# Hyperliquid: perp candles + funding
# --------------------------------------------------------------------------- #
def hl_coin(ticker):
    return f"{HL_EQUITY_DEX}:{ticker}"


def hl_available_equities():
    def produce():
        return _http_json(HL_INFO, post={"type": "perpDexs"})
    dexs = _cached("hl_perpdexs", produce)
    for x in dexs:
        if x and x.get("name") == HL_EQUITY_DEX:
            return [a.split(":")[1] for a, _ in x["assetToStreamingOiCap"]]
    return []


def hl_candles(ticker, start_ms, end_ms, interval="1h"):
    coin = hl_coin(ticker)

    def produce():
        return _http_json(HL_INFO, post={
            "type": "candleSnapshot",
            "req": {"coin": coin, "interval": interval,
                    "startTime": start_ms, "endTime": end_ms},
        })
    raw = _cached(f"hl_candle_{coin}_{interval}_{start_ms}_{end_ms}", produce)
    out = []
    for c in raw:
        out.append({"t": c["t"], "T": c["T"], "o": float(c["o"]),
                    "h": float(c["h"]), "l": float(c["l"]),
                    "c": float(c["c"]), "v": float(c["v"])})
    return out


def hl_funding(ticker, start_ms, end_ms):
    """Hourly funding rows. HL caps a response at 500 rows, so we page forward."""
    coin = hl_coin(ticker)

    def produce():
        rows, cursor = [], start_ms
        while True:
            batch = _http_json(HL_INFO, post={
                "type": "fundingHistory", "coin": coin,
                "startTime": cursor, "endTime": end_ms})
            if not batch:
                break
            rows.extend(batch)
            if len(batch) < 500:
                break
            nxt = batch[-1]["time"] + 1
            if nxt <= cursor:
                break
            cursor = nxt
        # dedupe by time
        seen, dedup = set(), []
        for r in rows:
            if r["time"] in seen:
                continue
            seen.add(r["time"])
            dedup.append({"time": r["time"], "fundingRate": float(r["fundingRate"]),
                          "premium": float(r.get("premium", 0) or 0)})
        dedup.sort(key=lambda x: x["time"])
        return dedup
    return _cached(f"hl_funding_{coin}_{start_ms}_{end_ms}", produce)
