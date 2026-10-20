"""Predeclared sensitivity suite (spec section 14). Measures stability only."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from .config import FACTOR_NAMES, FAMILIES, FAMILY_WEIGHTS, family_weights_to_metric_weights
from .scoring import score_universe


def family_variants(shift: float) -> list[tuple[str, dict]]:
    out = []
    for fam in FAMILIES:
        for sign in (+1, -1):
            new = dict(FAMILY_WEIGHTS)
            new[fam] = FAMILY_WEIGHTS[fam] + sign * shift
            rest = 1.0 - new[fam]
            others = [f for f in FAMILIES if f != fam]
            base_rest = sum(FAMILY_WEIGHTS[f] for f in others)
            for f in others:
                new[f] = FAMILY_WEIGHTS[f] / base_rest * rest
            out.append((f"{fam.lower()}_{'+' if sign > 0 else '-'}{int(round(shift * 100))}pp", new))
    out.append(("equal_family_20x5", {f: 0.2 for f in FAMILIES}))
    out.append(("quality_heavy_40_15x4", {"QUALITY": .40, "VALUATION": .15, "GROWTH": .15,
                                         "MOMENTUM": .15, "RISK": .15}))
    out.append(("momentum_light_35_20_20_10_15", {"QUALITY": .35, "VALUATION": .20, "GROWTH": .20,
                                                 "MOMENTUM": .10, "RISK": .15}))
    return out


def compare(base: pd.DataFrame, alt: pd.DataFrame, name: str, kind: str, cfg: dict) -> dict:
    b = base.loc[base["rank"].notna()].set_index("security_id")["rank"].astype(float)
    a = alt.loc[alt["rank"].notna()].set_index("security_id")["rank"].astype(float)
    common = b.index.intersection(a.index)
    b10, b20 = set(b[b <= 10].index), set(b[b <= 20].index)
    a10, a20 = set(a[a <= 10].index), set(a[a <= 20].index)
    rho = spearmanr(b[common], a[common]).statistic if len(common) > 2 else np.nan
    diff = (b[common] - a[common]).abs()
    top20_moves = (b.loc[list(b20 & set(common))] - a.loc[list(b20 & set(common))]).abs()
    jac = len(b20 & a20) / len(b20 | a20) if (b20 | a20) else np.nan
    sector = alt.loc[alt["rank"].le(20) & alt["rank"].notna()].groupby("sector").size()
    s = cfg["sensitivity"]
    flag = kind == "family_weight_shift" and ((rho < s["flag_spearman_below"]) or (jac < s["flag_top20_jaccard_below"]))
    return {"variant": name, "kind": kind, "complete_scores": int(len(a)), "common_ranked": int(len(common)),
            "top10_overlap": len(b10 & a10) / 10 if b10 else np.nan,
            "top20_overlap": len(b20 & a20) / 20 if b20 else np.nan, "top20_jaccard": jac,
            "spearman": rho, "median_abs_rank_change": float(diff.median()) if len(diff) else np.nan,
            "max_rank_change_baseline_top20": float(top20_moves.max()) if len(top20_moves) else np.nan,
            "entering_top20": ";".join(sorted(x.split(":")[1] for x in a20 - b20)),
            "leaving_top20": ";".join(sorted(x.split(":")[1] for x in b20 - a20)),
            "top20_sector_mix": ";".join(f"{k}={v}" for k, v in sector.items()),
            "review_flag": bool(flag)}


def run_sensitivity(eligible: pd.DataFrame, base: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    sc, s = cfg["scoring"], cfg["sensitivity"]
    kw = dict(min_peers=sc["min_valid_peers_per_metric"], winsor=tuple(sc["winsor_quantiles"]),
              sentinel_score=sc["economic_sentinel_score"])
    rows = [compare(base, base, "baseline", "baseline", cfg)]
    for name, fw in family_variants(s["family_shift_pp"]):
        alt = score_universe(eligible, weights=family_weights_to_metric_weights(fw), **kw)
        rows.append(compare(base, alt, name, "family_weight_shift" if "pp" in name else "family_weight_alt", cfg))
    for lo, hi in s["winsor_variants"]:
        alt = score_universe(eligible, **{**kw, "winsor": (lo, hi)})
        rows.append(compare(base, alt, f"winsor_{lo:g}_{hi:g}", "normalization", cfg))
    for m in s["peer_minimum_variants"]:
        alt = score_universe(eligible, **{**kw, "min_peers": m})
        rows.append(compare(base, alt, f"peer_min_{m}", "peer_minimum", cfg))
    for floor in s["price_floor_variants"]:
        sub = eligible.loc[eligible["raw_close"].fillna(0) >= floor]
        alt = score_universe(sub, **kw)
        rows.append(compare(base, alt, f"price_floor_{floor:g}", "universe", cfg))
    return pd.DataFrame(rows)


def factor_correlation(ranked: pd.DataFrame) -> pd.DataFrame:
    cols = [f"{n}_score" for n in FACTOR_NAMES]
    sub = ranked.loc[ranked["rank"].notna(), cols]
    corr = sub.corr(method="spearman") if len(sub) > 2 else pd.DataFrame(np.nan, index=cols, columns=cols)
    corr.index = FACTOR_NAMES
    corr.columns = FACTOR_NAMES
    return corr
