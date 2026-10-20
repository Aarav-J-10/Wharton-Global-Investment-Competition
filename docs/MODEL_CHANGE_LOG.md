# Model Change Log — Competition V1.1 → V1.2

Required by spec §1.3. Owner: Aarav Jalan. Implementation: this repository.
Date: 2026-10-20. Reviewer: **pending Supervisor review** — none of these
changes has been approved by the Supervisor yet; they are logged so the review
can accept or reverse each one independently.

The eleven factors, their weights, directions, family weights, the 20-peer
sector minimum, 5/95 winsorization, midrank percentile formula, the
all-eleven-outcomes rule, no-renormalization, sentinel handling, tie-break
order, queue sizes, the sector cap, resilience thresholds and the sensitivity
suite are **unchanged**. Changes below are accounting-route and
infrastructure conventions only.

| # | Area | V1.1 behaviour (prior build) | V1.2 behaviour | Reason | Expected effect |
|---|---|---|---|---|---|
| 1 | Debt / finance leases | Required an affirmative same-date finance-lease route before debt was accepted; otherwise `LEASE_STATUS_UNRESOLVED` / `DEBT_COMPONENT_MISSING` | Debt = issuer-tagged interest-bearing borrowings via ordered routes (total tag → noncurrent + current → LTD incl. current + short-term → other notes). Finance-lease liabilities count only when inside the issuer's own debt tag, so they are never added twice. Operating leases excluded. | Prior rule blocked debt for ~190 of 381 companies (see `history/.../MISSING_REASONS.csv`), so ROIC, ND/EBITDA and EV/EBIT were almost never available and no sector reached 20 peers. | Large coverage increase. Slight understatement of debt for issuers that report finance leases outside debt tags (typically small). |
| 2 | Zero debt | Absence of a debt concept never proved zero | Debt inferred = 0 **only** if the issuer tagged no borrowing concept at the balance-sheet date **and** none with a non-zero value in the prior two years. Flag `DEBT_ZERO_INFERRED` is published per company. | Debt-free issuers simply do not tag debt. Two-year look-back prevents a dropped tag being read as zero. | Debt-free issuers become scoreable; transparent flag. |
| 3 | Preferred / NCI | Unknown preferred/NCI blocked EV (`PREFERRED_STATUS_UNRESOLVED` 39 cases) | Taken from `PreferredStockValue*` / `MinorityInterest` (or total-minus-parent equity). If the issuer reports no such balance: 0, flagged `PREFERRED_NOT_REPORTED` / `NCI_NOT_REPORTED`. | Issuers tag these balances when they exist; requiring explicit zero evidence is not achievable from XBRL. | EV coverage increase. |
| 4 | Tax rate for ROIC | TTM effective rate, else blocked | TTM effective (0–50%) → 3-fiscal-year aggregate effective (0–50%) → blocked. When TTM EBIT ≤ 0, NOPAT = EBIT (no tax shield). | Spec §10.2 forbids a universal rate; reported-evidence fallback keeps it company-specific. Loss-makers need no rate. | Fewer `TAX_RATE_UNDEFINED`; still no statutory plug. |
| 5 | EBIT fallback | `OperatingIncomeLoss` only | If no operating-income tag: pretax income + interest expense (route recorded). | Several issuers (e.g. utilities, some industrials) omit an operating-income subtotal. | Coverage increase; route visible in lineage. |
| 6 | D&A fallback | Combined D&A tag only; component disagreement blocked | Combined tag → `Depreciation` + `AmortizationOfIntangibleAssets` → depreciation only (flagged route). | Common reporting variation. | EBITDA coverage increase. |
| 7 | TTM construction | Several routes required four discrete quarters | FY value → fiscal-YTD + prior FY − prior-year YTD (same duration) → four contiguous quarters (Q4 = FY − 9M allowed). Never Q1+H1+9M+FY. | Cash-flow statements are YTD-only in 10-Qs; the bridge is exact for compatible periods. | Fixes ~75 `TTM_INCOMPLETE` FCF cases. |
| 8 | Shares / market cap | Complete share-class evidence required | Cover-page shares (summed per filing) cross-checked within ±25% of weighted diluted shares; else balance-sheet shares; else weighted diluted (flagged). Restated to the price series' split basis. | Market cap must use the same split basis as the price; XBRL companyfacts omits dimensioned class facts. | Market-value metrics available; split errors prevented. |
| 9 | EPS history | As reported | EPS divided by the product of splits after each value's filing date. | Pre-split EPS would fabricate growth collapses/explosions. | Correct EPS CAGR across splits. |
| 10 | Filing availability | Filing date ≤ cutoff | Filing usable from the day after its SEC filing date (`filing_lag_days: 1`). | Filings accepted after the close must not drive same-day decisions in the backtest. | Conservative; negligible for the live screen. |
| 11 | Universe source | Wikipedia revision pinned at cutoff (automatic, Oct 8 authorization) | Same, plus a fallback to the GitHub-hosted Wikipedia-derived list (`fja05680/sp500`) recorded as `FALLBACK_PUBLIC_RESEARCH_SOURCE` if Wikipedia is unreachable. | Resilience; source class always recorded in `SOURCES.json`. | None when Wikipedia is reachable. |
| 12 | Market data provider | `REQUIRED_INPUT` | Yahoo Finance via `yfinance`; `Adj Close` (split + dividend adjusted) is the total-return index; raw close reconstructed from split events. | A provider is required to run; the prior build already targeted Yahoo. | Live runs possible. Provider is free/unlicensed — see limitations. |
| 13 | Historical backtest | Deferred (§3.3) | Point-in-time walk-forward backtest added, using the production scoring path. | Explicit user request (2026-10-20). Weights are **not** fitted to it. | Evidence on signal quality; see survivorship limits. |

### Changes made while auditing the first live run (2026-10-20)

| # | Area | Problem found in live data | V1.2 behaviour | Expected effect |
|---|---|---|---|---|
| 14 | SEC source completeness | SEC companyfacts API omitted 93 recent 10-K/10-Q filings (e.g. Coca-Cola's 10-Q filed 2026-07-29), leaving 48 issuers falsely `STALE_INPUT`. | Every 10-K/10-Q listed in the issuer's EDGAR submissions index from the last two years but absent from companyfacts is read from the filing's own XBRL instance (non-dimensional facts only, as companyfacts). Each supplemented filing is logged with URL and SHA-256 in `sec_filing_supplement.csv`. | Current fundamentals for all filers; primary source unchanged (SEC). |
| 15 | Share count corroboration | Issuer tagging-scale errors: McDonald's weighted diluted shares tagged as 711.1, Waters as 98.2 billion. A single cross-check propagated these into market cap. | A share count (cover page → balance sheet → weighted diluted) is accepted only if an independent source (balance-sheet shares or weighted diluted shares of this or the prior three quarters) agrees within 25% after split adjustment; values below 100,000 are rejected as implausible. Otherwise `SHARES_MAPPING_REVIEW` (blocked, not guessed). | Prevents absurd FCF yields / EV multiples (MCD 44,975× → blocked; WAT corrected to $42.7B). |
| 16 | Revenue tag consistency | Some issuers use `Revenues` for a sub-line (General Mills $2.0B vs $19.5B total; Emerson 2022), producing 111–121% fake CAGRs. | Primary revenue tag = the alternative with the largest value at the latest fiscal year; used for both TTM and the 3-year history. Other tags may fill a missing year only if they match the primary within 2% in a year both report (EPS: diluted first, 3%). | Correct revenue growth; no cross-tag splicing. |
| 17 | Cash-flow tag switches | Issuers switching capex/CFO/D&A tags between the 10-K and 10-Qs could not be bridged (e.g. Marriott). Verizon tags capex as `PaymentsToAcquireOtherProductiveAssets`. | After single-tag routes fail, a TTM bridge across equivalent cash-flow tags (highest priority per period) is allowed and flagged `TTM_ACROSS_EQUIVALENT_TAGS`; `PaymentsToAcquireOtherProductiveAssets` added as the lowest-priority capex tag. Never applied to revenue. | More FCF coverage, flagged per company. |

## Observed effect (live run, cutoff 2026-10-19)

| Measure | Prior build (2026-10-02 replay) | V1.2 live run |
|---|---:|---:|
| Eligible companies | 381 | 390 |
| ROIC valid | 40 | 339 |
| Net debt / EBITDA valid | 43 | 343 |
| EV / EBIT valid | 12 | 337 |
| Complete 11-factor scores | **0** | **260** |
| Sectors with a ranked company | 0 | 6 of 9 in-scope |

Sectors that remain unranked under the unchanged 20-peer rule: Communication Services (19 eligible),
Energy (21 eligible, ≤ 18 valid on several metrics) and Materials (24 eligible, 16–17 valid on EPS
growth / EV/EBIT). The `peer_min_15` sensitivity variant would add 19 names (279 complete); changing the minimum is a
Supervisor decision and has **not** been made.
