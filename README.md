# WIC-S003 Stock Research Engine — The Black Scholes Bandits

Interpretable, point-in-time, eleven-factor research screen over the S&P 500 for the 2026–27 Wharton
Global High School Investment Competition (client: Laura Gao), plus a walk-forward backtest that runs the
**same production code** at every historical month-end.

> **Model role: MODEL SUPPORT.** A rank means "research this next" — never "buy". The engine places no
> orders, has no BUY state, and does not size positions. WInS availability is unchecked for every name.

## Quick start

```bash
pip install -r requirements.txt
export WIC_SEC_USER_AGENT="Your Name your@email.com"   # SEC fair-access requirement (never saved)
python -m wic all            # acquire snapshot -> screen -> backtest -> reproduce & verify
python -m pytest -q          # 50 offline tests (synthetic fixtures only)
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
`source_map.csv`, `lineage.jsonl`, `model_gate_memo.md`, `VALIDATION.json`, `STATUS.json`,
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
| `wic/sources/` | Wikipedia universe, PIT membership, SEC companyfacts, Yahoo prices |
| `wic/snapshot.py` | Acquisition, sealing and verification of input snapshots |
| `wic/accounting/` | XBRL concept routes and point-in-time normalization |
| `wic/factors.py` | The eleven factor outcomes |
| `wic/scoring.py` | Sector percentiles, composite, ranking, diversified view |
| `wic/cross_section.py` | Eligibility, duplicate share classes, resilience, research states |
| `wic/sensitivity.py` | Predeclared sensitivity suite and factor correlations |
| `wic/validate.py` | Independent validator |
| `wic/pipeline.py` | Live screen artifacts and model-gate memo |
| `wic/backtest/` | Walk-forward engine, metrics and report |
| `config/competition_v1.yaml` | All thresholds (changes require a logged model change) |
| `docs/MODEL_CHANGE_LOG.md` | Every deviation from spec v1.1, with reasons |
| `docs/PRIOR_BUILD_AUDIT.md` | Why the handed-off build produced zero rankings |
| `docs/reference/` | Controlling specification and model-gate memo |

## Limits

Public research sources only (Wikipedia, SEC XBRL, Yahoo via yfinance) — not licensed S&P DJI or vendor
data. Automated XBRL mapping is transparent but imperfect; flagged conventions are published per company.
Past simulated performance does not predict future returns.
