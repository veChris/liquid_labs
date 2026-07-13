# Ex-Dividend / Dividend-Capture Model

An empirical model of how prices behave around **ex-dividend dates** for
Hyperliquid equity perps and their underlying stocks — and whether you can
profit by **buying the day before ex and selling on the ex-date**.

It answers, from real data, the questions from the strategy discussion:

- Does the price actually drop by the dividend on the ex-date, or does market
  noise dominate?
- Does the Hyperliquid perp drop by the same amount as the stock (so the legs
  cancel in a delta-neutral trade), or does it misprice the event?
- What does funding do over the holding window?
- After WHT and maker/taker fees, is any of this positive — and how big is the
  edge next to the overnight basis noise?

## Strategies compared

All sized to the same notional, all "buy at cum-day close, sell on ex-date":

| | Legs | Thesis |
|---|---|---|
| **A** Dividend capture | long stock only | keep the net dividend, eat the price drop |
| **B** Delta-neutral | long stock + short perp | drop cancels, keep the net dividend |
| **C** Pure perp short | short perp only | harvest the perp's ex-date drop, pay funding |

## Data sources (no API keys, no pip installs)

- **Yahoo Finance** `v8/finance/chart` — ex-dividend dates + amounts and the
  underlying daily OHLC.
- **Hyperliquid** `info` API — equity-perp mark-price candles (`candleSnapshot`)
  and `fundingHistory`. Equity perps live on the HIP-3 builder dex **`xyz`**,
  so MSFT's perp is the coin `xyz:MSFT`. Perp history currently reaches back
  ~200 days, so events before the listing show stock-only.

Raw responses are cached under `cache/` (12h TTL) so runs are reproducible and
offline-friendly. Delete `cache/` to force a refresh.

## Run

```bash
cd dividend-capture
python3 run.py --tickers MSFT,AAPL,NVDA,COIN,MSTR,GOOGL --notional 100000 --fills maker
```

Useful flags:

| flag | default | meaning |
|---|---|---|
| `--tickers` | MSFT,AAPL,NVDA,COIN,MSTR | comma list (only tickers with an `xyz:` perp are analysed) |
| `--notional` | 100000 | position size per event |
| `--wht` | 0.15 | dividend withholding tax (Cyprus/US treaty = 15%) |
| `--exit` | ex_open | sell on ex-date open or `ex_close` |
| `--fills` | maker | `maker` (3 bps/side) or `taker` (9 bps/side) |
| `--range` | 1y | Yahoo history window (`1y`,`2y`,`5y`) |
| `--open` | – | open the HTML report in a browser |

### Outputs

- `out/report.html` — executive summary + per-event cards with inline-SVG
  charts (perp mark around the ex-date, the "full-dividend" reference line, the
  overnight path, cumulative funding) and a P&L table per strategy.
- `out/events.csv` — one row per event with every measured field, including the
  corrected per-share delta-neutral P&L (see below).

### Corrected delta-neutral P&L (per share)

The report and CSV carry an explicit per-share P&L for "long stock + short perp,
hold across the ex-date":

```
P&L/share = (stock_after − stock_before)   ← long-stock leg: gains when stock rises
          + (perp_before  − perp_after)    ← short-perp leg: gains when perp falls
          + dividend (net of WHT)           ← the payout you collect
```

Note the **entry-side signs**: you *pay* for the stock (`− stock_before`) and
*receive* proceeds when shorting the perp (`+ perp_before`). A P&L is always
*exit − entry*, never a sum of the two basis snapshots — summing them
double-counts the entry basis (`+ 2·(stock_before − perp_before)`) and is not a
tradeable result.

Funding and fees are then added **per share** so one row is the complete net:

```
Full net / share = P&L/share  +  funding/share  +  fees/share
```

CSV columns: `pnl_share_priceDiv` (price legs + net dividend), `funding_share`,
`fees_share` (maker by default, negative), `pnl_share_full` (everything), and
`pnl_notional_full` (scaled to `--notional` of stock at entry).

## How each event is measured

For each ex-dividend event:

1. **cum day** = last trading day before ex. Entry = its close. Exit = ex-date
   open (or close).
2. **Stock drop** = `entry − exit`; **drop ratio** = `drop / dividend`
   (1.00 = "textbook" full drop).
3. **Perp snapshots** are taken at the *NYSE close* on cum-day and the chosen
   NYSE session time on ex-day (Eastern time, DST-aware), so stock and perp are
   compared over the same wall-clock window. From these: perp drop, perp drop
   ratio, **basis gap** (perp drop − stock drop) and the **overnight deviation**
   (how far the perp wandered from entry, as a multiple of the dividend).
4. **Funding** over the hold is summed from hourly `fundingHistory`. On
   Hyperliquid a positive rate means longs pay shorts, so a **short receives**
   positive funding.
5. **P&L** for A/B/C uses net dividend `div·(1−WHT)`, the measured price moves,
   funding, and round-trip fees.

## What the data shows (and the honest caveat)

The dividend on these names is ~0.05–0.2% of price. The measured **overnight
basis noise on the perp is routinely 10–40× the dividend** — a single night's
drift dwarfs the entire edge. So:

- The per-event P&L is dominated by *market direction over that one night*, not
  by the dividend. A few events look great, a few awful; that's variance, not
  edge.
- The genuine, repeatable edge (net dividend minus funding minus fees) is real
  but small, and only survives with **maker fills** and a **short hold**.
- Names with a tiny dividend (e.g. NVDA at $0.01) produce absurd ratios — any
  wiggle is 100×+ the dividend — and are the clearest illustration that at this
  signal size the strategy is a coin-flip plus a rounding error.

Treat the tool as a measurement rig: it tells you, per event, exactly how much
of the move was dividend vs. noise, and whether the perp mispriced the drop.
The current sample (a handful of perp-covered events) is far too small to call a
real edge — the value is that it accumulates automatically as more ex-dates pass.

*Educational model, not investment advice.*
