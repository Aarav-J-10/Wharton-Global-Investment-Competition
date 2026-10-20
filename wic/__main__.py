"""Command line: python -m wic {acquire,screen,backtest,verify,all}."""
from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import tempfile
from pathlib import Path

import pandas as pd

from .config import ROOT

DATA = ROOT / "data" / "snapshots"
OUT = ROOT / "outputs"


def _latest_snapshot() -> Path:
    snaps = sorted((p for p in DATA.glob("sp500_*") if (p / "MANIFEST.json").exists()),
                   key=lambda p: (p.name.replace("_current", ""), not p.name.endswith("_current")))
    if not snaps:
        sys.exit("No snapshot found; run `python -m wic acquire` first")
    return snaps[-1]


def cmd_acquire(a) -> Path:
    from .snapshot import acquire, last_completed_session

    cutoff = pd.Timestamp(a.cutoff) if a.cutoff else last_completed_session()
    snap = acquire(cutoff, Path(a.data), cache_dir=Path(a.cache) if a.cache else None,
                   current_only=a.current_only)
    print(f"snapshot: {snap}")
    return snap


def cmd_screen(a) -> Path:
    from .pipeline import run_screen

    out = run_screen(Path(a.snapshot) if a.snapshot else _latest_snapshot(), Path(a.out) / "screen", a.config)
    status = json.loads((out / "STATUS.json").read_text())
    print(json.dumps(status, indent=2))
    top = out / "priority_queue_top10.csv"
    if top.exists():
        t = pd.read_csv(top)
        print(t[["rank", "ticker", "security", "sector", "composite", "quality", "core_policy_status"]].to_string(index=False))
    return out


def cmd_backtest(a) -> Path:
    from .backtest.engine import run_backtest

    out = run_backtest(Path(a.snapshot) if a.snapshot else _latest_snapshot(), Path(a.out) / "backtest", a.config,
                       start=a.start)
    s = json.loads((out / "BACKTEST_SUMMARY.json").read_text())
    for k in ("TOP10", "TOP10_SECTOR_CAPPED", "SCORED_UNIVERSE_EW"):
        p = s["portfolios_net"].get(k, {})
        print(f"{k:22s} CAGR {p.get('cagr', float('nan')):.2%}  Sharpe {p.get('sharpe', float('nan')):.2f}  "
              f"MaxDD {p.get('max_drawdown', float('nan')):.2%}")
    for b, p in s["benchmarks"].items():
        print(f"{b:22s} CAGR {p['cagr']:.2%}  Sharpe {p['sharpe']:.2f}  MaxDD {p['max_drawdown']:.2%}")
    return out


def cmd_verify(a) -> int:
    """Re-run the screen from the snapshot into a temp dir and compare every output hash."""
    from .pipeline import run_screen

    run = Path(a.run)
    man = json.loads((run / "run_manifest.json").read_text())
    snap = Path(a.snapshot) if a.snapshot else DATA / man["snapshot_id"]
    with tempfile.TemporaryDirectory() as tmp:
        again = run_screen(snap, Path(tmp), a.config)
        man2 = json.loads((again / "run_manifest.json").read_text())
    diffs = {k: (v, man2["outputs"].get(k)) for k, v in man["outputs"].items() if man2["outputs"].get(k) != v}
    ok = not diffs and man["code_sha256"] == man2["code_sha256"]
    print(json.dumps({"reproduced": ok, "outputs_compared": len(man["outputs"]), "differences": diffs,
                      "code_sha256_match": man["code_sha256"] == man2["code_sha256"]}, indent=2))
    return 0 if ok else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="wic", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("acquire", "screen", "backtest", "verify", "all"):
        s = sub.add_parser(name)
        s.add_argument("--snapshot")
        s.add_argument("--config")
        s.add_argument("--out", default=str(OUT))
        s.add_argument("--data", default=str(DATA))
        s.add_argument("--cache", help="optional raw SEC payload cache directory")
        s.add_argument("--cutoff", help="YYYY-MM-DD (default: last completed NYSE session)")
        s.add_argument("--start", help="backtest start date override")
        s.add_argument("--run", help="screen run directory to verify")
        s.add_argument("--current-only", action="store_true",
                       help="acquire current constituents only (live screen; not sufficient for the backtest)")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    if a.cmd == "acquire":
        cmd_acquire(a)
    elif a.cmd == "screen":
        cmd_screen(a)
    elif a.cmd == "backtest":
        cmd_backtest(a)
    elif a.cmd == "verify":
        return cmd_verify(a)
    else:
        a.snapshot = str(cmd_acquire(a)) if not a.snapshot else a.snapshot
        a.run = str(cmd_screen(a))
        cmd_backtest(a)
        return cmd_verify(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
