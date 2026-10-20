"""Current-universe screen: snapshot -> spec section 15 artifacts.

Outputs are deterministic functions of (snapshot, config, code). Wall-clock
information is confined to RUN_LOG.json so reruns can be compared byte-for-byte.
"""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from . import __version__
from .accounting.fundamentals import IssuerFacts
from .config import FACTOR_NAMES, FACTORS, FAMILIES, ROOT, WEIGHTS, load_config
from .cross_section import FundamentalsCache, blocked_factor_summary, build_cross_section, research_states
from .factors import PriceSeries
from .scoring import diversified_view, score_universe
from .sensitivity import factor_correlation, run_sensitivity
from .snapshot import Snapshot
from .util import canonical_json, sha256_bytes, sha256_file, utc_now, write_csv, write_json

log = logging.getLogger("wic.pipeline")


def git_commit() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def code_hash() -> str:
    files = sorted((ROOT / "wic").rglob("*.py"))
    return sha256_bytes(b"".join(p.relative_to(ROOT).as_posix().encode() + b"\0" + p.read_bytes() for p in files))


def load_market(snap: Snapshot) -> tuple[pd.DataFrame, dict[str, PriceSeries]]:
    prices = snap.prices()
    series = {t: PriceSeries(g) for t, g in prices.groupby("ticker", sort=False)}
    return prices, series


def load_issuers(snap: Snapshot, ticker_for_cik: dict[int, str], series: dict[str, PriceSeries]) -> dict[int, IssuerFacts]:
    facts = snap.facts()
    issuers = {}
    for cik, g in facts.groupby("cik", sort=True):
        t = ticker_for_cik.get(int(cik))
        splits = series[t].splits if t in series else None
        issuers[int(cik)] = IssuerFacts(int(cik), g, splits)
    return issuers


def reference_session(series: dict[str, PriceSeries], cutoff: pd.Timestamp) -> pd.Timestamp:
    spy = series.get("SPY")
    if spy is None:
        raise RuntimeError("SPY benchmark prices missing; cannot establish the latest completed session")
    i = spy.index_at(cutoff)
    return pd.Timestamp(spy.dates[i])


FACTOR_DICTIONARY = pd.DataFrame([{
    "factor": f.name, "label": f.label, "family": f.family, "weight": f.weight,
    "direction": "HIGHER_IS_BETTER" if f.direction > 0 else "LOWER_IS_BETTER", "formula": f.formula}
    for f in FACTORS])


def run_screen(snapshot_path: str | Path, out_root: str | Path, config_path: str | Path | None = None) -> Path:
    cfg = load_config(config_path)
    snap = Snapshot(snapshot_path)
    cutoff = snap.cutoff
    cfg_hash = sha256_bytes(canonical_json(cfg).encode())[:12]
    run_id = f"{snap.manifest['snapshot_id']}__{cfg['model_version']}__cfg{cfg_hash}"
    out = Path(out_root) / run_id
    out.mkdir(parents=True, exist_ok=True)
    started = utc_now()

    universe = snap.universe()
    _, series = load_market(snap)
    ref = reference_session(series, cutoff)
    ticker_for_cik = {int(c): t for c, t in zip(universe["cik"], universe["yahoo_ticker"]) if pd.notna(c)}
    issuers = load_issuers(snap, ticker_for_cik, series)
    funds = FundamentalsCache(issuers)

    cs = build_cross_section(ref, ref, universe, series, funds, cfg)
    eligible = cs.loc[cs["eligibility_status"].eq("ELIGIBLE")].copy()
    sc = cfg["scoring"]
    ranked = score_universe(eligible, min_peers=sc["min_valid_peers_per_metric"],
                            winsor=tuple(sc["winsor_quantiles"]), sentinel_score=sc["economic_sentinel_score"])
    ranked = research_states(ranked, cfg)
    ranked["blocked_factors"] = ranked.apply(blocked_factor_summary, axis=1)

    complete = ranked.loc[ranked["rank"].notna()].sort_values("rank")
    top20 = complete.head(cfg["queues"]["research_queue_size"])
    top10 = complete.head(cfg["queues"]["priority_queue_size"])
    div = diversified_view(complete, cfg["queues"]["priority_queue_size"], cfg["queues"]["max_priority_names_same_sector"])

    # ---------------- artifacts
    display = ["rank", "ticker", "security", "sector", "composite", *[f.lower() for f in FAMILIES],
               *[f"{n}_score" for n in FACTOR_NAMES], *FACTOR_NAMES, "research_state", "core_policy_status",
               "core_policy_failures", "raw_close", "market_cap", "liquidity_63", "period_end", "max_filed_used",
               "accounting_flags", "cik", "security_id"]
    for c in display:
        if c not in ranked:
            ranked[c] = np.nan
    write_csv(out / "ranked_universe.csv", ranked[display + ["blocked_factors"]])
    write_csv(out / "research_queue_top20.csv", top20[display])
    write_csv(out / "priority_queue_top10.csv", top10[display])
    if len(div):
        write_csv(out / "diversified_research_view_top10.csv",
                  div[["diversified_rank", "sector_cap_exception", *display]])

    audit = cs[["ticker", "security", "sector", "cik", "eligibility_status", "eligibility_reason", "raw_close",
                "liquidity_63", "last_price_date", "price_status"]].merge(
        ranked[["ticker", "research_state", "rank", "blocked_factors"]], on="ticker", how="left")
    audit.loc[audit["research_state"].isna(), "research_state"] = audit["eligibility_status"]
    write_csv(out / "universe_audit.csv", audit.sort_values("ticker"))

    long = []
    for _, r in ranked.iterrows():
        for n in FACTOR_NAMES:
            long.append({"ticker": r["ticker"], "security_id": r["security_id"], "sector": r["sector"], "factor": n,
                         "raw_value": r[n], "status": r[f"{n}_status"], "detail": r[f"{n}_detail"],
                         "score": r[f"{n}_score"], "score_status": r[f"{n}_score_status"],
                         "valid_peers": r[f"{n}_peers"], "weight": WEIGHTS[n]})
    factor_values = pd.DataFrame(long)
    write_csv(out / "factor_values.csv", factor_values)
    write_csv(out / "factor_dictionary.csv", FACTOR_DICTIONARY)

    coverage = coverage_report(cs, ranked)
    write_csv(out / "coverage_report.csv", coverage)
    missing = (factor_values.loc[~factor_values["score_status"].isin(["VALID", "ECONOMICALLY_UNFAVORABLE"])]
               .groupby(["factor", "score_status"]).size().rename("count").reset_index()
               .sort_values(["factor", "count"], ascending=[True, False]))
    write_csv(out / "missing_reasons.csv", missing)

    sens = run_sensitivity(eligible, ranked, cfg) if len(complete) >= 20 else pd.DataFrame()
    write_csv(out / "sensitivity_results.csv", sens)
    corr = factor_correlation(ranked)
    write_csv(out / "factor_correlation.csv", corr.reset_index().rename(columns={"index": "factor"}))

    srcs = pd.read_csv(snap.path / "sec_sources.csv")
    source_map = cs[["ticker", "cik", "period_end", "max_filed_used", "last_price_date"]].merge(
        srcs[["cik", "url", "raw_sha256", "entity_name"]], on="cik", how="left")
    source_map["price_source"] = "Yahoo Finance via yfinance (snapshot prices.parquet)"
    write_csv(out / "source_map.csv", source_map.sort_values("ticker"))
    write_lineage(out / "lineage.jsonl", cs, funds, ref, cfg)
    if len(top10):
        from .risk import book_risk
        write_json(out / "priority_queue_risk.json", {
            "TOP10": book_risk(series, top10, ref),
            "DIVERSIFIED_VIEW": book_risk(series, div, ref) if len(div) else None})

    # ---------------- validation, gates, manifest
    from .validate import validate_run
    validation = validate_run(out, cutoff=cutoff)
    write_json(out / "VALIDATION.json", validation)
    gates = {
        "snapshot_hashes_verified": True,
        "independent_validator_passed": validation["passed"],
        "at_least_10_complete_scores": int(len(complete)) >= 10,
        "no_source_dates_after_cutoff": validation["checks"].get("source_dates_le_cutoff", False),
    }
    published = all(gates.values())
    if not published:
        for f in ("priority_queue_top10.csv", "research_queue_top20.csv", "diversified_research_view_top10.csv",
                  "priority_queue_risk.json"):
            (out / f).unlink(missing_ok=True)
    status = {"run_id": run_id, "status": "RANKING_PUBLISHED" if published else "NO VALIDATED RANKING AVAILABLE",
              "publication_gates": gates, "cutoff": cutoff.date().isoformat(), "market_session": ref.date().isoformat(),
              "constituents": int(len(cs)), "eligible": int(len(eligible)), "complete_scores": int(len(complete)),
              "complete_pct_of_eligible": round(100 * len(complete) / max(len(eligible), 1), 2)}
    write_json(out / "STATUS.json", status)
    memo(out, status, coverage, sens, corr, top10, div, cfg, snap)
    manifest = {"run_id": run_id, "model_version": cfg["model_version"], "package_version": __version__,
                "config_sha256_12": cfg_hash, "code_sha256": code_hash(), "snapshot_id": snap.manifest["snapshot_id"],
                "snapshot_manifest_sha256": sha256_file(snap.path / "MANIFEST.json"), "cutoff": status["cutoff"],
                "market_session": status["market_session"], "universe_source": snap.sources.get("universe", {}),
                "counts": {k: status[k] for k in ("constituents", "eligible", "complete_scores")},
                "status": status["status"],
                "outputs": {p.name: sha256_file(p) for p in sorted(out.iterdir())
                            if p.is_file() and p.name not in ("run_manifest.json", "RUN_LOG.json")}}
    write_json(out / "run_manifest.json", manifest)
    write_json(out / "RUN_LOG.json", {"started_utc": started, "finished_utc": utc_now(), "git_commit": git_commit()})
    log.info("Screen %s: %s (%d complete / %d eligible)", run_id, status["status"], len(complete), len(eligible))
    return out


def coverage_report(cs: pd.DataFrame, ranked: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for sector, g in cs.groupby("sector"):
        r = ranked.loc[ranked["sector"].eq(sector)]
        row = {"sector": sector, "constituents": len(g),
               "outside_standard_model": int(g["eligibility_status"].eq("OUTSIDE_STANDARD_MODEL").sum()),
               "duplicate_classes": int(g["eligibility_status"].eq("DUPLICATE_CLASS_EXCLUDED").sum()),
               "data_blocked_pre_scoring": int(g["eligibility_status"].isin(["DATA_BLOCKED", "INELIGIBLE"]).sum()),
               "eligible": len(r), "complete_scores": int(r["rank"].notna().sum()) if len(r) else 0}
        for n in FACTOR_NAMES:
            row[f"{n}_valid"] = int(r[f"{n}_status"].eq("VALID").sum()) if len(r) else 0
            row[f"{n}_scored"] = int(r[f"{n}_score"].notna().sum()) if len(r) else 0
        rows.append(row)
    df = pd.DataFrame(rows)
    total = df.drop(columns="sector").sum(numeric_only=True)
    total["sector"] = "ALL"
    return pd.concat([df, total.to_frame().T], ignore_index=True)


def write_lineage(path: Path, cs: pd.DataFrame, funds: FundamentalsCache, ref: pd.Timestamp, cfg: dict) -> None:
    lag = pd.Timedelta(days=cfg["fundamentals"]["filing_lag_days"])
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for _, r in cs.sort_values("ticker").iterrows():
            if r["cik"] is None or pd.isna(r["cik"]):
                continue
            fund = funds.get(int(r["cik"]), ref - lag)
            rec = {"ticker": r["ticker"], "cik": int(r["cik"]), "status": fund.get("status"),
                   "period_end": fund.get("period_end"),
                   "quantities": {k: {"value": v.value, "status": v.status, "lineage": v.lineage}
                                  for k, v in fund.get("q", {}).items()},
                   "revenue_fy": [(e, v, l) for e, v, l in fund.get("rev_hist", [])],
                   "eps_fy_split_adjusted": [(e, v, l) for e, v, l in fund.get("eps_hist", [])]}
            fh.write(canonical_json(rec) + "\n")


def _fmt(x, nd=1):
    return "" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.{nd}f}"


def memo(out: Path, status: dict, coverage: pd.DataFrame, sens: pd.DataFrame, corr: pd.DataFrame,
         top10: pd.DataFrame, div: pd.DataFrame, cfg: dict, snap: Snapshot) -> None:
    fam = sens.loc[sens["kind"].eq("family_weight_shift")] if len(sens) else pd.DataFrame()
    stable = (len(fam) and fam["top20_overlap"].min() >= 0.8)
    flags = int(fam["review_flag"].sum()) if len(fam) else 0
    hi_corr = []
    if corr.notna().any().any():
        for i, a in enumerate(FACTOR_NAMES):
            for b in FACTOR_NAMES[i + 1:]:
                if abs(corr.loc[a, b]) > cfg["sensitivity"]["correlation_flag_abs"]:
                    hi_corr.append(f"{a}~{b} ({corr.loc[a, b]:.2f})")
    published = status["status"] == "RANKING_PUBLISHED"
    decision = "MODEL_SUPPORT" if published else "MODEL_SUPPORT — NO VALIDATED RANKING THIS RUN"
    u = snap.sources.get("universe", {})
    lines = [
        f"# WIC-S003 Model Gate Memo — {status['run_id']}", "",
        f"**Decision:** {decision}", "",
        "This screen ranks companies for research priority. It is **not** a return forecast, an order, "
        "or investment approval. There is no BUY state.", "",
        "## Run facts", "",
        f"- Cutoff: {status['cutoff']} (market session used: {status['market_session']})",
        f"- Universe source: {u.get('source')} revision {u.get('revision_id', 'n/a')} "
        f"({u.get('revision_timestamp', 'n/a')}); {u.get('source_class', '')}",
        f"- Constituents: {status['constituents']}; eligible for standard model: {status['eligible']}; "
        f"complete 11-factor scores: {status['complete_scores']} ({status['complete_pct_of_eligible']}% of eligible)",
        f"- Publication gates: " + ", ".join(f"{k}={v}" for k, v in status["publication_gates"].items()), "",
        "## Coverage by sector", "",
        "| Sector | Constituents | Eligible | Complete |", "|---|---:|---:|---:|"]
    for _, r in coverage.iterrows():
        lines.append(f"| {r['sector']} | {int(r['constituents'])} | {int(r['eligible'])} | {int(r['complete_scores'])} |")
    if published:
        lines += ["", "## Priority queue (raw rank)", "", "| Rank | Ticker | Company | Sector | Composite | Quality | Core policy |",
                  "|---:|---|---|---|---:|---:|---|"]
        for _, r in top10.iterrows():
            lines.append(f"| {int(r['rank'])} | {r['ticker']} | {r['security']} | {r['sector']} | "
                         f"{_fmt(r['composite'])} | {_fmt(r['quality'])} | {r['core_policy_status']} |")
        if len(div):
            lines += ["", "Diversified research view (max 3 per sector): " + ", ".join(div["ticker"])]
    lines += ["", "## Stability", ""]
    if len(fam):
        lines += [f"- ±5pp family-weight shifts: min Top-20 overlap {fam['top20_overlap'].min():.0%}, "
                  f"min Spearman {fam['spearman'].min():.3f}, review flags {flags}.",
                  f"- Interpretation: {'high' if stable else 'moderate/low'} stability; exact ordinal positions "
                  "(e.g. rank 3 vs 5) should not be over-interpreted."]
    else:
        lines.append("- Sensitivity not run (fewer than 20 complete scores).")
    lines += [f"- Factor correlations above {cfg['sensitivity']['correlation_flag_abs']}: "
              + (", ".join(hi_corr) if hi_corr else "none")]
    lines += ["", "## Limits", "",
              "- Universe labels come from a public Wikipedia revision, not licensed S&P DJI data.",
              "- Fundamentals come from SEC XBRL companyfacts with automated concept routes; flagged "
              "conventions (debt-zero inference, NCI/preferred not reported) are listed per company in "
              "ranked_universe.csv `accounting_flags` and lineage.jsonl.",
              "- Financials and Real Estate are outside the standard model (not an investment rejection).",
              "- WInS platform availability is unchecked for every name (WINS_AVAILABILITY_UNCHECKED).",
              "- A high score means 'research this next', never 'buy'."]
    (out / "model_gate_memo.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
