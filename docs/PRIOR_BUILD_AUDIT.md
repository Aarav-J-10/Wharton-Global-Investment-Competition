# Audit of the handed-off build (WIC_S003_COMPETITION_V1_FINAL.py)

Source: `WIC_S003_CLAUDE_HANDOFF_UNDER_30MB.zip` (prepared 2026-10-20).

## What the handoff established

- File SHA256 `81d08709…`, embedded 36-module bundle `2dbe7388…`, 253 offline tests passing (Oct 8, Windows/Python 3.12).
- Automatic Wikipedia universe acquisition worked (revision 1376729338, 503 securities, cutoff 2026-10-07).
- The live smoke run was **BLOCKED at YAHOO_CONNECTIVITY** (TLS verification failure).
- The two full 381-company frozen replays (older bundle `2002c649…`) passed 867,861 integrity checks each and
  produced **0 complete scores, no Top 10**.

## Why it produced zero rankings

From the replay's `MISSING_REASONS.csv` (381 companies):

| Factor | VALID | Dominant blockers |
|---|---:|---|
| ROIC | 40 | DEBT_COMPONENT_MISSING 195, EBIT_HISTORY_INCOMPLETE 54, ROUTE_CONFLICT 28, LEASE_STATUS_UNRESOLVED 28 |
| Net debt / EBITDA | 43 | DEBT_COMPONENT_MISSING 150, DA_HISTORY_INCOMPLETE 52, ROUTE_CONFLICT 45 |
| EV / EBIT | 12 | DEBT_COMPONENT_MISSING 189, PREFERRED_STATUS_UNRESOLVED 39, LEASE_STATUS_UNRESOLVED 29 |
| FCF margin | 234 | TTM_INCOMPLETE 75 (capex required four discrete quarters) |

With ≤ 43 valid values spread across ~9 sectors, no sector-metric reached the 20-peer minimum, so every
company was `SCORING_UNAVAILABLE`. The integrity machinery was sound; the accounting route policy was so
strict that the model could never produce an output. Specific defects:

1. **Debt routes**: a balance-sheet debt total was rejected unless a same-date "affirmative finance-lease
   route" also existed, and same-filing alternative routes that disagreed were treated as conflicts instead
   of being resolved by priority.
2. **Preferred/NCI**: required explicit liquidation/book/zero evidence, which issuers without preferred stock
   never tag.
3. **TTM**: capex/EBIT/D&A required four discrete quarters, but 10-Q cash-flow statements are year-to-date
   only — the standard YTD bridge was not implemented.
4. **Market data**: the Yahoo client failed TLS in the recorded environment, so momentum/risk were never
   computed live.
5. **Monolith**: 176 KB single-file wrapper with base85-embedded modules made review and diffing hard.

## What this repository changes

A clean package (`wic/`) implementing spec v1.1 with the route-policy changes logged in
`MODEL_CHANGE_LOG.md`. The approved model (factors, weights, peer minimum, winsorization, percentile
formula, no imputation, no renormalization) is unchanged. Integrity features retained: hash-sealed
snapshots, fail-closed source errors, independent validator, publication gates, stale-queue removal,
deterministic outputs and a byte-for-byte reproduction check.
