# WIC-S003 — Final Stock Research Engine Specification

**Version:** 1.1 — Competition V1 Finalized Specification  
**Date:** 29 September 2026  
**Team:** The Black Scholes Bandits  
**Client:** Laura Gao  
**Primary technical owner:** Aarav Jalan  
**Model role:** MODEL SUPPORT only  
**Purpose:** Build a reproducible, interpretable equity-research system that ranks current S&P 500 companies for deeper research, supports disciplined company analysis, and sends evidence-backed research candidates to the team's investment-committee process. It is not a trading system, allocation engine, Goal Engine, or autonomous stock picker.

---

## 0. Implementation instructions for Aarav and any coding assistant

This file is the **finalized full specification for Competition V1**. It replaces the earlier WIC-S003 implementation design where this file conflicts with it. It does **not** replace passed WIC-S001, WIC-S002, or WIC-S007. Those remain controlling for client strategy, long-term goal modelling, and the current WInS implementation.

### 0.1 Do not build the entire system in one coding pass

Aarav may prefer one-shot coding, but this system should **not** be implemented as one giant pass. The highest-risk errors are data-definition errors, scoring-direction errors, accounting mapping errors, and silent source failures. If valuation, report generation, monitoring, and research automation are built before the deterministic screen is proven correct, later outputs can look polished while inheriting bad inputs.

**Required implementation doctrine:**

1. Build one stage at a time.
2. Each stage may be generated in one coding response, but do not generate later stages until the current stage runs and its tests pass.
3. At the end of every stage, produce:
   - files created/modified;
   - exact commands run;
   - tests passed/failed;
   - output artifacts created;
   - unresolved inputs;
   - any deviation from this specification;
   - a short checkpoint for Supervisor review.
4. Never silently change a threshold, factor, source, universe, queue size, or formula to make the code run.
5. If a required external input is not supplied, stop that dependency and report it. Do not guess.
6. Synthetic fixtures may be used to prove logic. Synthetic values must never be presented as real research.
7. A failed or incomplete run is a valid output. Do not fill missing data with invented values.
8. The code must never place an order, log into WInS, alter a portfolio, or generate a claim that a trade occurred.

### 0.2 Stage order

**Stage 0 — Repository scaffold, configuration, contracts, and tests**  
**Stage 1A — Current S&P 500 universe + market-data pipeline**  
**Stage 1B — Fundamental-data normalization + eleven factors**  
**Stage 1C — Cross-sectional scoring + Top 20 / Top 10 queues**  
**Stage 1D — Sensitivity + source/coverage audit + model-gate package**  

Completion of Stages 0–1D is the **WIC-S003 competition checkpoint requirement**.

Only after Stage 1 passes:

**Stage 2 — Structured company research dossiers for 3–4 names**  
**Stage 3 — Analyst-reviewed valuation module for researched names**  
**Stage 4 — Portfolio-fit interface and optional monitoring improvements**

Historical replay, advanced automation, optional valuation distributions, tactical trading logic, and large monitoring infrastructure are deferred unless the Supervisor later approves them.

---

# 1. Source authority and change control

## 1.1 Controlling source order

When two sources conflict, use this order:

1. **Current official 2026–27 Wharton competition materials.**
2. **Current explicit Supervisor / Coordinator decisions.**
3. **Passed internal artifacts:**
   - WIC-S001 — Client Strategy Specification — PASS;
   - WIC-S002 — Laura Goal Engine — PASS;
   - WIC-S007 — Initial WInS Implementation Packet — PASS.
4. **Current WIC-S003 approved design decisions and current team evidence.**
5. **Older internal planning documents, chats, brainstorming, and prior algorithm proposals.**
6. **Current primary external research and data-source documentation.**
7. **New engineering conventions introduced in this specification.**

Official rules override any user preference, old team note, or model convention that conflicts with them.

## 1.2 Status labels

Every numerical or procedural rule must be classified as one of:

- **CASE FACT** — fixed by the official Laura Gao case.
- **COMPETITION RULE** — fixed by current official competition/WInS materials.
- **PASSED STRATEGY RULE** — established by a passed team artifact.
- **COMPETITION V1 POLICY** — an explicit implementation choice in this specification; adjustable only through a logged model change.
- **ENGINEERING CONVENTION** — a definition needed for deterministic calculation.
- **EXTERNAL INPUT** — supplied by a data source, current platform check, Goal Engine, allocation process, or user.
- **DEFERRED** — intentionally outside the Competition V1 pass requirement.

A V1 policy is not evidence that the threshold is universally correct. Never alter one merely to admit a favored company.

## 1.3 Change log requirement

Every material change after v1.1 must record:

- old value/rule;
- new value/rule;
- reason;
- expected effect;
- observed effect after rerun;
- owner;
- reviewer;
- date;
- whether Supervisor approval is required.

Material changes include universe definition, factor definitions, factor weights, missing-data policy, scoring method, queue size, resilience gates, source adapters, valuation gates, and model status.

---

# 2. Laura Gao: client contract translated into stock-research behavior

## 2.1 Fixed client facts

The stock engine must respect these case facts:

- Laura contributes **$300,000 at the beginning of 2027**.
- Laura contributes an additional **$150,000 at the beginning of 2028**.
- There are **no portfolio withdrawals before 2033**.
- Beginning in 2033, Laura must fund **ten annual fixed $50,000 operating payments through 2042**.
- The operating reserve is established at the beginning of 2033 before the first payment and before any facility contribution.
- Laura must preserve appropriate financial flexibility.
- The facility contribution is residual, not predetermined.
- Laura begins co-sponsor communication in 2031 and needs a credible range for a possible 2033 facility contribution.
- WInS performance does not change Laura's long-term starting capital or Goal Engine projections.

## 2.2 Passed priority hierarchy

The stock engine is subordinate to:

**Operating Commitment > Financial Flexibility > Facility Contribution**

The engine must never reverse this hierarchy.

A high stock score must never be used to justify:

- weakening the operating reserve;
- increasing total equity risk solely to seek a larger facility contribution;
- transferring WInS gains into Laura's long-term projection;
- changing Goal Engine assumptions;
- creating a return target needed to reach a desired facility amount.

## 2.3 What the stock engine is allowed to conclude

Keep three conclusions separate:

1. **Business conclusion:** Is this company financially resilient and understandable enough to research seriously?
2. **Valuation conclusion:** Is the company attractively priced under documented, reviewed assumptions?
3. **Portfolio conclusion:** Would owning it fit Laura's current growth-risk budget and existing exposures?

The stock engine owns conclusions 1 and 2. It provides evidence to conclusion 3. The integrated allocation / investment-committee process owns conclusion 3.

## 2.4 Current WInS implementation context

WIC-S007 passed with the initial WInS implementation approximately:

- VTI: 40%
- VXUS: 25%
- VGIT: 25%
- SGOV: 5%
- Cash: about 5%

Growth sleeve: 65%  
Protection sleeve: 30%  
Liquidity: about 5%

This is an initial WInS implementation, not final IPS policy.

### Direct-stock integration rule

**Default Competition V1 assumption:** a later individual-stock position normally replaces part of existing diversified growth exposure, especially VTI and/or VXUS, rather than increasing the total growth sleeve above its separately approved level.

The stock engine must not decide the replacement amount. It should output the candidate's business/valuation evidence, sector/geographic exposures, overlap risks, and research status. Allocation/IC decides whether any VTI/VXUS reduction is justified.

A direct stock may be researched even if no current capacity exists to buy it. Research approval and deployment capacity are different states.

---

# 3. Competition V1 scope

## 3.1 Required now

Competition V1 must deliver:

1. Current S&P 500 universe snapshot with a declared cutoff.
2. Deterministic eligibility and exclusion audit.
3. Eleven-factor current cross-sectional screen.
4. Sector-relative normalization where valid peer data exist.
5. Full factor/source coverage reporting.
6. Ranked eligible universe.
7. Top 20 research queue.
8. Top 10 priority queue.
9. Predetermined score/universe sensitivity analysis.
10. Reproducibility and arithmetic tests.
11. Source map and run manifest.
12. Model-gate memo concluding MODEL_SUPPORT / MODEL_REJECT as supported by the actual run.
13. Clear separation between research ranking and investment approval.

## 3.2 Required after Stage 1 passes

For 3–4 priority names, if time permits and the team chooses to continue:

- company research dossier;
- counter-case;
- cash-flow quality review;
- balance-sheet review;
- valuation assumptions prepared by an analyst;
- deterministic bear/base/bull valuation;
- risks and invalidation triggers;
- client role;
- obvious alternative comparison;
- readiness blockers.

## 3.3 Deferred from the WIC-S003 pass criterion

Do not put these on the current critical path:

- historical performance backtest;
- S&P Composite 1500 expansion;
- Random Forest, XGBoost, neural networks, or other ML stock predictors;
- sentiment scraping as an alpha layer;
- social-media signal scoring;
- Black-Litterman;
- automatic trading;
- broker/WInS login automation;
- position sizing by stock score;
- automated replacement trading;
- Monte Carlo DCF distributions;
- tactical short-horizon strategy;
- stop-loss/profit-cap system;
- complex scheduling/alert infrastructure;
- fully automated 12-month price-target generation;
- automatically generated official-submission prose.

These may be considered later only if the core competition work is already secure and the Supervisor approves expansion.

---

# 4. Known WInS rules and permission model

## 4.1 Known category-level rules

Current official project materials establish that WInS permits relevant categories including qualifying stocks, ETFs, government/Treasury bonds, and cash, while margin, short selling, crypto, derivatives, and other unapproved instruments are prohibited.

For the stock engine:

- research common stocks only;
- require raw current share price at or above the current WInS minimum-price rule;
- never propose short positions;
- never propose derivatives;
- do not infer platform availability solely from a market-data provider.

## 4.2 Per-security deployment status

Every researched stock has one of:

- `WINS_VERIFIED_AVAILABLE`
- `WINS_VERIFIED_UNAVAILABLE`
- `WINS_AVAILABILITY_UNCHECKED`

A research score may be calculated while availability is unchecked. A candidate cannot be called execution-ready until current platform availability is verified manually or by an approved permission source.

No research-engine result is an order.

---

# 5. Runtime inputs that are not allowed to be guessed

The architecture is final even if these operational inputs are not yet supplied.

## 5.1 Market-data provider

**Status: REQUIRED EXTERNAL INPUT before a live Stage 1 run.**

The team has not supplied a Supervisor-approved market-data provider/API in the current artifact set. Therefore this specification does not invent one.

Required capabilities:

- daily raw OHLC;
- split-adjusted price history;
- dividend/total-return treatment or enough fields to construct it correctly;
- raw volume;
- corporate-action metadata or a documented compatible adjustment policy;
- at least 13 months of history for current screening;
- stable timestamps and source IDs.

Until Aarav/user selects a provider, implement a `MarketDataAdapter` interface and use synthetic fixtures only.

## 5.2 Current S&P 500 membership source

**Status: REQUIRED EXTERNAL INPUT before production ranking.**

Use a dated, traceable current S&P 500 constituent snapshot. Do not hard-code an undated web list. Store provider, retrieved timestamp, effective/as-of date, and content hash.

If a current authoritative/traceable source cannot be obtained, stop the live ranking and report the dependency. Do not substitute a hand-selected list.

## 5.3 Sector classification

A sector label is required for sector-relative scoring. The provider/classification version must be logged.

Do not silently infer sectors from company names or mix incompatible classification systems in one run.

If the universe source provides a documented sector classification, preserve its source/version. If not, require a separate classification source.

## 5.4 Fundamental data

SEC EDGAR filings and XBRL/company facts are the preferred primary source for U.S. issuer fundamentals, subject to mapping/reconciliation rules in this specification.

Company-specific ambiguous/custom facts require original-filing review rather than automatic guessing.

---

# 6. Project structure

Recommended structure:

```text
stock_research/
  README.md
  pyproject.toml or requirements.txt
  config/
    competition_v1.yaml
  contracts/
    enums.py
    models.py
    validation.py
  adapters/
    universe_base.py
    market_base.py
    sec.py
    sector_base.py
    wins_permission.py
  storage/
    snapshots.py
    manifests.py
  identity/
    security_master.py
  accounting/
    mappings.py
    normalize.py
    periods.py
  eligibility/
    rules.py
  factors/
    fundamentals.py
    momentum.py
    risk.py
  scoring/
    normalize.py
    composite.py
    queues.py
  sensitivity/
    run_variants.py
  research/
    dossier.py
    evidence.py
    review.py
  valuation/
    fcff.py
    scenarios.py
    sensitivity.py
  reporting/
    exports.py
    markdown.py
  orchestration/
    run_current_screen.py
  tests/
    fixtures/
    unit/
    integration/
```

This is modularity for correctness, not complexity. Do not add distributed services, a vector database, background workers, or cloud infrastructure unless a concrete later need appears.

---

# 7. Canonical Competition V1 configuration

The following is the required starting configuration. Values marked V1 POLICY remain hypotheses rather than claims of optimality.

```yaml
schema_version: "1.1"
model_version: "stock-research-competition-v1.1"
mode: CURRENT_RESEARCH
base_currency: USD
market_timezone: America/New_York
report_timezone: Asia/Kolkata

universe:
  index_id: SP500
  snapshot_required: true
  security_type: COMMON_STOCK
  min_raw_close_usd: 5.0
  min_price_history_calendar_months: 13
  required_return_observations: 252
  required_annual_observations: 4
  exclude_financial_sector_from_standard_model: true
  exclude_reits_from_standard_model: true
  exclude_spacs_shells: true
  exclude_funds_etfs_preferreds_warrants_derivatives: true
  exclude_depositary_receipts_from_standard_model: true
  duplicate_issuer_share_class_policy: MOST_LIQUID_RESEARCH_CLASS

fundamentals:
  max_latest_quarter_age_days: 180
  max_latest_fy_age_days: 550
  require_point_in_time_publication_metadata: true
  no_silent_imputation: true

scoring:
  peer_level: SECTOR
  min_valid_peers_per_metric: 20
  winsor_quantiles: [0.05, 0.95]
  percentile_method: MIDRANK
  require_all_11_factor_outcomes: true
  missing_weight_policy: NO_RENORMALIZATION
  weights:
    roic: 0.12
    fcf_margin: 0.10
    net_debt_ebitda: 0.08
    fcf_yield: 0.10
    ev_ebit: 0.10
    revenue_cagr_3y: 0.10
    eps_cagr_3y: 0.10
    momentum_12_1: 0.12
    momentum_6_1: 0.08
    volatility_252: 0.05
    max_drawdown_252: 0.05

queues:
  research_queue_size: 20
  priority_queue_size: 10
  initial_deep_research_target: 4
  max_priority_names_same_sector: 3

resilience:
  enabled_for_deep_research_priority: true
  require_positive_ttm_ebit_cfo_fcf: true
  positive_fcf_years_of_latest_three: 2
  max_net_debt_ebitda: 4.0
  min_interest_coverage_if_interest_positive: 3.0
  composite_score_floor_for_auto_priority: 70.0
  quality_family_floor_for_auto_priority: 60.0

valuation:
  automatic_draft_valuation: false
  analyst_review_required: true
  forecast_years: 5
  min_wacc_terminal_growth_gap: 0.02
  min_base_margin_of_safety: 0.15
  max_bear_value_loss_fraction: 0.30
  sensitivity_wacc_shifts: [-0.02, -0.01, 0.0, 0.01, 0.02]
  sensitivity_terminal_growth_shifts: [-0.01, 0.0, 0.01]
  optional_uncertainty_module: false

reporting:
  current_screen_outputs_required: true
  company_cards_required_for_s003_pass: false
  target_price_required_for_s003_pass: false
  ai_thesis_generation_required: false

external:
  market_data_provider: REQUIRED_INPUT
  universe_provider: REQUIRED_INPUT
  sector_classification_provider: REQUIRED_INPUT
  goal_policy_id: null
  portfolio_snapshot_id: null
  wins_permission_snapshot_id: null
```

### 7.1 No silent default substitution

`REQUIRED_INPUT` means stop that production dependency. Do not replace it with a convenient service without recording the source choice and obtaining team approval where required.

---

# 8. Universe and eligibility

## 8.1 Competition V1 universe

Use the **current S&P 500 constituent universe as of the declared run cutoff**.

Reason: this preserves the current approved large-cap U.S. scope, materially reduces implementation burden versus the earlier Composite 1500 proposal, and remains broad enough for diversified stock discovery.

S&P Composite 1500 expansion is deferred. It may later be tested as a universe sensitivity, not silently substituted into V1.

## 8.2 Security-level eligibility order

For every source constituent:

1. Resolve issuer/security identity.
2. Confirm current membership at cutoff.
3. Confirm common-equity security type.
4. Confirm raw current close is at least the WInS minimum-price threshold.
5. Exclude categories outside this standard model: financials, REITs, SPAC/shells, funds/ETFs, preferreds, warrants, derivatives, and depositary receipts.
6. Resolve multiple ordinary share classes deterministically; retain excluded classes in the audit.
7. Require at least 13 calendar months of usable price history and 252 daily return observations for the main risk factors.
8. Require four comparable annual observations for three-year growth rates.
9. Require current compatible TTM and balance-sheet inputs for the fundamental factors.
10. Require source/freshness checks to pass.
11. Record WInS availability separately.

## 8.3 Statuses

Use distinct states:

- `ELIGIBLE`
- `OUTSIDE_STANDARD_MODEL`
- `DATA_BLOCKED`
- `SCORING_INCOMPLETE`
- `SCORED`

Do not call an unavailable accounting field a weak company result.

A company outside the standard model is not an investment rejection. It means this engine is not designed to compare it reliably.

## 8.4 Coverage audit is mandatory

Before interpreting ranks, export:

- source constituent count;
- resolved securities;
- duplicate classes removed;
- exclusions by reason;
- data-blocked count;
- complete-score count;
- complete-score percentage;
- complete-score count by sector;
- each factor's valid-count by sector;
- most common missing fields;
- most common mapping failures.

**No fixed minimum completion percentage is approved in advance.** The first production run must show the actual coverage. If coverage is poor or heavily sector-biased, the Supervisor decides whether mapping must be fixed before the ranks are decision-useful.

Do not lower data standards simply to increase the completion rate.

---

# 9. Point-in-time and data-integrity rules

## 9.1 Current research cutoff

Every run declares one cutoff timestamp. Use only information available by that cutoff.

For current screening:

- price data must come from the latest completed market session available under the provider's final-data convention;
- a filing/publication must have been publicly available before it can influence the run;
- fiscal period-end date alone is never the availability date;
- later restatements do not rewrite earlier stored runs;
- each source record must carry source/retrieval metadata.

## 9.2 Fundamental availability convention

For a filing with a reliable public timestamp, store:

- period end;
- filing/accession;
- publication/acceptance timestamp;
- run cutoff;
- source ID.

For current research, information must be public by cutoff and actually retrieved/processed by the run.

The code must not use a generic “45 days after quarter end” assumption when actual filing data exist.

## 9.3 Missing versus negative

Keep these distinct:

- missing EBITDA ≠ negative EBITDA;
- missing FCF ≠ negative FCF;
- missing EPS ≠ nonpositive EPS;
- unavailable sector peer set ≠ median score;
- retrieval outage ≠ bad company.

Missing data remains null with a reason. Economic weakness may receive a defined sentinel only where this specification explicitly allows it.

## 9.4 Snapshot immutability

Every production run stores:

- model/config version;
- cutoff;
- source identifiers;
- source hashes where permitted;
- input snapshot IDs;
- output hashes;
- test status;
- run status.

Do not overwrite past run artifacts.

---

# 10. Accounting normalization

All flow metrics are TTM unless explicitly annual. Balance-sheet values are point-in-time.

## 10.1 Canonical quantities

```text
FCF_screen = cash_flow_from_operations - cash_capex
EBIT = canonical GAAP operating income
EBITDA = EBIT + depreciation_and_amortization
Debt = current_interest_bearing_debt + noncurrent_interest_bearing_debt
Cash = unrestricted_cash_and_cash_equivalents
NetDebt = Debt - Cash
InvestedCapital = Debt + common_book_equity + preferred_book_capital + NCI_book_capital - Cash
AverageInvestedCapital = (IC_latest_quarter + IC_same_quarter_prior_year) / 2
NOPAT = EBIT * (1 - normalized_tax_rate)
MarketCap = complete current common-equity market capitalization
EV = MarketCap + Debt + preferred_claim_value + NCI_claim_value - Cash
```

Finance lease treatment must be consistent and counted once. If the chosen mapping cannot support a consistent treatment for a company, mark the relevant metric `NEEDS_MAPPING_REVIEW` rather than improvise.

## 10.2 Tax normalization

Do not silently insert a universal tax rate.

Use a defensible normalized corporate tax rate based on reported evidence and company/jurisdiction context. If no defensible current rate exists, ROIC is incomplete until reviewed.

## 10.3 Annual growth history

Three-year CAGR requires four annual observations:

```text
CAGR_3Y = (FY0 / FY_minus_3)^(1/3) - 1
```

Do not calculate a “three-year” CAGR from only three annual observations.

## 10.4 TTM construction

Where cash-flow statements report year-to-date values, derive discrete quarters only from compatible periods/vintages. Never sum Q1 + H1 + 9M + FY.

The implementation must retain a derivation record for reconstructed quarters.

---

# 11. Factor architecture

The approved family weights remain:

- Quality: 30%
- Valuation: 20%
- Growth: 20%
- Momentum: 20%
- Risk: 10%

The Competition V1 metric weights are:

| Family | Metric | Weight | Better direction |
|---|---|---:|---|
| Quality | ROIC | 12% | Higher |
| Quality | FCF margin | 10% | Higher |
| Quality | Net debt / EBITDA | 8% | Lower |
| Valuation | FCF yield | 10% | Higher |
| Valuation | EV / EBIT | 10% | Lower |
| Growth | Revenue CAGR 3Y | 10% | Higher |
| Growth | EPS CAGR 3Y | 10% | Higher |
| Momentum | 12–1 total return | 12% | Higher |
| Momentum | 6–1 total return | 8% | Higher |
| Risk | 252-session annualized volatility | 5% | Lower |
| Risk | 252-session maximum drawdown magnitude | 5% | Lower |

Weights sum to 100%.

## 11.1 Exact definitions

### ROIC

```text
ROIC = NOPAT / AverageInvestedCapital
```

If average invested capital <= 0, standard ROIC comparison is unavailable; mark outside this metric model. Do not force a positive/negative score.

### FCF margin

```text
FCF_margin = FCF_screen / Revenue
```

Revenue <= 0 blocks the metric. Negative FCF is valid and unfavorable, not missing.

### Net debt / EBITDA

```text
NetDebt_EBITDA = NetDebt / EBITDA
```

Net cash may produce a negative ratio and can be favorable. EBITDA <= 0 receives an explicit unfavorable economic sentinel for this metric; do not let a negative denominator look attractive.

### FCF yield

```text
FCF_yield = FCF_screen / MarketCap
```

Negative FCF is valid and unfavorable. Market cap <= 0 is invalid.

### EV / EBIT

```text
EV_EBIT = EV / EBIT
```

EBIT <= 0 receives an unfavorable economic sentinel. EV <= 0 requires special review and is outside the standard comparison.

### Revenue CAGR

Four comparable completed annual observations required.

### EPS CAGR

Four annual EPS observations required. If any observation is missing: missing. If observations exist but nonpositive earnings make CAGR economically invalid, record raw CAGR null plus a defined unfavorable economic state. Do not take invalid roots.

### Momentum 12–1

Using a documented total-return series:

```text
Momentum_12_1 = TRI[t-21] / TRI[t-252] - 1
```

### Momentum 6–1

```text
Momentum_6_1 = TRI[t-21] / TRI[t-126] - 1
```

The latest approximately one month is skipped intentionally.

### Volatility

Use 252 daily total returns when available:

```text
Vol_252 = sample_std(daily_total_returns) * sqrt(252)
```

### Maximum drawdown

Use positive loss magnitude:

```text
DD[d] = 1 - TRI[d] / running_max_TRI[d]
MaxDrawdown_252 = max(DD[d])
```

A 35% drawdown is stored as +0.35. Lower is better.

---

# 12. Cross-sectional scoring

## 12.1 Peer groups

Score each metric within the current sector classification of the eligible current universe.

Use at least 20 valid finite peers for a sector-metric comparison under Competition V1.

If fewer than 20 exist:

- mark that metric `SCORING_UNAVAILABLE` for that sector;
- do not silently switch to an all-market percentile;
- do not merge sectors without a logged model change.

This minimum is a V1 policy and must appear in sensitivity/coverage reporting.

## 12.2 Normalization algorithm

For each sector and metric:

1. Select valid finite economic values.
2. Compute 5th/95th percentile cut points.
3. Winsorize valid values to those cut points.
4. Rank winsorized values ascending with midranks for ties.
5. For n values, calculate:

```text
p = 100 * (rank - 0.5) / n
```

6. If **higher is better**, `score = p`.
7. If **lower is better**, `score = 100 - p`.
8. Missing values remain null.
9. Explicit economic sentinels receive their specified unfavorable score.

### Non-negotiable direction tests

Automated tests must prove:

- higher ROIC -> higher score;
- higher FCF margin -> higher score;
- lower net debt/EBITDA -> higher score;
- higher FCF yield -> higher score;
- lower positive EV/EBIT -> higher score;
- higher revenue growth -> higher score;
- higher valid EPS growth -> higher score;
- higher momentum -> higher score;
- lower volatility -> higher score;
- lower drawdown magnitude -> higher score.

This directly prevents recurrence of the prior scoring-direction defect.

## 12.3 Composite score

```text
S = 0.12*ROIC_score
  + 0.10*FCF_margin_score
  + 0.08*NetDebt_EBITDA_score
  + 0.10*FCF_yield_score
  + 0.10*EV_EBIT_score
  + 0.10*RevenueGrowth_score
  + 0.10*EPSGrowth_score
  + 0.12*Momentum12_1_score
  + 0.08*Momentum6_1_score
  + 0.05*Volatility_score
  + 0.05*Drawdown_score
```

Family scores:

```text
Quality = weighted quality contribution / 0.30
Valuation = weighted valuation contribution / 0.20
Growth = weighted growth contribution / 0.20
Momentum = weighted momentum contribution / 0.20
Risk = weighted risk contribution / 0.10
```

All eleven outcomes must be available for a ranked composite under baseline Competition V1.

No missing-weight redistribution.

## 12.4 Sorting

Rank complete companies by:

1. composite score descending;
2. quality score descending;
3. documented liquidity measure descending if available;
4. stable security ID ascending.

Use full precision for sorting. Display rounded values separately.

---

# 13. Research queues

## 13.1 Queue sizes

Human workload is intentionally limited.

- **Research queue:** Top 20 scored companies.
- **Priority queue:** Top 10 scored companies, subject to data/research flags.
- **Initial deep research:** 3–4 names, not 20.

Do not create a 40-name human research queue.

## 13.2 Sector concentration in the displayed queue

The priority queue should not contain more than three names from one sector unless fewer alternatives satisfy the baseline rules. If the raw Top 10 exceeds that, preserve the raw rank and separately produce a `DIVERSIFIED_RESEARCH_VIEW` with the cap.

This is a research-workload rule, not a portfolio-sector limit.

## 13.3 Quantitative resilience precheck

For automatic promotion into deep research, Competition V1 tests:

- positive TTM EBIT;
- positive TTM CFO;
- positive TTM FCF;
- positive annual FCF in at least 2 of latest 3 fiscal years;
- net debt/EBITDA <= 4.0x with positive EBITDA;
- interest coverage >= 3.0x where positive gross interest expense exists;
- composite score >= 70;
- Quality >= 60.

These are V1 resilience hypotheses, not universal truths.

A company that fails may still be manually researched, but the automatic engine must label it `OUTSIDE_CORE_POLICY` rather than quietly overriding the gate.

## 13.4 No automatic buy status

Stage 1 outputs only research priority states such as:

- `TOP10_PRIORITY`
- `TOP20_RESEARCH`
- `SCORED_NOT_PRIORITY`
- `OUTSIDE_CORE_POLICY`
- `DATA_BLOCKED`
- `OUTSIDE_STANDARD_MODEL`

There is no `BUY` state.

---

# 14. Stage 1 sensitivity suite

Sensitivity tests exist to measure stability, not to select weights that look best after the fact.

## 14.1 Family-weight variants

Baseline:

```text
Q=.30, V=.20, G=.20, M=.20, R=.10
```

For each family, test +5 percentage points and −5 percentage points while proportionally rescaling the other families.

Also test:

- equal family weights 20/20/20/20/20;
- quality-heavy 40/15/15/15/15;
- momentum-light 35/20/20/10/15.

Preserve relative metric weights within each family when shifting family weights.

## 14.2 Normalization/universe variants

Test separately:

- winsorization 1/99;
- winsorization 2.5/97.5;
- baseline 5/95;
- peer-minimum sensitivity if coverage reveals a meaningful issue;
- $10 price floor as a universe-policy diagnostic.

Do not combine every option into a large optimization grid.

## 14.3 Required outputs for each variant

Report:

- Top 10 overlap with baseline;
- Top 20 overlap with baseline;
- Top 20 Jaccard similarity;
- Spearman rank correlation on common eligible names;
- median absolute rank change;
- maximum rank change among baseline Top 20;
- sector composition;
- eligible/complete counts;
- names entering/leaving Top 20.

Flag for review, not automatic rejection, when a reasonable ±5-point family-weight change produces:

- Spearman rank correlation below 0.90; or
- Top 20 Jaccard below 0.60.

These are V1 stability flags, not claims of predictive power.

## 14.4 Factor-correlation diagnostic

Compute the correlation matrix among the eleven normalized factor scores on the complete sample.

Flag absolute correlations >0.80 for review of duplicated exposure. Do not automatically delete a factor because two related concepts correlate.

---

# 15. Stage 1 required output artifacts

A WIC-S003 Stage 1 package is incomplete unless it contains the actual run outputs below.

```text
WIC-S003/
  README.md
  config/
    competition_v1.yaml
  src/...
  tests/...
  outputs/<run_id>/
    run_manifest.json
    universe_audit.csv
    coverage_report.csv
    factor_dictionary.csv
    factor_values.csv
    ranked_universe.csv
    research_queue_top20.csv
    priority_queue_top10.csv
    sensitivity_results.csv
    factor_correlation.csv
    source_map.csv
    model_gate_memo.md
```

## 15.1 `run_manifest.json`

At minimum:

- run ID;
- cutoff;
- model/config version;
- code version/commit where available;
- source snapshot identifiers;
- universe count;
- complete score count;
- test status;
- run status;
- output hashes.

## 15.2 `universe_audit.csv`

One row per source constituent with:

- stable ID;
- ticker/display name;
- membership source/as-of;
- sector source;
- security type;
- exclusion/eligibility status;
- all reason codes;
- WInS availability status.

## 15.3 `coverage_report.csv`

Must make data quality visible rather than hiding it.

## 15.4 `factor_values.csv`

For every eligible/data-supported company:

- raw factor values;
- units;
- relevant dates;
- validity states;
- source IDs;
- normalized scores;
- clipping flags;
- factor contributions.

## 15.5 `ranked_universe.csv`

At minimum:

- rank;
- ticker/company;
- sector;
- 11 raw values or references;
- 11 normalized scores;
- five family scores;
- composite score;
- data/source status;
- research bucket.

## 15.6 `source_map.csv`

At minimum:

- dataset/source;
- provider;
- retrieved timestamp;
- as-of/effective date;
- fields supplied;
- source location/URL or stable ID;
- hash/reference where permitted;
- known limitations.

Local device paths alone are not durable source records.

---

# 16. Model-gate standard

## 16.1 Intended status

Competition V1 is designed for **MODEL SUPPORT**.

MODEL SUPPORT means:

- current screen runs reproducibly;
- calculations and score directions pass tests;
- data coverage is visible;
- factors are interpretable;
- source lineage is traceable;
- sensitivity is reviewed;
- output is used to prioritize research;
- no historical alpha claim is made.

## 16.2 MODEL REJECT triggers

Examples:

- material scoring-direction error;
- unexplained source leakage;
- unstable or irreconcilable inputs;
- data failures hidden as favorable values;
- output not reproducible under same inputs/config;
- current-universe ranks based on silently mixed dates;
- coverage so distorted that rank interpretation is misleading and unresolved.

## 16.3 MODEL CORE

Do not pursue MODEL CORE during the current competition checkpoint.

It would require credible point-in-time out-of-sample evidence, proper historical universe handling, execution assumptions, costs, benchmarks, independent review, and robust results. Even then it would be core to equity research, not Laura's overall goal strategy.

---

# 17. Stage 1 acceptance tests

The coding implementation must contain tests rather than a checklist that nobody runs.

## 17.1 Configuration

- factor weights sum to 1.00;
- unknown enum rejected;
- invalid quantiles rejected;
- required provider fields cannot be silently populated;
- baseline mode is CURRENT_RESEARCH.

## 17.2 Factor direction

Tests listed in Section 12.2 are mandatory.

## 17.3 CAGR

Four annual revenues 100, 110, 121, 133.1 -> 10% three-year CAGR.

Three annual observations -> no 3Y CAGR.

EPS series crossing/nonpositive values -> no invalid mathematical root.

Missing EPS -> missing state, not zero economic score.

## 17.4 Leverage

Debt 0, cash 100, EBITDA 50 -> net debt/EBITDA = -2x.

Positive debt with EBITDA <= 0 -> unfavorable sentinel, not an attractive negative ratio.

## 17.5 Cash-flow periods

Q1=10, H1=25, 9M=45, FY=70 -> discrete quarters 10/15/20/25 and annual total 70, not 150.

## 17.6 Corporate action

A 2-for-1 split with unchanged economic value must not create an artificial -50% momentum or drawdown.

## 17.7 Drawdown

TRI 100, 120, 90, 110 -> maximum drawdown magnitude 25%.

## 17.8 Percentile ties

All equal valid peer values -> scores of 50.

## 17.9 Peer minimum

19 valid peers under the production baseline -> metric unavailable; no all-market fallback.

## 17.10 Missing high-weight factor

Missing ROIC under baseline all-eleven policy -> no ranked composite.

## 17.11 Composite arithmetic

Use a fixed synthetic fixture whose hand-calculated weighted composite is known and assert equality within tight tolerance.

## 17.12 Reproducibility

Same input hashes + same config + same code -> same numeric factor values, scores, ranks, queues, and sensitivity results, excluding explicit operational timestamps.

## 17.13 Output integrity

- every source constituent reconciles to an eligibility/exclusion status;
- every ranked company has all eleven factor outcomes;
- rank order matches composite tie-break rules;
- Top 10 subset of Top 20;
- no output row has NaN/Infinity serialized as valid numeric data;
- no synthetic fixture appears in production output.

---

# 18. Stage 2 company research dossier

Stage 2 begins only after Stage 1 passes.

The screen is a queueing device. A high score is not a thesis.

For each of 3–4 selected research names, require:

1. **Business model** — customers, products/services, revenue drivers, major segments, economics.
2. **Durability** — competition, switching costs, pricing power, weak-period behavior.
3. **Growth mechanism** — organic versus acquisition growth, reinvestment needs, capacity constraints.
4. **Cash-flow quality** — CFO/earnings reconciliation, working capital, capex, stock compensation, unusual items.
5. **Balance-sheet resilience** — debt maturity, liquidity, refinancing needs, leases, contingent obligations.
6. **Capital stewardship** — reinvestment, R&D, acquisitions, buybacks, dilution, governance incentives.
7. **Counter-case** — strongest plausible mechanism that breaks the thesis.
8. **Valuation readiness** — what assumptions can be supported and what remains unknown.
9. **Laura role** — why this could belong in the permitted growth sleeve and why it cannot secure the operating reserve.
10. **Portfolio overlap** — sector/geographic/company exposure already obtained through VTI/VXUS and other holdings.
11. **Invalidation triggers** — measurable evidence that would force reassessment.
12. **Source index** — current filing, latest quarterly material, IR evidence, and at least one independent challenge source where available.

## 18.1 Research verdicts

Use:

- `APPROVED_RESEARCH`
- `NEEDS_EVIDENCE`
- `REJECTED_RESEARCH`

Do not average qualitative dimensions into another pseudo-precise numerical score.

## 18.2 Severe-risk holds

Verified going-concern warnings, active bankruptcy proceedings, unresolved material financial-reporting issues that make the thesis unreliable, or a business dependent on a single binary survival event block standard core approval until resolved.

Allegations alone are not established facts. Record evidence status.

---

# 19. Valuation module — Stage 3 only

Automatic draft valuation is **OFF** in Competition V1.

Valuation starts only when a company has an evidence-backed research packet and an analyst/reviewer provides company-specific assumptions.

## 19.1 Standard method

For ordinary nonfinancial operating businesses, use a five-year nominal USD FCFF DCF when appropriate.

```text
Revenue[k] = Revenue[k-1] * (1 + growth[k])
EBIT[k] = Revenue[k] * EBIT_margin[k]
NOPAT[k] = EBIT[k] * (1 - tax_rate[k])
DA[k] = Revenue[k] * DA_ratio[k]
Capex[k] = Revenue[k] * Capex_ratio[k]
ONWC[k] = Revenue[k] * ONWC_ratio[k]
DeltaONWC[k] = ONWC[k] - ONWC[k-1]
FCFF[k] = NOPAT[k] + DA[k] - Capex[k] - DeltaONWC[k]
```

Discount FCFF at a documented WACC.

## 19.2 Terminal value

Tie growth to reinvestment:

```text
Revenue6 = Revenue5 * (1 + g)
NOPAT6 = Revenue6 * terminal_margin * (1-terminal_tax)
TerminalReinvestmentRate = g / terminal_ROIC
FCFF6 = NOPAT6 * (1-TerminalReinvestmentRate)
TV5 = FCFF6 / (WACC-g)
```

Reject or hold when:

- WACC <= g;
- WACC-g < 2 percentage points under V1 valuation policy;
- terminal ROIC <= g;
- terminal assumptions lack support;
- company does not fit a standard steady-state FCFF model.

## 19.3 Enterprise-to-equity bridge

Account explicitly for:

- cash/nonoperating assets;
- interest-bearing debt;
- preferred claims;
- NCI;
- other debt-like claims;
- diluted-equivalent shares.

Do not double count items already reflected in FCFF.

## 19.4 Scenarios

Use coherent bear/base/bull scenarios created from company-specific evidence.

Do not generate them from fixed generic growth/margin offsets by default.

## 19.5 Required sensitivity

For a reviewed valuation:

- WACC shifts: -2pp, -1pp, base, +1pp, +2pp;
- terminal growth shifts: -1pp, base, +1pp;
- company-specific operating downside challenge.

## 19.6 Valuation gates

The following remain V1 hypotheses and must be labeled as such:

- base margin of safety >= 15%;
- modeled bear-value loss <= 30%;
- terminal assumptions reviewed;
- sensitivity does not reveal an obviously fragile case without explanation.

Passing valuation does not authorize an order.

## 19.7 12-month target

A dated 12-month target may be produced only after the company-specific valuation is reviewed and a forward capital bridge can be defended.

It is optional for WIC-S003 and must not delay Stage 1.

Do not label today's intrinsic value as a 12-month target.

---

# 20. Risk and client-fit package

For a deeply researched company, provide:

- 252-session volatility;
- trailing maximum drawdown;
- current drawdown;
- beta versus a documented broad U.S. benchmark if calculable;
- liquidity metric;
- debt/refinancing exposures;
- major customer dependence where disclosed;
- geographic/revenue/supply-chain exposures where disclosed;
- event calendar uncertainty;
- three principal business risks;
- invalidation conditions;
- overlap with current growth exposure where measurable.

Past volatility/drawdown never caps future loss.

## 20.1 Country/STEEP review

Use Social, Technological, Economic, Environmental, and Political lenses as causal questions, not additive scores.

Each material issue must identify:

- evidence;
- affected business segment/exposure;
- transmission mechanism;
- financial effect if estimable;
- review trigger.

Laura's Taiwan project does not create an automatic Taiwan-equity preference.

---

# 21. Portfolio and Goal Engine interfaces

## 21.1 Inputs from allocation/Goal process

When available, accept:

- current WInS portfolio snapshot ID;
- current growth-sleeve risk budget/status;
- whether new equity risk is allowed;
- relevant concentration constraints;
- WInS security availability check.

Missing portfolio/Goal context does not stop independent research. It stops any claim that a security is ready for allocation.

## 21.2 Output to investment committee

For an approved researched candidate, export:

- identity/ticker;
- research cutoff;
- score and factor contributions;
- business thesis;
- counter-case;
- valuation status and values if reviewed;
- major risks;
- invalidation triggers;
- sector/geographic exposure;
- existing-portfolio overlap flags;
- WInS availability state;
- current research verdict;
- current portfolio-fit blockers.

Do **not** export a target weight from the score.

`S=90` does not imply 9% weight, 90% probability, or expected 9% return.

## 21.3 Existing diversified holdings

Because the current WInS growth sleeve is largely VTI/VXUS, the IC must explicitly compare any direct stock with the broad exposure it would replace.

The stock engine should not say “add 5% stock X.” It should say, for example:

> Candidate X is approved/rejected for research; if IC wishes to deploy it, evaluate replacing part of diversified equity exposure while holding the separately approved total growth budget constant unless allocation approves otherwise.

## 21.4 Goal Engine

The Goal Engine must not consume individual stock scores or DCF upside as guaranteed long-term returns.

Company-specific stress narratives may inform qualitative risk review, but reserve probability, flexibility, and facility capacity remain Goal Engine / allocation outputs.

---

# 22. Monitoring — minimum Competition V1 approach

Do not build large monitoring infrastructure before Stage 1 works.

Minimum sufficient process:

- full screen: weekly or on-demand with a synchronized cutoff;
- held/researched company review: after material filings/earnings or major thesis-relevant events;
- research dossier expiry: team-defined/manual if needed;
- no automatic trading from rank movement.

A rank decline alone does not force a sale.

If later automated monitoring is added, it should preserve immutable prior decisions and distinguish data-feed failures from business deterioration.

---

# 23. AI assistance boundaries

AI may assist internally with:

- code generation and debugging;
- structured source extraction;
- research-question generation;
- drafting internal dossiers from frozen evidence packets;
- checking consistency;
- sensitivity interpretation;
- adversarial critique.

AI must not:

- invent financial inputs;
- invent source dates;
- invent team approvals;
- invent WInS trades;
- invent a company fact missing from the evidence store;
- turn an unreviewed draft into an approved research decision;
- automatically place orders;
- copy internal generated prose into an official competition submission without current rules being checked.

Calculations, factors, scoring, and gates should remain deterministic code.

---

# 24. Model status and claims

## 24.1 Permitted Competition V1 claims after Stage 1 passes

Examples:

- “We use an interpretable five-family, eleven-factor screen to prioritize company research.”
- “The screen compares companies within sectors and records data/source limitations.”
- “Factor weights are hypotheses and were sensitivity-tested rather than optimized for past returns.”
- “The screen is research support, not an autonomous stock-selection system.”
- “We do not claim historical alpha without a defensible point-in-time test.”

## 24.2 Prohibited claims

Do not claim:

- the screen predicts a specific excess return;
- the weights are historically optimal;
- high score means high probability of outperformance;
- a few weeks of WInS performance validate the model;
- today's S&P 500 can be used as the historical universe for a valid backtest;
- current fundamentals can be placed into past dates;
- a DCF discount is a guaranteed return;
- a stock score determines portfolio weight.

---

# 25. Stage-by-stage coding handoff protocol

This section is intentionally written so Aarav can paste the full specification into a coding assistant.

## Stage 0 — scaffold and contracts

### Build

- project structure;
- config loader/validator;
- enums/statuses;
- typed records/dataclasses/Pydantic-style contracts;
- base adapter interfaces;
- run manifest skeleton;
- unit-test framework;
- synthetic fixtures.

### Must pass before Stage 1A

- weights sum to 1;
- invalid config rejected;
- required external providers remain unresolved rather than silently selected;
- JSON/CSV serialization handles missing values explicitly;
- no network access occurs from pure calculation modules.

### Return to Aarav

- file tree;
- tests and results;
- exact unresolved provider inputs.

Do not build valuation yet.

---

## Stage 1A — universe + market pipeline

### Build

- selected universe adapter;
- selected market-data adapter;
- source snapshot/versioning;
- raw current S&P 500 snapshot;
- security identity normalization;
- market history validation;
- price/momentum/risk inputs;
- eligibility reasons that depend on security/market data.

### Must produce

- universe snapshot;
- market source map;
- preliminary universe audit;
- market-factor fixture tests.

### Stop conditions

Stop and report if:

- provider is not supplied;
- universe source cannot be dated;
- sector source is absent for sector scoring;
- price adjustments/corporate actions cannot be interpreted safely.

Do not patch these by guessing.

---

## Stage 1B — fundamentals + factor calculations

### Build

- SEC retrieval/mapping;
- annual and quarterly normalization;
- TTM reconstruction;
- share/debt/cash mapping;
- eleven raw factors;
- data validity states;
- coverage diagnostics.

### Must produce

- factor dictionary;
- factor values with source IDs/dates;
- coverage report;
- all factor arithmetic tests.

### Stop conditions

Stop affected companies when:

- accounting mappings are ambiguous;
- annual history is incomplete;
- current share/debt/cash values cannot be reconciled;
- source conflicts are material and unresolved.

Do not turn source failure into a neutral/favorable score.

---

## Stage 1C — scoring + queues

### Build

- sector peer groups;
- winsorization;
- correct percentile direction;
- all-eleven completeness rule;
- family/composite scores;
- deterministic sorting;
- Top 20 / Top 10 outputs;
- raw and diversified research views if needed.

### Mandatory anti-regression test

Construct synthetic companies A/B/C where C is better on every factor and A is worse on every factor. The code must rank C above B above A.

This directly guards against the prior reversed-rank error.

---

## Stage 1D — sensitivity + final WIC-S003 package

### Build/run

- family-weight variants;
- equal-weight/quality-heavy/momentum-light variants;
- winsorization variants;
- factor-correlation matrix;
- coverage/sector-bias review;
- reproducibility rerun;
- model-gate memo.

### Required final checkpoint package

Return all Stage 1 outputs listed in Section 15.

Only after Supervisor audit may the build be treated as WIC-S003 PASS.

---

## Stage 2 — deep research

Choose 3–4 names from the priority/research queue. Do not choose names because the team already likes them unless they are clearly marked as manual research intake.

Build dossiers using primary filings and current evidence. No automatic stock purchase follows.

---

## Stage 3 — reviewed valuation

Implement the deterministic FCFF module and tests. Do not create company assumptions from generic defaults. Require analyst inputs/evidence.

A coding assistant may build the valuation calculator before all real dossiers are ready, but should test it only on synthetic fixtures until reviewed company assumptions exist.

---

# 26. Required coding-assistant response format after each stage

The coding assistant should return:

```text
STAGE COMPLETED:

A. Files created/modified
- ...

B. Commands run
- ...

C. Tests
- X passed / Y failed
- failures, if any

D. Artifacts produced
- ...

E. Data/source coverage
- ...

F. Deviations from specification
- NONE or exact list

G. Inputs still required from Jai/Aarav
- ...

H. Risks / defects
- ...

I. Recommended next stage
- ...
```

If a stage fails, do not continue merely because the next stage is already specified.

---

# 27. Unknowns that must be asked rather than invented

The implementation assistant must ask Aarav/Jai when any of the following becomes necessary and is not supplied:

1. Which current market-data provider/API the team has access to.
2. Which dated current S&P 500 membership source will be used.
3. Which sector-classification source/version will be used.
4. Any API credentials/entitlements; credentials must never be printed into code or logs.
5. Any ambiguous company-specific accounting mapping that cannot be resolved from the filing.
6. Any company-specific DCF assumption not supported by evidence.
7. Any proposed change to the total growth sleeve or current WInS implementation.
8. Any final portfolio concentration limit not already approved.
9. Any final stock position size.
10. Any decision to expand beyond the S&P 500 Competition V1 universe.

The assistant should not ask questions whose answers are already present in the current project artifacts.

---

# 28. Final pass standard for WIC-S003

WIC-S003 can be submitted for Supervisor re-audit when:

- Stage 1 code exists;
- current S&P 500 snapshot is dated and traceable;
- factor values are actually calculated on current data;
- rank directions are tested and correct;
- complete-score coverage is reported;
- ranked universe exists;
- Top 20 and Top 10 queues exist;
- sensitivity results exist;
- repeated run with identical inputs/config is reproducible;
- source map exists;
- known limitations are explicit;
- model-gate memo states MODEL_SUPPORT unless evidence requires MODEL_REJECT;
- no historical alpha claim is made;
- no individual stock is treated as approved merely because of rank.

A large design document without live outputs does not satisfy this standard.

---

# 29. Master Google Doc treatment

For WIC-S003, the Master Google Doc should contain a **summary only**, not the full technical specification or code.

After final audit, include:

- task/owner;
- model role;
- universe;
- five factor families and weights;
- short methodology summary;
- data/source limitations;
- sensitivity conclusion;
- Top 10/Top 20 research outputs or selected research names if approved for internal documentation;
- model-gate status;
- link to full technical package;
- Supervisor status/date.

Do not paste thousands of lines of specification into the Master Doc.

---

# 30. Deferred reference architecture

The earlier v1.0 specification contained useful ideas that are retained as **deferred reference**, not current required scope:

- broader Composite 1500 universe;
- full immutable historical replay;
- comprehensive corporate-action reconstruction for backtesting;
- automated nightly scheduling;
- alert deduplication infrastructure;
- automatic draft valuation;
- 12-month target generation for every displayed stock;
- optional valuation-distribution simulation;
- technical/tactical indicators;
- automated natural-language thesis generation;
- replacement hysteresis automation;
- full research-event monitoring.

None of these should be deleted from project history. They may be implemented later if the core competition work is secure and their benefit clearly exceeds the time cost.

---

# 31. Source register for this finalized specification

## 31.1 Controlling internal/official sources

1. `2026_WGY_Gao Case Study-FINAL(1).pdf` — Laura's contributions, timing, operating commitment, reserve, facility contribution, co-sponsor communication, scope.
2. `2026_WGY_Competition Guide-FINAL(1).pdf` — strategy-first competition structure, role of WInS, deliverable sequence, evaluation framing.
3. `FAQ.txt` — current WInS account/trading rules and permitted/prohibited categories.
4. `WInS.txt` — official/practice trading timing and Trading Note role.
5. `client_strategy_spec_v1.md` / WIC-S001 — passed client strategy specification.
6. `Laura Goal Engine v0.2.1` / WIC-S002 — passed client scenario engine and strategy boundary.
7. `wins_initial_implementation_packet_FINAL.md` / WIC-S007 — passed opening WInS allocation and executed implementation evidence.
8. `WIC-S003_Aarav_Equity_Screen_Model_Gate.md` — prior WIC-S003 screen/model-gate design and identified implementation defects.
9. `WGHSIC Stock Research Engine Implementation Specification v1.0` — detailed technical reference; revised here for current authority, scope, and competition execution.

## 31.2 External technical references retained from v1.0

- SEC EDGAR API/documentation for submissions and XBRL/company facts.
- Kenneth R. French Data Library momentum methodology as background for the prior-return convention; Competition V1 uses its own documented daily-session implementation.
- Damodaran valuation references for FCFF/WACC consistency and terminal reinvestment logic.
- S&P documentation for index definitions when required by the selected universe source.

External references support definitions and implementation choices. They do not prove that this exact screen predicts excess returns.

---

# 32. Final statement

This Competition V1 Stock Research Engine exists to make the team's equity research **more disciplined, traceable, and client-aware**.

Its role is deliberately limited:

**Current S&P 500 data -> transparent factor ranking -> small research queue -> company research -> reviewed valuation -> investment-committee consideration -> possible replacement of diversified growth exposure if the integrated client strategy permits it.**

It does not determine Laura's risk budget. It does not determine the operating reserve. It does not set the facility contribution. It does not convert a stock score into a position size. It does not trade.

The current WInS portfolio already provides broad growth, protection, and liquidity exposure. Individual equities must therefore earn their place through evidence and must fit within the broader strategy rather than expand risk by default.

**Competition V1 target:** build a correct, reproducible, current research-support system first. Add complexity only after that system is proven and only when it serves a clear competition need.
