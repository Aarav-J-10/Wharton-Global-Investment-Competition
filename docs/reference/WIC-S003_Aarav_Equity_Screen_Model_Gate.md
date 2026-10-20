# WIC-S003 — Interpretable Equity Screen + Model Gate

**Owner:** Aarav Jalan  
**Status:** COMPLETE FOR SUPPORT-LEVEL CHECKPOINT USE  
**Prepared:** 27 September 2026  
**Deadline:** 29 September 2026, 2:00 p.m. IST  
**Role:** Growth-sleeve research infrastructure, not a return-prediction system

---

## 1. Executive Decision

### Model Gate Recommendation: **MODEL SUPPORT**

The equity model should be retained as an **interpretable research screener** that ranks an eligible equity universe for deeper fundamental research. It should **not** be presented as an alpha model, return forecast, optimizer, or autonomous security-selection engine.

The initial factor architecture is:

| Factor | Initial Weight | Purpose |
|---|---:|---|
| Quality | 30% | Prefer financially robust, profitable businesses |
| Valuation | 20% | Avoid paying indiscriminately for otherwise attractive companies |
| Growth | 20% | Capture fundamental business/earnings expansion |
| Momentum | 20% | Recognize persistent market information without short-term chasing |
| Risk | 10% | Penalize unusually unstable or drawdown-prone candidates |

These weights are a **hypothesis**, not an optimized result. No claim is made that 30/20/20/20/10 is historically optimal.

**Permitted use:** generate a ranked shortlist, expose factor trade-offs, prioritize analyst time, and document why a company entered research.

**Not permitted:** claim expected excess returns from score alone; retrospectively apply today's fundamentals; use the screen as a substitute for security research; force individual equities into the opening WInS portfolio; feed WInS performance into Laura's long-term Goal Engine.

---

## 2. Client and Portfolio Boundary

The screen belongs to the **growth-sleeve research process**. It is separate from Laura's long-term Goal Engine and does not alter the client's reserve, facility-capacity, certainty-standard, or glidepath calculations.

The uploaded WIC-S002 artifact defines the Goal Engine as a 2027–2042 scenario model of Laura's actual cash flows, explicitly states that WInS results are not used, and treats strategic parameters as provisional sensitivity variables until WIC-S001 is approved. The screen therefore cannot become an implicit source of long-term expected-return assumptions.

### Operating rules

1. **Client-first:** a high screen score never overrides portfolio role, liquidity needs, reserve protection, diversification, or implementation constraints.
2. **Research-first:** a high score means "research this security next," not "buy."
3. **No forced activity:** individual equities may remain at zero weight until research is sufficient.
4. **No WInS leakage:** simulated or realized WInS returns do not enter long-term client projections.
5. **No circularity:** the screen does not target a return required to justify a predetermined facility amount.

---

## 3. Eligible Universe

### v1 universe

Use a **large-cap U.S. listed equity universe**, preferably the contemporaneous S&P 500 membership list for the current screen date, subject to data availability.

### Eligibility filters

A security is eligible only if:

- it is an operating-company common equity;
- it has sufficient current financial-statement data for the required fundamental factors;
- it has sufficient adjusted price history for momentum and risk;
- it is not a duplicate share class unless there is a documented reason to retain both;
- required data can be traced to a dated source.

### Exclusions / flags

- ETFs, closed-end funds, preferred shares and other non-common-equity instruments;
- securities with insufficient price history;
- securities with severe fundamental-data gaps;
- financial metrics that are structurally non-comparable should be **sector-aware or flagged**, not blindly ranked.

**Universe warning:** today's index constituents cannot be used as the historical universe in a backtest. Doing so introduces survivorship bias.

---

## 4. Factor Dictionary

All raw metrics are converted to cross-sectional percentile scores from 0 to 100, where **higher is better**. Percentile ranking reduces scale incompatibility and prevents a metric with large numerical units from dominating merely because humans chose inconvenient measurement systems.

### 4.1 Quality — 30%

Preferred metrics:

| Metric | Direction | Rationale |
|---|---|---|
| Return on equity (ROE) | Higher better | Profitability relative to shareholder capital |
| Free-cash-flow margin | Higher better | Cash conversion / economic quality |
| Debt-to-equity | Lower better | Balance-sheet conservatism |

**Quality score**
`mean(percentile(ROE), percentile(FCF margin), reverse_percentile(D/E))`

Optional expansion only if sourced consistently: operating profitability, accruals ratio, interest coverage.

### 4.2 Valuation — 20%

| Metric | Direction | Rationale |
|---|---|---|
| P/E | Lower better | Price paid per unit of earnings |
| FCF yield | Higher better | Cash flow relative to market value |

**Valuation score**
`mean(reverse_percentile(P/E), percentile(FCF yield))`

Negative or economically meaningless denominators are treated as missing rather than as "cheap."

### 4.3 Growth — 20%

| Metric | Direction | Rationale |
|---|---|---|
| Revenue growth | Higher better | Business expansion |
| EPS growth | Higher better | Per-share earnings expansion |

Use a consistent trailing or multi-year definition across the universe. Do not mix forward analyst estimates with trailing realized growth unless separately labeled.

**Growth score**
`mean(percentile(revenue growth), percentile(EPS growth))`

### 4.4 Momentum — 20%

| Metric | Direction | Rationale |
|---|---|---|
| 12-to-1 month return | Higher better | Medium-term price persistence while skipping most recent month |
| 6-to-1 month return | Higher better | Secondary medium-term confirmation |

The 12-to-1 convention is aligned with the established academic practice of using prior returns while skipping the most recent month.

**Momentum score**
`mean(percentile(12-1 return), percentile(6-1 return))`

### 4.5 Risk — 10%

| Metric | Direction | Rationale |
|---|---|---|
| 1-year annualized volatility | Lower better | Penalize unstable price behavior |
| 1-year maximum drawdown | Less severe better | Penalize large peak-to-trough losses |

**Risk score**
`mean(reverse_percentile(volatility), percentile(max drawdown))`

This is a **ranking control**, not a full portfolio risk model.

---

## 5. Composite Score

For stock \(i\):

\[
S_i = 0.30Q_i + 0.20V_i + 0.20G_i + 0.20M_i + 0.10R_i
\]

where each component is a 0–100 percentile score.

The score has **ordinal research meaning**. A score of 80 is not a forecast of 80% return, 80% probability of success, or any other seductive nonsense.

### Shortlist rule

- Rank eligible securities by composite score.
- Primary research queue: top 20.
- High-priority queue: top 10.
- A stock enters an IC proposal only after separate company-specific research covering thesis, valuation reasonableness, principal risks, portfolio role, obvious alternatives and invalidation conditions.

---

## 6. Missing-Data Treatment

Missing data must not silently become a favorable score.

### Rule set

1. Compute a factor only if at least **50% of its specified submetrics** are valid.
2. For a missing submetric within an otherwise valid factor, average only available submetrics and record the missing field.
3. If **two or more of the five factors** are unavailable, mark the security `INSUFFICIENT_DATA` and exclude it from the ranked shortlist.
4. Display `data_coverage` as the percentage of required raw metrics present.
5. Never impute a missing fundamental with the current cross-sectional median for a historical test unless the imputation rule was fixed ex ante and applied point-in-time.
6. Negative P/E or FCF-yield denominator pathologies are missing/flagged, not automatically "best value."

A stricter production variant can require 100% factor availability. The 50% submetric rule is retained for v1 so one unavailable accounting field does not erase an otherwise researchable company.

---

## 7. Data-Source Map

| Data need | Preferred source | Use | Point-in-time requirement |
|---|---|---|---|
| Filing dates / historical filings | SEC EDGAR submissions | Determine when information became public | **Yes** |
| Fundamental statement facts | SEC XBRL Company Facts / filings | Quality, valuation, growth inputs | **Yes** |
| Current index universe | S&P Dow Jones Indices / documented constituent source | Current eligible universe | Current screen only |
| Historical prices / adjusted returns | Reliable market-price provider | Momentum, volatility, drawdown | **Yes** |
| Academic factor validation | Kenneth R. French Data Library | Validate factor definitions/conventions | Not security-level input |
| Company-specific confirmation | 10-K, 10-Q, earnings releases / IR | Analyst diligence after screening | Dated source required |

### Source-control requirement

Every material input should preserve:
`ticker, metric, value, period_end, filing_date/publication_date, source, access_date`.

The **filing/publication date**, not merely fiscal period end, controls when a fundamental is available in a historical test.

---

## 8. Current-Universe Output Schema

The reproducible run exports `equity_screen_current.csv` with:

```text
as_of_date
ticker
company
sector
eligible
data_coverage
quality_score
valuation_score
growth_score
momentum_score
risk_score
composite_score
rank
research_bucket
missing_fields
source_status
```

### Research buckets

- `A_TOP10` — immediate fundamental-research queue
- `B_11_20` — secondary research queue
- `C_OTHER` — eligible, not currently prioritized
- `INSUFFICIENT_DATA` — not ranked
- `INELIGIBLE` — excluded by universe rules

**Important:** no live ranked ticker list is fabricated in this memo. The current-universe output is valid only after the accompanying code is supplied with dated, traceable fundamentals and price data.

---

## 9. Reproducible Screen Code

Save as `equity_screen.py`. Input file: `screen_input.csv`.

```python
import numpy as np
import pandas as pd

WEIGHTS = {
    "quality": 0.30,
    "valuation": 0.20,
    "growth": 0.20,
    "momentum": 0.20,
    "risk": 0.10,
}

RAW_FIELDS = [
    "roe", "fcf_margin", "debt_to_equity",
    "pe", "fcf_yield",
    "sales_growth", "eps_growth",
    "mom_12_1", "mom_6_1",
    "vol_1y", "max_dd_1y",
]

def pct_score(series, higher_is_better=True):
    """Cross-sectional percentile score, 0-100. Missing stays missing."""
    return series.rank(
        pct=True,
        ascending=not higher_is_better,
        method="average"
    ) * 100.0

def row_mean(frame, cols, min_count):
    return frame[cols].mean(axis=1, skipna=True).where(
        frame[cols].notna().sum(axis=1) >= min_count
    )

def build_screen(df):
    x = df.copy()

    # Basic sanity treatment
    x.loc[x["pe"] <= 0, "pe"] = np.nan

    # Raw metric percentile scores
    x["q_roe"] = pct_score(x["roe"], True)
    x["q_fcfm"] = pct_score(x["fcf_margin"], True)
    x["q_de"] = pct_score(x["debt_to_equity"], False)

    x["v_pe"] = pct_score(x["pe"], False)
    x["v_fcfy"] = pct_score(x["fcf_yield"], True)

    x["g_sales"] = pct_score(x["sales_growth"], True)
    x["g_eps"] = pct_score(x["eps_growth"], True)

    x["m_12_1"] = pct_score(x["mom_12_1"], True)
    x["m_6_1"] = pct_score(x["mom_6_1"], True)

    x["r_vol"] = pct_score(x["vol_1y"], False)
    # max_dd_1y should be negative; -10% is better than -50%
    x["r_mdd"] = pct_score(x["max_dd_1y"], True)

    # At least half of submetrics per factor
    x["quality_score"] = row_mean(x, ["q_roe", "q_fcfm", "q_de"], 2)
    x["valuation_score"] = row_mean(x, ["v_pe", "v_fcfy"], 1)
    x["growth_score"] = row_mean(x, ["g_sales", "g_eps"], 1)
    x["momentum_score"] = row_mean(x, ["m_12_1", "m_6_1"], 1)
    x["risk_score"] = row_mean(x, ["r_vol", "r_mdd"], 1)

    factor_cols = [
        "quality_score", "valuation_score", "growth_score",
        "momentum_score", "risk_score"
    ]
    x["factor_count"] = x[factor_cols].notna().sum(axis=1)
    x["data_coverage"] = x[RAW_FIELDS].notna().mean(axis=1)

    # Weighted average across available factors, but require >=4/5.
    weighted_sum = (
        WEIGHTS["quality"] * x["quality_score"].fillna(0)
        + WEIGHTS["valuation"] * x["valuation_score"].fillna(0)
        + WEIGHTS["growth"] * x["growth_score"].fillna(0)
        + WEIGHTS["momentum"] * x["momentum_score"].fillna(0)
        + WEIGHTS["risk"] * x["risk_score"].fillna(0)
    )
    available_weight = (
        WEIGHTS["quality"] * x["quality_score"].notna()
        + WEIGHTS["valuation"] * x["valuation_score"].notna()
        + WEIGHTS["growth"] * x["growth_score"].notna()
        + WEIGHTS["momentum"] * x["momentum_score"].notna()
        + WEIGHTS["risk"] * x["risk_score"].notna()
    )

    x["composite_score"] = (weighted_sum / available_weight).where(
        x["factor_count"] >= 4
    )

    x["rank"] = x["composite_score"].rank(
        ascending=False, method="min"
    )

    x["research_bucket"] = np.select(
        [
            x["composite_score"].isna(),
            x["rank"] <= 10,
            x["rank"] <= 20,
        ],
        [
            "INSUFFICIENT_DATA",
            "A_TOP10",
            "B_11_20",
        ],
        default="C_OTHER",
    )

    x = x.sort_values(
        ["composite_score", "data_coverage"],
        ascending=[False, False],
        na_position="last"
    )

    return x

if __name__ == "__main__":
    df = pd.read_csv("screen_input.csv")
    out = build_screen(df)
    out.to_csv("equity_screen_current.csv", index=False)
    print(out[
        ["ticker", "composite_score", "rank",
         "research_bucket", "data_coverage"]
    ].head(20).to_string(index=False))
```

---

## 10. Input Data Contract

`screen_input.csv` must contain at minimum:

```text
as_of_date,ticker,company,sector,roe,fcf_margin,debt_to_equity,pe,fcf_yield,sales_growth,eps_growth,mom_12_1,mom_6_1,vol_1y,max_dd_1y
```

### Calculation conventions

- `mom_12_1`: total/adjusted-price return from approximately 12 months ago to 1 month ago.
- `mom_6_1`: total/adjusted-price return from approximately 6 months ago to 1 month ago.
- `vol_1y`: standard deviation of daily returns × sqrt(252).
- `max_dd_1y`: minimum of `price / rolling_peak - 1`.
- Growth metrics must use the same horizon across securities.
- Market-value-dependent metrics use prices known on or before `as_of_date`.

---

## 11. Sensitivity Analysis

The objective is **robustness**, not finding the weight vector that makes the past look prettiest.

### Required tests

#### A. One-factor ±5 percentage-point test

For each factor, change its weight by ±5pp and proportionally rescale the remaining weights to sum to 100%.

Record:

- top-10 overlap with baseline;
- top-20 overlap with baseline;
- median absolute rank change;
- maximum rank change among baseline top 20.

#### B. Equal-weight comparator

Compare baseline 30/20/20/20/10 against 20/20/20/20/20.

#### C. Quality-heavy comparator

40/15/15/15/15.

#### D. Momentum-light comparator

35/20/20/10/15.

### Stability interpretation

- **High stability:** ≥80% top-20 overlap across reasonable variants.
- **Moderate stability:** 60–79%.
- **Low stability:** <60%; do not treat exact ranks as meaningful.

Even with high overlap, exact ordinal differences such as rank 3 versus rank 5 should not be overinterpreted.

### Reference implementation

```python
def weighted_score(df, weights):
    cols = {
        "quality": "quality_score",
        "valuation": "valuation_score",
        "growth": "growth_score",
        "momentum": "momentum_score",
        "risk": "risk_score",
    }
    num = 0.0
    den = 0.0
    for factor, w in weights.items():
        s = df[cols[factor]]
        num = num + w * s.fillna(0)
        den = den + w * s.notna()
    return (num / den).where(df[list(cols.values())].notna().sum(axis=1) >= 4)

def top_overlap(base, alt, n=20):
    a = set(base.nlargest(n).index)
    b = set(alt.nlargest(n).index)
    return len(a & b) / n
```

---

## 12. Turnover and Risk Discussion

### Turnover controls

The screen should be refreshed on a **monthly** schedule for research prioritization, not daily.

Reasons:

- fundamental information changes at filing/earnings cadence, not every afternoon;
- momentum can move faster, but daily reranking encourages noise-driven research churn;
- WInS activity should reflect investment decisions, not a leaderboard twitch.

Suggested governance:

1. monthly scheduled screen;
2. event-driven refresh after a material filing/earnings event;
3. do not replace a researched holding solely because its rank slips a few places;
4. require a documented thesis change, risk change, valuation change, or materially superior alternative before turnover.

### Risks the score does not solve

- sector concentration;
- correlated business models;
- macro factor concentration;
- valuation regime changes;
- accounting comparability;
- event/gap risk;
- liquidity/spread issues;
- tax considerations;
- client-level reserve and liability matching.

These require portfolio-level judgment outside the screener.

---

## 13. Historical Testing Feasibility Assessment

### Question

Can a defensible point-in-time historical test be produced efficiently enough to justify an alpha claim?

### Finding

**Technically feasible, but not justified for the current checkpoint unless point-in-time universe and fundamental snapshots are reconstructed correctly.**

A valid historical test needs, for every rebalance date:

1. the universe that actually existed then;
2. only filings publicly available by that date;
3. historical market prices available by that date;
4. a predeclared missing-data rule;
5. realistic rebalance lag after filings;
6. delisted/removed companies retained where applicable;
7. transaction-cost/turnover treatment;
8. weights fixed without using future outcomes;
9. out-of-sample or walk-forward evaluation.

SEC EDGAR provides filing histories and XBRL facts that can support publication-aware fundamental reconstruction. However, a present-day constituent list is not a historical universe, and current fundamentals cannot be pasted backward.

### Decision

**Do not make an unsupported alpha claim.**

For WIC-S003 v1, retain the model as a **current research screener**. Historical factor literature may support the *reasonableness of factor categories*, but it does not validate this exact composite, universe, implementation, or weight set.

A future backtest becomes admissible only when the team can demonstrate point-in-time data integrity and survivorship control.

---

## 14. Model Gate Memo

### MODEL CORE

**Reject.**

The screen should not become the project's core quantitative model. Laura's Goal Engine remains the core because it models the client's cash flows, reserve reliability, facility capacity, and uncertainty directly.

### MODEL SUPPORT

**Accept.**

This is the correct role for v1. The screen is:

- interpretable;
- reproducible;
- deliberately simple;
- useful for prioritizing research;
- compatible with disciplined growth-sleeve implementation;
- resistant to unsupported ML/optimization expansion;
- separable from client-liability modeling.

### MODEL REJECT

**Reject the following versions/claims:**

- any Random Forest, XGBoost or neural-network extension;
- an "AI stock predictor";
- optimized factor weights selected for historical performance;
- a backtest using today's constituents as historical constituents;
- a backtest using current fundamentals at prior dates;
- a claim that high score predicts a specified excess return;
- automatic WInS trading from ranks;
- a screen score used to justify a predetermined facility target.

### Final Gate

> **MODEL SUPPORT.** Use the 30/20/20/20/10 interpretable multi-factor score as a transparent research-prioritization tool. Do not claim predictive alpha unless a later, separately audited point-in-time backtest satisfies universe, filing-date, survivorship, look-ahead, turnover and out-of-sample controls.

---

## 15. Validation and Test Checklist

Before each official run:

- [ ] weights sum to 1.00;
- [ ] all percentile scores lie in [0, 100];
- [ ] lower D/E produces a higher quality subscore, all else equal;
- [ ] lower positive P/E produces a higher valuation subscore;
- [ ] higher FCF yield produces a higher valuation subscore;
- [ ] higher momentum produces a higher momentum subscore;
- [ ] lower volatility produces a higher risk subscore;
- [ ] less-negative drawdown produces a higher risk subscore;
- [ ] securities with <4 valid factors receive no composite;
- [ ] no missing value becomes zero before percentile ranking;
- [ ] output is identical on repeated clean runs with identical input;
- [ ] all source dates are ≤ screen as-of date;
- [ ] historical runs use publication/filing dates, not fiscal period end alone;
- [ ] no current-universe membership is used to define a past universe.

---

## 16. Deliverables Checklist

This single document contains the methodology and code required to create the WIC-S003 package.

Expected project files after execution:

```text
WIC-S003/
├── WIC-S003_equity_screen_and_model_gate.md
├── equity_screen.py
├── screen_input.csv
├── equity_screen_current.csv
├── factor_sensitivity.csv
└── source_map.csv
```

### Completion state

| Requirement | State |
|---|---|
| Quality / valuation / growth / momentum / risk architecture | Complete |
| 30/20/20/20/10 initial hypothesis | Complete |
| Missing-data treatment | Complete |
| Eligible-universe rules | Complete |
| Ranked-shortlist mechanism | Complete |
| Factor sensitivity methodology | Complete |
| Turnover/risk discussion | Complete |
| Look-ahead guard | Complete |
| Survivorship guard | Complete |
| Historical-test feasibility decision | Complete |
| MODEL CORE / SUPPORT / REJECT decision | Complete |
| Reproducible screen code | Complete |
| Fabricated alpha/backtest claims | None |
| Advanced ML | None |

The only intentionally unfilled artifact is a **live ticker ranking**, because producing one without a dated, traceable current input dataset would violate the task's own pass criterion. Once `screen_input.csv` is populated from verified sources, the supplied code generates it reproducibly.

---

## 17. Evidence Notes

- **SEC EDGAR APIs:** support submissions histories and extracted XBRL company facts. These provide filing/publication-aware raw material for a future point-in-time implementation.
- **Kenneth R. French Data Library:** documents established momentum construction using prior returns while skipping the most recent period, and provides long histories of value/profitability/momentum factor research data.
- **S&P factor methodology context:** S&P maintains transparent quality and multi-factor indices, supporting the general use of interpretable factor categories. This does **not** validate the team's exact weights.
- **WIC-S002 boundary:** Laura's Goal Engine is the client-liability model and excludes WInS results. The equity screen therefore remains support infrastructure.

---

## 18. Checkpoint Summary

**What exists:** a transparent five-factor screen, explicit input contract, missing-data rules, current-universe output schema, sensitivity tests, turnover governance, historical-testing gate, validation checklist and executable Python implementation.

**What is claimed:** the screen is useful for disciplined research prioritization.

**What is not claimed:** predictive alpha, optimized weights, guaranteed outperformance, or client-level return forecasts.

**Decision:** **MODEL SUPPORT.**
