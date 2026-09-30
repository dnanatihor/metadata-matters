"""Command line for download, dry-run, and fixture or live runs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mm.config import configs_dir, load_models_config, load_prices_config, load_run_config
from mm.data.download import main as download_main
from mm.data.fixture import load_fixture
from mm.llm.budget import BudgetExceededError
from mm.paths import repo_root
from mm.report.readme import update_readme
from mm.suite import fixture_summary, run_fixture


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mm")
    sub = parser.add_subparsers(dest="command", required=True)

    download = sub.add_parser("download", help="Download the BIRD dev set.")
    download.add_argument("--dest", type=Path, default=None)

    run = sub.add_parser("run", help="Run one research question.")
    run.add_argument("rq", choices=("rq1", "rq2", "rq3", "rq4"))
    run.add_argument("-c", "--config", type=Path, required=True)
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--fixture", action="store_true")

    report = sub.add_parser("report", help="Write metrics, a plot, and report.md for a run.")
    report.add_argument("run_dir", type=Path)

    sub.add_parser("readme", help="Refresh the README results section from results/.")

    args = parser.parse_args(argv)
    if args.command == "download":
        forwarded = ["--dest", str(args.dest)] if args.dest is not None else []
        return download_main(forwarded)
    if args.command == "readme":
        update_readme(repo_root() / "README.md", repo_root() / "results")
        print("Updated README.md")
        return 0
    if args.command == "report":
        from mm.suite import rebuild_report

        rebuild_report(args.run_dir)
        print(f"Wrote {args.run_dir / 'report.md'}")
        return 0
    return _run(args)


def _run(args: argparse.Namespace) -> int:
    config = load_run_config(args.config)
    if config.rq != args.rq:
        print(f"Config rq {config.rq} does not match {args.rq}", file=sys.stderr)
        return 2
    root = configs_dir()
    prices = load_prices_config(root / "prices.yaml")
    models = load_models_config(root / "models.yaml")
    if not args.fixture:
        print(
            "Live model calls require --fixture in this build, or a budgeted provider.",
            file=sys.stderr,
        )
        return 2
    dataset = load_fixture()
    if args.dry_run:
        count, estimate = fixture_summary(dataset, config, prices, models)
        print(f"items: {count}")
        print(f"estimated_usd: {estimate:.6f}")
        return 0
    output = repo_root() / "results" / args.rq / _run_id()
    try:
        written = run_fixture(dataset, config, prices, models, output, repo_root() / "cache.db")
    except BudgetExceededError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"Wrote {written / 'run.json'}")
    return 0


def _run_id() -> str:
    from datetime import UTC, datetime
    from uuid import uuid4

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid4().hex[:8]}"
