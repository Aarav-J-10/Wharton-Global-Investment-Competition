# Operating the screen (research process, not a trading system)

## Role in Laura Gao's portfolio

The screen supports the **growth sleeve** research process. Under WIC-S007 the initial WInS structure is
about VTI 40% / VXUS 25% / VGIT 25% / SGOV 5% / cash 5%. A direct stock, if the Investment Committee ever
approves one, **replaces part of existing diversified growth exposure (VTI/VXUS)** — it does not add equity
risk. Priority remains Operating Commitment > Financial Flexibility > Facility Contribution, and WInS results
never feed Laura's long-term Goal Engine.

## Monthly cycle

| When | Step | Command / artifact |
|---|---|---|
| First weekday after month-end | Acquire sealed snapshot, screen, backtest refresh, reproduction check | `research-run` workflow or `python -m wic all` |
| Same day | Check `STATUS.json` = `RANKING_PUBLISHED` and `VALIDATION.json` passed | gates fail → no queue is published |
| Same day | Read `model_gate_memo.md`, `coverage_report.csv`, `sensitivity_results.csv` | stability flags, sector coverage |
| Within a week | Pick 3–4 names from the Top 10 / diversified view for deep research | dossiers: thesis, counter-case, cash-flow and balance-sheet review, valuation, invalidation triggers |
| IC meeting | Portfolio-fit decision (owner: allocation / IC) | `priority_queue_risk.json` supplies beta, vol, correlation, sector mix |
| Event-driven | Re-run after a material filing for a researched name | `python -m wic all --cutoff <date>` |

## Turnover governance (from the model-gate memo §12)

1. Re-rank monthly for research prioritisation, not daily.
2. Do not replace a researched holding merely because its rank slipped a few places; require a documented
   thesis, risk or valuation change, or a materially superior alternative.
3. `OUTSIDE_CORE_POLICY` names (failed resilience precheck) may still be researched manually, but are not
   auto-promoted.
4. Exact ordinal positions (rank 3 vs 5) are not meaningful; sensitivity results show which names are robust.

## Reading the backtest

- Weights were fixed ex ante; the backtest is evidence about the screen, not an optimisation target.
- The most reliable comparison is Top 10 vs the scored universe (same data/survivorship exposure).
- A quintile spread and positive rank IC across sub-periods matter more than a single CAGR figure.
- 10 bps one-way costs are included; taxes and market impact are not.

## Hard limits

No orders, no WInS logins, no BUY state, no position sizing by score, no leverage, no shorts, no
derivatives, no stop-loss/tactical layer. A failed or incomplete run is a valid output.
