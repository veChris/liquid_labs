"""Event-study + P&L engine for the ex-dividend / dividend-capture strategy.

For every ex-dividend event we measure, from real data:

  * how much the *underlying stock* actually dropped across the ex-date
    (the classic "does it drop by the full dividend?" question), and
  * how much the *Hyperliquid equity perp* dropped over the same window, and
  * what *funding* the perp accrued over the holding window.

From those we compute the P&L of three ways to play the same event, all
sized to the same notional N and all "buy the day before ex, sell on ex-day":

  A) plain dividend capture   long stock only            -> keep net dividend, eat the drop
  B) delta-neutral            long stock + short perp     -> the strategy discussed
  C) pure perp short          short perp only             -> harvest the perp's ex-date drop

Sign conventions
----------------
  drop            = entry_price - exit_price          (>0 means price fell = classic ex-date move)
  drop_ratio      = drop / dividend                   (1.0 = fully priced in)
  funding: HL positive rate => longs pay shorts. A SHORT therefore *receives*
           positive funding. funding_pnl(short) = +sum(rate_h) * notional.
"""

import time


# --------------------------------------------------------------------------- #
# US Eastern time helpers (NYSE session -> UTC ms)
# --------------------------------------------------------------------------- #
def _nth_weekday(year, month, weekday, n):
    """UTC-day timestamp of the n-th `weekday` (0=Mon) of month. n negative => from end."""
    import calendar
    days = [d for d in range(1, calendar.monthrange(year, month)[1] + 1)
            if time.gmtime(time.mktime((year, month, d, 12, 0, 0, 0, 0, 0)) -
                           time.timezone).tm_wday == weekday]
    return days[n if n < 0 else n - 1]


def _us_dst(ts_ms):
    """True if US Eastern DST (EDT) is in effect at this instant.
    DST: 2nd Sunday of March 07:00 UTC .. 1st Sunday of November 06:00 UTC."""
    t = time.gmtime(ts_ms / 1000)
    y = t.tm_year
    mar = _nth_weekday(y, 3, 6, 2)   # 2nd Sunday March
    nov = _nth_weekday(y, 11, 6, 1)  # 1st Sunday November
    start = _ymd_utc(y, 3, mar, 7)
    end = _ymd_utc(y, 11, nov, 6)
    return start <= ts_ms < end


def _ymd_utc(y, m, d, hour=0, minute=0):
    return int(time.mktime((y, m, d, hour, minute, 0, 0, 0, 0)) - time.timezone) * 1000


def et_session_utc(day_str, which):
    """UTC ms for NYSE 'open' (09:30 ET) or 'close' (16:00 ET) on a calendar day."""
    y, m, d = map(int, day_str.split("-"))
    noon = _ymd_utc(y, m, d, 12)
    off = 4 if _us_dst(noon) else 5          # EDT=UTC-4, EST=UTC-5
    hh, mm = (9, 30) if which == "open" else (16, 0)
    return _ymd_utc(y, m, d, hh + off, mm)


# --------------------------------------------------------------------------- #
# Perp snapshot from hourly candles
# --------------------------------------------------------------------------- #
def perp_price_at(candles, target_ms, tol_ms=3 * 3600 * 1000):
    """Close of the hourly candle covering target_ms, else the nearest candle
    within `tol_ms`. Returns None if target_ms falls outside candle coverage
    (e.g. the event predates the perp's listing) so we never fabricate a drop."""
    if not candles:
        return None
    if target_ms < candles[0]["t"] - tol_ms or target_ms > candles[-1]["T"] + tol_ms:
        return None
    best, bestd = None, None
    for c in candles:
        if c["t"] <= target_ms <= c["T"]:
            return c["c"]
        mid = (c["t"] + c["T"]) / 2
        dd = abs(mid - target_ms)
        if bestd is None or dd < bestd:
            best, bestd = c, dd
    if best and bestd is not None and bestd <= tol_ms:
        return best["c"]
    return None


def perp_path(candles, start_ms, end_ms):
    seg = [c for c in candles if start_ms <= c["t"] <= end_ms]
    return seg


def funding_over(funding, start_ms, end_ms):
    """Sum of hourly funding rates in [start,end]; also count of hours."""
    rows = [f for f in funding if start_ms <= f["time"] <= end_ms]
    return sum(f["fundingRate"] for f in rows), len(rows)


# --------------------------------------------------------------------------- #
# The event study
# --------------------------------------------------------------------------- #
def prev_trading_day(bars, ex_date):
    days = sorted(bars)
    prior = [d for d in days if d < ex_date]
    return prior[-1] if prior else None


def analyze_event(ticker, ev, bars, candles, funding, cfg):
    """Return a dict of measurements + P&L for one ex-dividend event, or None
    if we lack the stock bars around it."""
    ex_date = ev["ex_date"]
    div = ev["amount"]
    cum_date = prev_trading_day(bars, ex_date)
    if not cum_date or ex_date not in bars:
        return None

    cum = bars[cum_date]
    exb = bars[ex_date]

    exit_side = cfg["exit"]                      # "ex_open" or "ex_close"
    P_entry = cum["close"]                        # buy at cum-day close
    P_exit_stock = exb["open"] if exit_side == "ex_open" else exb["close"]

    net_div = div * (1 - cfg["wht"])

    # ---- underlying stock drop ----
    stock_drop = P_entry - P_exit_stock
    stock_drop_ratio = stock_drop / div if div else None

    # ---- perp snapshots over the SAME wall-clock window ----
    entry_ms = et_session_utc(cum_date, "close")
    exit_ms = et_session_utc(ex_date, "open" if exit_side == "ex_open" else "close")
    perp_entry = perp_price_at(candles, entry_ms) if candles else None
    perp_exit = perp_price_at(candles, exit_ms) if candles else None

    perp = {}
    if perp_entry and perp_exit:
        perp_drop = perp_entry - perp_exit
        seg = perp_path(candles, entry_ms, exit_ms)
        # overnight basis noise: max abs deviation of perp from the cum-close,
        # expressed in $ and as a multiple of the dividend
        dev = max((abs(c["h"] - perp_entry) for c in seg), default=0.0)
        dev = max(dev, max((abs(c["l"] - perp_entry) for c in seg), default=0.0))
        fund_sum, fund_hrs = funding_over(funding, entry_ms, exit_ms)
        perp = {
            "entry": perp_entry, "exit": perp_exit,
            "drop": perp_drop, "drop_ratio": perp_drop / div if div else None,
            "basis_gap": perp_drop - stock_drop,        # perp fell more(+)/less(-) than stock
            "overnight_dev": dev, "overnight_dev_x_div": dev / div if div else None,
            "funding_sum": fund_sum, "funding_hours": fund_hrs,
        }

    # ---- P&L per strategy, sized to notional N ----
    N = cfg["notional"]
    qty = N / P_entry
    stock_fee = cfg["stock_fee_bps"] / 1e4
    perp_fee = (cfg["perp_maker_bps"] if cfg["fills"] == "maker" else cfg["perp_taker_bps"]) / 1e4

    # A) plain dividend capture (long stock only)
    a_price = qty * (P_exit_stock - P_entry)
    a_div = qty * net_div
    a_fees = 2 * stock_fee * N
    a_total = a_price + a_div - a_fees

    strat = {"A_plain": {"price": a_price, "dividend": a_div,
                         "fees": -a_fees, "total": a_total}}

    if perp:
        qp = N / perp["entry"]
        # short perp: gains when price falls => +qp*drop
        b_perp_price = qp * perp["drop"]
        # short receives positive funding
        b_funding = perp["funding_sum"] * N
        b_perp_fees = 2 * perp_fee * N
        # B) delta-neutral = stock leg (A without its fees, we fee both legs explicitly)
        b_stock = a_price + a_div
        b_total = b_stock + b_perp_price + b_funding - a_fees - b_perp_fees
        strat["B_delta_neutral"] = {
            "stock_price": a_price, "dividend": a_div,
            "perp_price": b_perp_price, "funding": b_funding,
            "fees": -(a_fees + b_perp_fees), "total": b_total,
        }
        # C) pure perp short
        c_total = b_perp_price + b_funding - b_perp_fees
        strat["C_perp_short"] = {
            "perp_price": b_perp_price, "funding": b_funding,
            "fees": -b_perp_fees, "total": c_total,
        }

    # ---- corrected per-share delta-neutral P&L ----
    # P&L/share = (stock exit - stock entry) + (perp entry - perp exit) + dividend
    #   long-stock leg gains when the stock rises;
    #   short-perp leg gains when the perp falls;
    #   plus the dividend you collect (gross, and net of WHT).
    ps = None
    if perp:
        stock_leg = P_exit_stock - P_entry
        perp_leg = perp["entry"] - perp["exit"]
        ps = {
            "stock_leg": stock_leg, "perp_leg": perp_leg,
            "gross": stock_leg + perp_leg + div,
            "net": stock_leg + perp_leg + net_div,   # dividend net of WHT
        }

    return {
        "ticker": ticker, "ex_date": ex_date, "cum_date": cum_date,
        "dividend": div, "net_dividend": net_div,
        "price_entry": P_entry, "price_exit": P_exit_stock,
        "stock_drop": stock_drop, "stock_drop_ratio": stock_drop_ratio,
        "perp": perp, "strategies": strat, "pnl_share": ps,
        "notional": N, "qty": qty,
    }
