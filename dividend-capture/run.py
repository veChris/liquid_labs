#!/usr/bin/env python3
"""Run the ex-dividend / dividend-capture model.

    python3 run.py --tickers MSFT,AAPL,NVDA --notional 100000 --fills maker

Outputs:
    out/report.html   interactive report with charts + per-event P&L
    out/events.csv     one row per ex-dividend event

Everything runs on real data (Yahoo dividends+OHLC, Hyperliquid perp candles+funding),
cached under cache/. No third-party packages required.
"""

import argparse
import csv
import os
import sys
import webbrowser

from divcap import data, model, report

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")


def parse_args(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tickers", default="MSFT,AAPL,NVDA,COIN,MSTR",
                    help="comma list; only tickers with a Hyperliquid equity perp are analysed")
    ap.add_argument("--notional", type=float, default=100_000)
    ap.add_argument("--wht", type=float, default=0.15, help="dividend withholding tax fraction")
    ap.add_argument("--exit", choices=["ex_open", "ex_close"], default="ex_open",
                    help="when to sell on the ex-date")
    ap.add_argument("--fills", choices=["maker", "taker"], default="maker")
    ap.add_argument("--stock-fee-bps", type=float, default=1.0)
    ap.add_argument("--perp-maker-bps", type=float, default=3.0)
    ap.add_argument("--perp-taker-bps", type=float, default=9.0)
    ap.add_argument("--range", default="1y", help="Yahoo history range (1y,2y,5y)")
    ap.add_argument("--open", action="store_true", help="open the report in a browser")
    return ap.parse_args(argv)


def main(argv):
    a = parse_args(argv)
    os.makedirs(OUT, exist_ok=True)
    cfg = dict(notional=a.notional, wht=a.wht, exit=a.exit, fills=a.fills,
               stock_fee_bps=a.stock_fee_bps, perp_maker_bps=a.perp_maker_bps,
               perp_taker_bps=a.perp_taker_bps, dex=data.HL_EQUITY_DEX)

    available = set(data.hl_available_equities())
    requested = [t.strip().upper() for t in a.tickers.split(",") if t.strip()]
    tickers = [t for t in requested if t in available]
    skipped = [t for t in requested if t not in available]
    if skipped:
        print(f"note: no Hyperliquid equity perp for {', '.join(skipped)} — "
              f"using stock data only where possible", file=sys.stderr)

    all_results = {}
    for tk in tickers:
        print(f"[{tk}] fetching…", file=sys.stderr)
        divs, bars = data.stock_series(tk, a.range)
        if not bars:
            continue
        lo, hi = int(bars[min(bars)]["ts"]), int(bars[max(bars)]["ts"])
        candles = data.hl_candles(tk, lo, hi)
        funding = data.hl_funding(tk, lo, hi)
        rows = []
        for ev in divs:
            r = model.analyze_event(tk, ev, bars, candles, funding, cfg)
            if r:
                r["_candles"] = candles
                r["_funding"] = funding
                rows.append(r)
        all_results[tk] = rows

    if not any(all_results.values()):
        print("No events found. Try a wider --range or different --tickers.", file=sys.stderr)
        return 1

    write_csv(all_results, os.path.join(OUT, "events.csv"))
    path = report.build_report(all_results, cfg, os.path.join(OUT, "report.html"))
    print(f"\nWrote {path}\nWrote {os.path.join(OUT, 'events.csv')}")
    print_console(all_results, cfg)
    if a.open:
        webbrowser.open("file://" + path)
    return 0


def write_csv(all_results, path):
    cols = ["ticker", "ex_date", "cum_date", "dividend",
            "stock_before", "stock_after", "perp_before", "perp_after",
            "pnl_share_priceDiv", "funding_share", "fees_share",
            "pnl_share_full", "pnl_notional_full",
            "stock_drop", "stock_drop_ratio", "perp_drop", "perp_drop_ratio",
            "basis_gap", "overnight_dev_x_div", "funding_sum_pct",
            "A_plain", "B_delta_neutral", "C_perp_short"]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for rs in all_results.values():
            for r in rs:
                p = r["perp"]
                s = r["strategies"]
                ps = r["pnl_share"]
                qty = r["notional"] / r["price_entry"]
                w.writerow([
                    r["ticker"], r["ex_date"], r["cum_date"], f'{r["dividend"]:.4f}',
                    f'{r["price_entry"]:.2f}', f'{r["price_exit"]:.2f}',
                    f'{p["entry"]:.2f}' if p else "", f'{p["exit"]:.2f}' if p else "",
                    f'{ps["net"]:.4f}' if ps else "",
                    f'{ps["funding"]:.4f}' if ps else "",
                    f'{ps["fees"]:.4f}' if ps else "",
                    f'{ps["full_net"]:.4f}' if ps else "",
                    f'{ps["full_net"]*qty:.1f}' if ps else "",
                    f'{r["stock_drop"]:.4f}', f'{r["stock_drop_ratio"]:.3f}',
                    f'{p["drop"]:.4f}' if p else "", f'{p["drop_ratio"]:.3f}' if p else "",
                    f'{p["basis_gap"]:.4f}' if p else "",
                    f'{p["overnight_dev_x_div"]:.2f}' if p else "",
                    f'{p["funding_sum"]*100:.4f}' if p else "",
                    f'{s["A_plain"]["total"]:.1f}',
                    f'{s["B_delta_neutral"]["total"]:.1f}' if "B_delta_neutral" in s else "",
                    f'{s["C_perp_short"]["total"]:.1f}' if "C_perp_short" in s else "",
                ])


def print_console(all_results, cfg):
    print("\n" + "=" * 78)
    print(f"{'ticker/ex':16} {'div':>6} {'stk×':>6} {'perp×':>6} {'noise×':>7} "
          f"{'A':>8} {'B':>8} {'C':>8}")
    print("-" * 78)
    agg = {"stock": [], "perp": [], "noise": [], "B": []}
    for rs in all_results.values():
        for r in rs:
            p = r["perp"]; s = r["strategies"]
            b = s.get("B_delta_neutral", {}).get("total")
            c = s.get("C_perp_short", {}).get("total")
            print(f"{r['ticker']+' '+r['ex_date']:16} {r['dividend']:6.2f} "
                  f"{r['stock_drop_ratio']:6.2f} "
                  f"{p['drop_ratio']:6.2f}" if p else
                  f"{r['ticker']+' '+r['ex_date']:16} {r['dividend']:6.2f} "
                  f"{r['stock_drop_ratio']:6.2f} {'  n/a':>6}", end="")
            if p:
                print(f" {p['overnight_dev_x_div']:7.1f} "
                      f"{s['A_plain']['total']:8.0f} {b:8.0f} {c:8.0f}")
                agg["perp"].append(p["drop_ratio"]); agg["noise"].append(p["overnight_dev_x_div"])
                agg["B"].append(b)
            else:
                print(f" {'n/a':>7} {s['A_plain']['total']:8.0f} {'n/a':>8} {'n/a':>8}")
            agg["stock"].append(r["stock_drop_ratio"])

    def mean(v): return sum(v) / len(v) if v else float("nan")
    print("-" * 78)
    print(f"means: stock drop {mean(agg['stock']):+.2f}× | perp drop {mean(agg['perp']):+.2f}× | "
          f"overnight noise {mean(agg['noise']):.1f}× div | delta-neutral B {mean(agg['B']):+.0f}")
    print("=" * 78)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
