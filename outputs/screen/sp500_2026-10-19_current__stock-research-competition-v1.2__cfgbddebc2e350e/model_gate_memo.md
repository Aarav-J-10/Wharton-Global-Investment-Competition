# WIC-S003 Model Gate Memo — sp500_2026-10-19_current__stock-research-competition-v1.2__cfgbddebc2e350e

**Decision:** MODEL_SUPPORT

This screen ranks companies for research priority. It is **not** a return forecast, an order, or investment approval. There is no BUY state.

## Run facts

- Cutoff: 2026-10-19 (market session used: 2026-10-19)
- Universe source: Wikipedia: List of S&P 500 companies revision 1380159481 (2026-10-14T03:35:16Z); AUTO_REPRODUCIBLE_PUBLIC_RESEARCH_SOURCE (not licensed S&P DJI data)
- Constituents: 503; eligible for standard model: 390; complete 11-factor scores: 259 (66.41% of eligible)
- Publication gates: snapshot_hashes_verified=True, independent_validator_passed=True, at_least_10_complete_scores=True, no_source_dates_after_cutoff=True

## Coverage by sector

| Sector | Constituents | Eligible | Complete |
|---|---:|---:|---:|
| Communication Services | 22 | 19 | 0 |
| Consumer Discretionary | 47 | 47 | 33 |
| Consumer Staples | 34 | 33 | 27 |
| Energy | 21 | 21 | 0 |
| Financials | 76 | 0 | 0 |
| Health Care | 60 | 60 | 54 |
| Industrials | 83 | 81 | 65 |
| Information Technology | 75 | 74 | 60 |
| Materials | 24 | 24 | 0 |
| Real Estate | 30 | 0 | 0 |
| Utilities | 31 | 31 | 20 |
| ALL | 503 | 390 | 259 |

## Priority queue (raw rank)

| Rank | Ticker | Company | Sector | Composite | Quality | Core policy |
|---:|---|---|---|---:|---:|---|
| 1 | INCY | Incyte | Health Care | 86.4 | 95.9 | CORE_POLICY_PASS |
| 2 | EXPE | Expedia Group | Consumer Discretionary | 79.5 | 90.2 | CORE_POLICY_PASS |
| 3 | MU | Micron Technology | Information Technology | 76.7 | 90.6 | CORE_POLICY_PASS |
| 4 | NVDA | Nvidia | Information Technology | 73.0 | 86.0 | CORE_POLICY_PASS |
| 5 | MO | Altria | Consumer Staples | 72.6 | 86.2 | CORE_POLICY_PASS |
| 6 | SNDK | Sandisk | Information Technology | 72.5 | 92.1 | OUTSIDE_CORE_POLICY |
| 7 | DXCM | Dexcom | Health Care | 72.2 | 89.7 | CORE_POLICY_PASS |
| 8 | DECK | Deckers Brands | Consumer Discretionary | 69.5 | 91.6 | OUTSIDE_CORE_POLICY |
| 9 | PM | Philip Morris International | Consumer Staples | 69.3 | 83.2 | OUTSIDE_CORE_POLICY |
| 10 | DAL | Delta Air Lines | Industrials | 69.1 | 41.9 | OUTSIDE_CORE_POLICY |

Diversified research view (max 3 per sector): INCY, EXPE, MU, NVDA, MO, SNDK, DXCM, DECK, PM, DAL

## Stability

- ±5pp family-weight shifts: min Top-20 overlap 80%, min Spearman 0.986, review flags 0.
- Interpretation: high stability; exact ordinal positions (e.g. rank 3 vs 5) should not be over-interpreted.
- Factor correlations above 0.8: none

## Limits

- Universe labels come from a public Wikipedia revision, not licensed S&P DJI data.
- Fundamentals come from SEC XBRL companyfacts with automated concept routes; flagged conventions (debt-zero inference, NCI/preferred not reported) are listed per company in ranked_universe.csv `accounting_flags` and lineage.jsonl.
- Financials and Real Estate are outside the standard model (not an investment rejection).
- WInS platform availability is unchecked for every name (WINS_AVAILABILITY_UNCHECKED).
- A high score means 'research this next', never 'buy'.
