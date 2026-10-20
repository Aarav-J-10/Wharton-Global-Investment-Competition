"""Model constants and configuration loading.

The eleven-factor table is the single source of truth for weights, families
and directions; every other module (live screen, backtest, validator) reads it
from here so a scoring-direction defect cannot hide in a second copy.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config" / "competition_v1.yaml"


@dataclass(frozen=True)
class Factor:
    name: str
    weight: float
    direction: int  # +1 higher is better, -1 lower is better
    family: str
    label: str
    formula: str


FACTORS: tuple[Factor, ...] = (
    Factor("roic", 0.12, 1, "QUALITY", "ROIC",
           "EBIT_TTM*(1-effective_tax_rate) / average(IC_latest, IC_prior_year)"),
    Factor("fcf_margin", 0.10, 1, "QUALITY", "FCF margin", "(CFO_TTM - CapEx_TTM) / Revenue_TTM"),
    Factor("net_debt_ebitda", 0.08, -1, "QUALITY", "Net debt / EBITDA",
           "(Debt - Cash) / (EBIT_TTM + D&A_TTM); EBITDA<=0 -> unfavorable sentinel"),
    Factor("fcf_yield", 0.10, 1, "VALUATION", "FCF yield", "FCF_TTM / market capitalization"),
    Factor("ev_ebit", 0.10, -1, "VALUATION", "EV / EBIT",
           "(MarketCap + Debt + Preferred + NCI - Cash) / EBIT_TTM; EBIT<=0 -> unfavorable sentinel"),
    Factor("revenue_cagr_3y", 0.10, 1, "GROWTH", "Revenue CAGR 3Y", "(Rev_FY0 / Rev_FY-3)^(1/3) - 1"),
    Factor("eps_cagr_3y", 0.10, 1, "GROWTH", "EPS CAGR 3Y",
           "(EPS_FY0 / EPS_FY-3)^(1/3) - 1, split-adjusted; nonpositive endpoint -> unfavorable sentinel"),
    Factor("momentum_12_1", 0.12, 1, "MOMENTUM", "Momentum 12-1", "TRI[t-21] / TRI[t-252] - 1"),
    Factor("momentum_6_1", 0.08, 1, "MOMENTUM", "Momentum 6-1", "TRI[t-21] / TRI[t-126] - 1"),
    Factor("volatility_252", 0.05, -1, "RISK", "Volatility 252d", "stdev(252 daily TR returns) * sqrt(252)"),
    Factor("max_drawdown_252", 0.05, -1, "RISK", "Max drawdown 252d", "max(1 - TRI/running_max(TRI)) over 252 sessions"),
)

FACTOR_NAMES = tuple(f.name for f in FACTORS)
WEIGHTS = {f.name: f.weight for f in FACTORS}
DIRECTIONS = {f.name: f.direction for f in FACTORS}
FAMILY_OF = {f.name: f.family for f in FACTORS}
FAMILIES = tuple(dict.fromkeys(f.family for f in FACTORS))
FAMILY_WEIGHTS = {fam: math.fsum(f.weight for f in FACTORS if f.family == fam) for fam in FAMILIES}

# Factor outcome states. VALID and UNFAVORABLE are the only states that can
# contribute to a composite; everything else blocks the company's rank.
VALID = "VALID"
UNFAVORABLE = "ECONOMICALLY_UNFAVORABLE"
SCOREABLE_STATES = frozenset({VALID, UNFAVORABLE})

assert abs(math.fsum(WEIGHTS.values()) - 1.0) < 1e-12
assert {k: round(v, 10) for k, v in FAMILY_WEIGHTS.items()} == {
    "QUALITY": 0.30, "VALUATION": 0.20, "GROWTH": 0.20, "MOMENTUM": 0.20, "RISK": 0.10}


def load_config(path: str | Path | None = None) -> dict:
    with open(path or DEFAULT_CONFIG, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    lo, hi = cfg["scoring"]["winsor_quantiles"]
    if not 0 <= lo < hi <= 1:
        raise ValueError("Invalid winsor quantiles")
    if cfg["scoring"]["min_valid_peers_per_metric"] < 2:
        raise ValueError("Peer minimum must be at least 2")
    return cfg


def family_weights_to_metric_weights(family_weights: dict[str, float]) -> dict[str, float]:
    """Rescale metric weights to new family weights, preserving within-family ratios."""
    total = math.fsum(family_weights.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError("Family weights must sum to 1")
    return {f.name: f.weight / FAMILY_WEIGHTS[f.family] * family_weights[f.family] for f in FACTORS}
