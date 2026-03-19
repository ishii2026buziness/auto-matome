"""Standard CLI entrypoint for auto-matome."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date

from common.contracts import JobStatus

from pipeline import ROOT, run_pipeline


def smoke() -> dict[str, object]:
    sources_path = ROOT / "config" / "sources.yaml"
    site_package = ROOT / "site" / "package.json"
    return {
        "sources_config_exists": sources_path.exists(),
        "site_package_exists": site_package.exists(),
        "package_root": str(ROOT),
    }


def check() -> dict[str, object]:
    return {
        "output_dir_exists": (ROOT / "output").exists(),
        "artifacts_dir": str(ROOT / "artifacts"),
        "cli_module": "cli",
    }


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="auto-matome")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--run-date", type=_parse_date, help="Override logical run date (YYYY-MM-DD)")

    subparsers.add_parser("smoke")
    subparsers.add_parser("check")
    args = parser.parse_args(argv)

    if args.command == "run":
        result = asyncio.run(run_pipeline(run_date=args.run_date))
        print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return 1 if result.status == JobStatus.FAILED else 0

    if args.command == "smoke":
        print(json.dumps({"job": "auto-matome", "command": "smoke", "result": smoke()}, ensure_ascii=False, indent=2))
        return 0

    print(json.dumps({"job": "auto-matome", "command": "check", "result": check()}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
