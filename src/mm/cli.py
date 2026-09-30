"""Command line for download, dry-run, and fixture or live runs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mm.config import configs_dir, load_prices_config, load_run_config
from mm.data.download import main as download_main
from mm.data.fixture import load_fixture
from mm.llm.budget import BudgetExceededError
from mm.llm.runner import dry_run_summary, fixture_clients, run_rq1
from mm.paths import repo_root


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

    args = parser.parse_args(argv)
    if args.command == "download":
        forwarded = ["--dest", str(args.dest)] if args.dest is not None else []
        return download_main(forwarded)
    return _run(args)


def _run(args: argparse.Namespace) -> int:
    if args.rq != "rq1":
        print(f"{args.rq} is not available yet", file=sys.stderr)
        return 2
    config = load_run_config(args.config)
    if config.rq != args.rq:
        print(f"Config rq {config.rq} does not match {args.rq}", file=sys.stderr)
        return 2
    prices = load_prices_config(configs_dir() / "prices.yaml")
    if not args.fixture:
        print("Live model calls require a configured chat model. Use --fixture.", file=sys.stderr)
        return 2
    dataset = load_fixture()
    clients = fixture_clients()
    if args.dry_run:
        count, estimate = dry_run_summary(
            dataset=dataset, config=config, prices=prices, clients=clients
        )
        print(f"items: {count}")
        print(f"estimated_usd: {estimate:.6f}")
        return 0
    output = repo_root() / "results" / args.rq / _run_id()
    try:
        written = run_rq1(
            dataset=dataset,
            config=config,
            prices=prices,
            clients=clients,
            output_dir=output,
            cache_path=repo_root() / "cache.db",
        )
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
