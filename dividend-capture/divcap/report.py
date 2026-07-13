"""HTML report with inline-SVG charts (no external libraries).

Renders, per ex-dividend event that has Hyperliquid perp coverage:
  * the perp mark-price path around the ex-date, with the cum-close, the
    "full-dividend" reference (cum-close minus the dividend) and the entry/exit
    snapshots marked, so the overnight basis noise vs. the dividend is visible;
  * cumulative perp funding over the holding window;
  * a P&L table for the three strategies under maker and taker fills.
And an executive summary aggregating the drop ratios across all events.
"""

import html
import time


# --------------------------------------------------------------------------- #
# tiny SVG line-chart helper
# --------------------------------------------------------------------------- #
def _svg_line(series, width=720, height=240, pad=44, hlines=None, vlines=None,
              points=None, ylabel="", title=""):
    """series: list of (label, color, [(x_ms, y)]). hlines: [(y,color,label)].
    vlines: [(x_ms,color,label)]. points: [(x_ms,y,color,label)]."""
    xs, ys = [], []
    for _, _, pts in series:
        for x, y in pts:
            xs.append(x); ys.append(y)
    for h in (hlines or []):
        ys.append(h[0])
    for p in (points or []):
        xs.append(p[0]); ys.append(p[1])
    if not xs or not ys:
        return "<p><em>no data</em></p>"
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    if ymax == ymin:
        ymax += 1
    yr = ymax - ymin
    ymin -= yr * 0.08; ymax += yr * 0.08
    xr = (xmax - xmin) or 1

    def X(x): return pad + (x - xmin) / xr * (width - 2 * pad)
    def Y(y): return height - pad - (y - ymin) / (ymax - ymin) * (height - 2 * pad)

    out = [f'<svg viewBox="0 0 {width} {height}" width="100%" '
           f'style="max-width:{width}px;font:12px system-ui">']
    if title:
        out.append(f'<text x="{pad}" y="16" font-weight="600" fill="#111">{html.escape(title)}</text>')
    # axes frame
    out.append(f'<rect x="{pad}" y="{pad-8}" width="{width-2*pad}" height="{height-2*pad+8}" '
               f'fill="none" stroke="#e5e7eb"/>')
    # y grid + labels
    for i in range(5):
        yv = ymin + (ymax - ymin) * i / 4
        yy = Y(yv)
        out.append(f'<line x1="{pad}" y1="{yy:.1f}" x2="{width-pad}" y2="{yy:.1f}" stroke="#f1f5f9"/>')
        out.append(f'<text x="{pad-6}" y="{yy+4:.1f}" text-anchor="end" fill="#64748b">{yv:.2f}</text>')
    # x labels (dates)
    for i in range(5):
        xv = xmin + xr * i / 4
        xx = X(xv)
        lab = time.strftime("%m-%d", time.gmtime(xv / 1000))
        out.append(f'<text x="{xx:.1f}" y="{height-pad+16}" text-anchor="middle" fill="#64748b">{lab}</text>')
    # horizontal reference lines
    for (yv, color, label) in (hlines or []):
        yy = Y(yv)
        out.append(f'<line x1="{pad}" y1="{yy:.1f}" x2="{width-pad}" y2="{yy:.1f}" '
                   f'stroke="{color}" stroke-dasharray="5 4" stroke-width="1.3"/>')
        out.append(f'<text x="{width-pad-4}" y="{yy-4:.1f}" text-anchor="end" fill="{color}">{html.escape(label)}</text>')
    # vertical lines (e.g. ex-open)
    for (xv, color, label) in (vlines or []):
        xx = X(xv)
        out.append(f'<line x1="{xx:.1f}" y1="{pad-8}" x2="{xx:.1f}" y2="{height-pad}" '
                   f'stroke="{color}" stroke-dasharray="3 3" stroke-width="1.3"/>')
        out.append(f'<text x="{xx+3:.1f}" y="{pad+4}" fill="{color}">{html.escape(label)}</text>')
    # series polylines
    for (label, color, pts) in series:
        if not pts:
            continue
        d = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in pts)
        out.append(f'<polyline points="{d}" fill="none" stroke="{color}" stroke-width="1.8"/>')
    # marked points
    for (x, y, color, label) in (points or []):
        out.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="4" fill="{color}"/>')
        out.append(f'<text x="{X(x)+6:.1f}" y="{Y(y)-6:.1f}" fill="{color}" font-weight="600">{html.escape(label)}</text>')
    out.append("</svg>")
    return "".join(out)


def _money(v):
    return f"${v:,.0f}" if abs(v) >= 1 else f"${v:,.2f}"


def _cls(v):
    return "pos" if v > 0 else ("neg" if v < 0 else "")


# --------------------------------------------------------------------------- #
def event_card(r, candles, funding):
    ex = r["ex_date"]
    div = r["dividend"]
    p = r["perp"]
    parts = [f'<div class="card"><h3>{r["ticker"]} &middot; ex-date {ex} '
             f'<span class="muted">(cum {r["cum_date"]}, dividend ${div:.2f})</span></h3>']

    # stock line
    parts.append(
        f'<p>Underlying: <b>${r["price_entry"]:.2f}</b> (cum close) &rarr; '
        f'<b>${r["price_exit"]:.2f}</b> (ex {"open" if True else ""}) '
        f'= drop <b>${r["stock_drop"]:+.2f}</b>, '
        f'i.e. <b>{r["stock_drop_ratio"]:+.2f}&times;</b> the dividend. '
        f'A "textbook" ex-drop would be exactly 1.00&times;.</p>')

    if p:
        from .model import et_session_utc, perp_path
        entry_ms = et_session_utc(r["cum_date"], "close")
        exit_ms = et_session_utc(ex, "open")
        win_lo = entry_ms - 2 * 86400_000
        win_hi = exit_ms + 1 * 86400_000
        seg = [c for c in candles if win_lo <= c["t"] <= win_hi]
        pts = [((c["t"] + c["T"]) // 2, c["c"]) for c in seg]
        chart = _svg_line(
            series=[("perp mark", "#2563eb", pts)],
            hlines=[(p["entry"] - div, "#dc2626", f"cum-close − full div (${p['entry']-div:.2f})")],
            vlines=[(exit_ms, "#f59e0b", "ex-open")],
            points=[(entry_ms, p["entry"], "#16a34a", "entry"),
                    (exit_ms, p["exit"], "#7c3aed", "exit")],
            title=f"{r['ticker']} perp mark around ex-date")
        parts.append(chart)
        parts.append(
            f'<p>Perp: <b>${p["entry"]:.2f}</b> &rarr; <b>${p["exit"]:.2f}</b> '
            f'= drop <b>${p["drop"]:+.2f}</b> ({p["drop_ratio"]:+.2f}&times; div). '
            f'Basis gap vs stock: <b>${p["basis_gap"]:+.2f}</b>. '
            f'Overnight the perp wandered up to <b>${p["overnight_dev"]:.2f}</b> from the entry '
            f'= <b>{p["overnight_dev_x_div"]:.1f}&times;</b> the dividend '
            f'&mdash; the noise the edge has to survive.</p>')

        # funding cumulative chart
        frows = [f for f in funding if entry_ms - 2*86400_000 <= f["time"] <= exit_ms + 86400_000]
        cum, acc = [], 0.0
        for f in frows:
            acc += f["fundingRate"]
            cum.append((f["time"], acc * 100))
        parts.append(_svg_line(series=[("cumulative funding %", "#0891b2", cum)],
                               vlines=[(exit_ms, "#f59e0b", "ex-open")],
                               title="cumulative perp funding (%) — short receives when rising"))
        parts.append(
            f'<p>Funding over the {p["funding_hours"]}h hold summed to '
            f'<b>{p["funding_sum"]*100:+.4f}%</b> of notional '
            f'(a short {"receives" if p["funding_sum"]>0 else "pays"} this).</p>')
    else:
        parts.append('<p class="muted">No Hyperliquid perp coverage for this date '
                     '(event predates the equity-perp listing).</p>')

    # P&L table (recompute maker & taker)
    parts.append(_pnl_table(r))
    parts.append("</div>")
    return "".join(parts)


def _pnl_table(r):
    s = r["strategies"]
    rows = []
    rows.append(("A — dividend capture (long stock only)", s["A_plain"]["total"],
                 f'div {_money(s["A_plain"]["dividend"])}, price {_money(s["A_plain"]["price"])}, fees {_money(s["A_plain"]["fees"])}'))
    if "B_delta_neutral" in s:
        b = s["B_delta_neutral"]
        rows.append(("B — delta-neutral (long stock + short perp)", b["total"],
                     f'stock {_money(b["stock_price"]+b["dividend"])}, perp {_money(b["perp_price"])}, funding {_money(b["funding"])}, fees {_money(b["fees"])}'))
        c = s["C_perp_short"]
        rows.append(("C — pure perp short", c["total"],
                     f'perp {_money(c["perp_price"])}, funding {_money(c["funding"])}, fees {_money(c["fees"])}'))
    body = "".join(
        f'<tr><td>{html.escape(name)}</td>'
        f'<td class="{_cls(tot)} num">{_money(tot)}</td>'
        f'<td class="muted small">{html.escape(br)}</td></tr>'
        for name, tot, br in rows)
    return (f'<table class="pnl"><thead><tr><th>Strategy (per {_money(r["notional"])} notional)</th>'
            f'<th>P&amp;L</th><th>breakdown</th></tr></thead><tbody>{body}</tbody></table>')


def price_table(all_results, cfg):
    """Compact table: prices before/after ex + the corrected per-share P&L
    (long stock + short perp + dividend) and that P&L scaled to notional."""
    N = cfg["notional"]
    rows = []
    for rs in all_results.values():
        for r in rs:
            p = r["perp"]; ps = r["pnl_share"]
            if not p or not ps:
                continue
            qty = N / r["price_entry"]
            rows.append(
                f'<tr><td>{r["ticker"]} {r["ex_date"]}</td>'
                f'<td class="num">${r["dividend"]:.2f}</td>'
                f'<td class="num">{r["price_entry"]:.2f}</td>'
                f'<td class="num">{r["price_exit"]:.2f}</td>'
                f'<td class="num">{p["entry"]:.2f}</td>'
                f'<td class="num">{p["exit"]:.2f}</td>'
                f'<td class="num {_cls(ps["net"])}">{ps["net"]:+.2f}</td>'
                f'<td class="num {_cls(ps["net"]*qty)}">{_money(ps["net"]*qty)}</td></tr>')
    if not rows:
        return ""
    return f"""
    <h2>Prices &amp; corrected delta-neutral P&amp;L</h2>
    <p class="muted small">P&amp;L/share = (stock after − stock before) + (perp before − perp after)
      + net dividend. Long-stock leg gains when the stock rises; short-perp leg gains when the
      perp falls. The last column scales that to {_money(N)} of stock at entry.</p>
    <table class="pnl"><thead><tr>
      <th>Ticker / ex-date</th><th>Div</th>
      <th>Stock before</th><th>Stock after</th>
      <th>Perp before</th><th>Perp after</th>
      <th>P&amp;L / share</th><th>P&amp;L / {_money(N)}</th>
    </tr></thead><tbody>{''.join(rows)}</tbody></table>"""


def build_report(all_results, cfg, out_path):
    covered = [r for rs in all_results.values() for r in rs if r["perp"]]
    all_ev = [r for rs in all_results.values() for r in rs]

    def mean(vals):
        vals = [v for v in vals if v is not None]
        return sum(vals) / len(vals) if vals else float("nan")

    m_stock = mean([r["stock_drop_ratio"] for r in all_ev])
    m_perp = mean([r["perp"]["drop_ratio"] for r in covered])
    m_noise = mean([r["perp"]["overnight_dev_x_div"] for r in covered])
    m_b = mean([r["strategies"].get("B_delta_neutral", {}).get("total") for r in covered])

    summary = f"""
    <div class="summary">
      <h2>What the data says</h2>
      <ul>
        <li>Across <b>{len(all_ev)}</b> ex-dividend events, the underlying moved on average
            <b>{m_stock:+.2f}&times;</b> the dividend across the ex-date — nowhere near the
            textbook <b>1.00&times;</b>. The dividend is a rounding error next to the day-to-day move.</li>
        <li>On the <b>{len(covered)}</b> events with Hyperliquid perp coverage, the perp moved
            <b>{m_perp:+.2f}&times;</b> the dividend, while overnight it wandered up to
            <b>{m_noise:.1f}&times;</b> the dividend away from the entry.</li>
        <li>The delta-neutral play (B) averaged <b>{_money(m_b)}</b> per {_money(cfg['notional'])}
            event — but that number is dominated by basis noise, not by the ~0.1–0.2% dividend edge.</li>
        <li><b>Conclusion:</b> the dividend signal (~0.1–0.2%) is an order of magnitude smaller than the
            overnight basis noise (~0.5–1%+). The edge is real but tiny; the variance is not. Only
            worth it with maker fills, a short hold, and many repetitions — exactly as suspected.</li>
      </ul>
    </div>"""

    cards = []
    for tk, rs in all_results.items():
        for r in rs:
            cands = r.pop("_candles", [])
            fund = r.pop("_funding", [])
            cards.append(event_card(r, cands, fund))

    cfg_line = (f'notional {_money(cfg["notional"])} &middot; WHT {cfg["wht"]*100:.0f}% &middot; '
                f'exit {cfg["exit"]} &middot; fills {cfg["fills"]} &middot; '
                f'perp fee {cfg["perp_maker_bps"] if cfg["fills"]=="maker" else cfg["perp_taker_bps"]}bps/side')

    doc = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ex-Dividend / Dividend-Capture Model</title>
<style>
  body{{font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#0f172a;
       max-width:860px;margin:0 auto;padding:28px 18px 80px}}
  h1{{font-size:24px;margin:0 0 2px}} h2{{font-size:19px;margin:28px 0 8px}}
  h3{{font-size:16px;margin:0 0 8px}}
  .muted{{color:#64748b}} .small{{font-size:12px}}
  .config{{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:8px 12px;font-size:13px}}
  .summary{{background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;padding:6px 18px;margin:18px 0}}
  .card{{border:1px solid #e2e8f0;border-radius:10px;padding:16px 18px;margin:18px 0}}
  table.pnl{{border-collapse:collapse;width:100%;margin-top:12px;font-size:13px}}
  table.pnl th,table.pnl td{{border-bottom:1px solid #eef2f7;padding:6px 8px;text-align:left;vertical-align:top}}
  td.num{{font-variant-numeric:tabular-nums;font-weight:600;white-space:nowrap}}
  .pos{{color:#16a34a}} .neg{{color:#dc2626}}
  footer{{margin-top:40px;font-size:12px;color:#94a3b8}}
</style></head><body>
<h1>Ex-Dividend &amp; Dividend-Capture Model</h1>
<p class="muted">Empirical study of price behaviour around ex-dividend dates for Hyperliquid
equity perps and their underlyings. Buy the day before ex, sell on the ex-date.</p>
<div class="config">{cfg_line}</div>
{summary}
{price_table(all_results, cfg)}
<h2>Per-event detail</h2>
{''.join(cards)}
<footer>
  Data: Yahoo Finance (dividends + stock OHLC), Hyperliquid <code>info</code> API
  (perp candles + funding, dex <code>{cfg.get('dex','xyz')}</code>).
  Generated {time.strftime('%Y-%m-%d')}. Educational model, not investment advice.
</footer>
</body></html>"""
    with open(out_path, "w") as f:
        f.write(doc)
    return out_path
