# WIC-S003 Stock Research Engine — The Black Scholes Bandits

Interpretable, point-in-time, eleven-factor research screen over the S&P 500 for the 2026–27 Wharton
Global High School Investment Competition (client: Laura Gao), plus a walk-forward backtest that runs the
**same production code** at every historical month-end.

> **Model role: MODEL SUPPORT.** A rank means "research this next" — never "buy". The engine places no
> orders, has no BUY state, and does not size positions. WInS availability is unchecked for every name.

## Latest validated run — cutoff 2026-10-19 (market close)

Universe: Wikipedia revision [1380159481](https://en.wikipedia.org/w/index.php?oldid=1380159481)
(2026-10-14, 503 constituents; cross-checked identical to the `datasets/s-and-p-500-companies` mirror).
390 eligible, **260 complete 11-factor scores**, independent validator passed, byte-for-byte reproduction
verified. Outputs: `outputs/screen/sp500_2026-10-19_current__stock-research-competition-v1.2__cfgbddebc2e350e/`.

| # | Ticker | Company | Sector | Composite | Quality | Valuation | Growth | Momentum | Risk | Core policy |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---|
| 1 | INCY | Incyte | Health Care | 86.4 | 95.9 | 90.2 | 90.4 | 77.5 | 60.0 | pass |
| 2 | EXPE | Expedia Group | Consumer Discretionary | 79.5 | 90.2 | 86.2 | 81.0 | 87.0 | 16.0 | pass |
| 3 | MU | Micron Technology | Information Technology | 76.7 | 90.6 | 88.1 | 48.6 | 97.3 | 27.7 | pass |
| 4 | NVDA | Nvidia | Information Technology | 73.0 | 86.0 | 44.1 | 97.3 | 50.1 | 89.2 | pass |
| 5 | MO | Altria | Consumer Staples | 72.6 | 86.2 | 84.1 | 41.1 | 69.4 | 78.8 | pass |
| 6 | SNDK | Sandisk | Information Technology | 72.5 | 92.1 | 78.9 | 48.6 | 94.3 | 5.1 | outside (FCF history) |
| 7 | DXCM | Dexcom | Health Care | 72.2 | 89.7 | 38.3 | 90.1 | 75.8 | 44.2 | pass |
| 8 | DECK | Deckers Brands | Consumer Discretionary | 69.5 | 91.6 | 90.2 | 90.6 | 16.0 | 26.6 | outside (composite < 70) |
| 9 | PM | Philip Morris International | Consumer Staples | 69.3 | 83.2 | 32.4 | 80.9 | 82.7 | 51.5 | outside (composite < 70) |
| 10 | DAL | Delta Air Lines | Industrials | 69.1 | 41.9 | 97.3 | 82.1 | 84.1 | 37.7 | outside (composite, quality) |

Ranks 11–20: ADP, ROST, BMY, EIX, SNA, CAH, TGT, KO, VRTX, GD. Every ±5-point family-weight shift keeps
≥ 80% of the Top 20 (Spearman ≥ 0.986). Communication Services, Energy and Materials are unranked under
the 20-valid-peer rule (see `docs/MODEL_CHANGE_LOG.md`). Ranks are research priorities, not buy signals.

### Walk-forward backtest (Feb 2013 → Oct 2026, 166 monthly rebalances, net of 10 bps costs)

Outputs: `outputs/backtest/sp500_2026-10-19__backtest__cfgbddebc2e350e/` (`BACKTEST_REPORT.md`, charts, daily returns, holdings).

| Book | CAGR | Vol | Sharpe | Max DD | vs scored universe (excess CAGR / IR) |
|---|---:|---:|---:|---:|---:|
| Top 10 (EW) | 12.6% | 18.7% | 0.63 | −38.2% | −0.4% / −0.01 |
| Top 10 sector-capped | 12.5% | 18.4% | 0.63 | −38.5% | −0.5% / −0.02 |
| Top 20 (EW) | 14.2% | 17.7% | 0.74 | −39.9% | +1.2% / +0.16 |
| Best quintile (Q1) | 14.3% | 16.8% | 0.77 | −36.1% | +1.3% / +0.20 |
| Worst quintile (Q5) | 13.6% | 20.8% | 0.63 | −44.0% | +0.6% / +0.17 |
| Scored universe (EW) | 13.0% | 16.9% | 0.70 | −36.9% | — |
| SPY | 14.6% | — | 0.79 | −33.7% | — |
| RSP (equal-weight S&P 500) | 12.0% | — | 0.64 | −39.0% | — |

**Honest read:** the composite's mean monthly rank IC is +0.009 (t = 0.93, 57% of months positive) —
not statistically significant. The broad top of the ranking (Top 20 / Q1) beat the scored universe by about
1.2–1.3% a year with Sharpe 0.74–0.77, but the quintiles are not monotonic and the concentrated Top 10 added
nothing. Cap-weighted SPY beat every equal-weight book, largely due to mega-cap technology in 2023–2025. This
supports the model-gate decision: **MODEL SUPPORT** (research prioritisation), **not** an alpha claim. The
weights were not, and should not be, re-tuned to improve these numbers. Survivorship: on average 75 of ~503
members per month lacked Yahoo price history (146 in 2013 → 1 in 2026); see `rebalance_coverage.csv`.

## Quick start

```bash
pip install -r requirements.txt
export WIC_SEC_USER_AGENT="Your Name your@email.com"   # SEC fair-access requirement (never saved)
python -m wic all            # acquire snapshot -> screen -> backtest -> reproduce & verify
python -m pytest -q          # 64 offline tests (synthetic fixtures only)
```

Individual steps: `python -m wic acquire [--cutoff YYYY-MM-DD]`, `python -m wic screen`,
`python -m wic backtest`, `python -m wic verify --run outputs/screen/<run_id>`.

Or run **Actions → research-run → Run workflow** on GitHub: it acquires live data, runs everything,
verifies reproducibility and commits the sealed snapshot and outputs back to the branch.

## How it works

```
acquire (network, once)          everything else (offline, deterministic)
───────────────────────          ─────────────────────────────────────────────────────────
Wikipedia revision @ cutoff ─┐   snapshot ──► accounting (PIT TTM, debt, claims, shares) ──┐
SEC XBRL companyfacts ───────┼─► MANIFEST  ► market factors (momentum, vol, drawdown) ─────┤
Yahoo daily prices ──────────┤   (sha256)   ► sector midrank percentiles (20-peer min) ◄───┘
PIT membership history ──────┘              ► composite → Top 20 / Top 10 / sector-capped view
                                            ► independent validator → publication gates
                                            ► sensitivity suite, coverage, lineage, memo
                                            ► walk-forward backtest (same code, each month-end)
```

| Family (weight) | Metric | Weight | Better |
|---|---|---:|---|
| Quality (30%) | ROIC = EBIT·(1−t) / avg invested capital | 12% | Higher |
| | FCF margin | 10% | Higher |
| | Net debt / EBITDA | 8% | Lower |
| Valuation (20%) | FCF yield | 10% | Higher |
| | EV / EBIT | 10% | Lower |
| Growth (20%) | Revenue CAGR 3Y | 10% | Higher |
| | EPS CAGR 3Y (split-adjusted) | 10% | Higher |
| Momentum (20%) | 12–1 month total return | 12% | Higher |
| | 6–1 month total return | 8% | Higher |
| Risk (10%) | 252-day volatility | 5% | Lower |
| | 252-day max drawdown | 5% | Lower |

Scoring (spec v1.1 §12, unchanged): within each GICS sector, valid values only, ≥ 20 peers, 5/95
winsorization, ascending midranks, `p = 100·(rank − 0.5)/n`, reversed for lower-is-better; explicit
economic sentinels (EBIT ≤ 0, EBITDA ≤ 0, non-positive EPS endpoint) score 0. **All eleven outcomes are
required**; nothing is imputed and missing weight is never redistributed. Financials and Real Estate are
outside the standard model.

## Why the outputs are verifiable

1. **Sealed inputs.** `acquire` is the only network step. It writes `data/snapshots/sp500_<cutoff>/` with
   the Wikipedia revision id + raw payload, SEC payload hashes per issuer, prices and a `MANIFEST.json`
   of SHA-256 hashes. Any edit to the snapshot is detected and the run refuses to start.
2. **Lineage.** Every accounting input in `lineage.jsonl` names its XBRL concept, route, accession number
   and filing date, so any number can be checked against the filing on EDGAR.
3. **Independent validator.** `wic/validate.py` re-derives every percentile, family score, composite and
   rank from the published `factor_values.csv` with separate code and fails the publication gate on any
   mismatch, direction violation or source date after the cutoff.
4. **Byte-for-byte reproduction.** `python -m wic verify` re-runs the screen from the snapshot and
   compares the SHA-256 of every output against `run_manifest.json`.
5. **Fail closed.** If a gate fails, the Top 10 / Top 20 files are deleted and `STATUS.json` says
   `NO VALIDATED RANKING AVAILABLE` with the blockers.

## Outputs

`outputs/screen/<run_id>/`: `priority_queue_top10.csv`, `research_queue_top20.csv`,
`diversified_research_view_top10.csv`, `ranked_universe.csv`, `factor_values.csv`, `universe_audit.csv`,
`coverage_report.csv`, `missing_reasons.csv`, `sensitivity_results.csv`, `factor_correlation.csv`,
`source_map.csv`, `lineage.jsonl`, `priority_queue_risk.json`, `model_gate_memo.md`, `VALIDATION.json`, `STATUS.json`,
`run_manifest.json`.

`outputs/backtest/<run_id>/`: `BACKTEST_REPORT.md` (tables + charts), `BACKTEST_SUMMARY.json`, daily/monthly
net and gross returns, holdings per rebalance, turnover, rank-IC series, per-rebalance coverage.

## Backtest design

Month-end rebalancing from 2013; universe = S&P 500 members **on that date** (fja05680/sp500 point-in-time
list) with GICS/CIK labels from the latest Wikipedia revision on or before the date; fundamentals only from
filings made before the date; equal-weight Top 10, Top 20, sector-capped Top 10, score quintiles, the scored
universe and SPY / RSP benchmarks; 10 bps one-way costs on traded notional; CAPM alpha with HAC t-stats,
information ratios, rank ICs per factor/family. Factor weights were fixed in the September 2026
specification and are **not** optimized on the backtest.

**Survivorship limitation:** Yahoo Finance lacks most delisted symbols, so historical members without
price history drop out of their months' universes (counted in `rebalance_coverage.csv`). Absolute returns
are biased upward; Top-10-vs-scored-universe comparisons share the same bias and are the more reliable read.

## Repository map

| Path | Purpose |
|---|---|
| `wic/sources/` | Wikipedia universe, PIT membership, SEC companyfacts (+ XBRL-instance supplement for filings companyfacts misses), Yahoo prices |
| `wic/snapshot.py` | Acquisition, sealing and verification of input snapshots |
| `wic/accounting/` | XBRL concept routes and point-in-time normalization |
| `wic/factors.py` | The eleven factor outcomes |
| `wic/scoring.py` | Sector percentiles, composite, ranking, diversified view |
| `wic/cross_section.py` | Eligibility, duplicate share classes, resilience, research states |
| `wic/sensitivity.py` | Predeclared sensitivity suite and factor correlations |
| `wic/validate.py` | Independent validator |
| `wic/risk.py` | Ex-ante risk profile of the Top 10 / diversified view (vol, beta, correlations) |
| `wic/pipeline.py` | Live screen artifacts and model-gate memo |
| `wic/backtest/` | Walk-forward engine, metrics and report |
| `config/competition_v1.yaml` | All thresholds (changes require a logged model change) |
| `docs/MODEL_CHANGE_LOG.md` | Every deviation from spec v1.1, with reasons |
| `docs/PRIOR_BUILD_AUDIT.md` | Why the handed-off build produced zero rankings |
| `docs/STRATEGY_OPERATIONS.md` | Monthly research cycle, turnover governance, hard limits |
| `docs/reference/` | Controlling specification and model-gate memo |

## Limits

Public research sources only (Wikipedia, SEC XBRL, Yahoo via yfinance) — not licensed S&P DJI or vendor
data. Automated XBRL mapping is transparent but imperfect; flagged conventions are published per company.
Past simulated performance does not predict future returns.
