"""``python -m multicloud_network_mcp.contracts <command>`` -- the
conformance CLI this milestone's validation step requires.

    python -m multicloud_network_mcp.contracts validate contracts/examples
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from multicloud_network_mcp.contracts.validate import validate_directory


def _cmd_validate(args: argparse.Namespace) -> int:
    directory = Path(args.directory)
    if not directory.is_dir():
        print(f"error: {directory} is not a directory", file=sys.stderr)
        return 2

    report = validate_directory(directory)
    if not report.results:
        print(f"error: no *.json example files found under {directory}", file=sys.stderr)
        return 2

    for result in report.results:
        status = "PASS" if result.passed else "FAIL"
        print(f"{status}  {result.path}  (type={result.resource_type_slug})")
        for error in result.errors:
            print(f"      {error}")

    passed = sum(1 for r in report.results if r.passed)
    total = len(report.results)
    print(f"\n{passed}/{total} example(s) passed.")

    return 0 if report.passed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="multicloud_network_mcp.contracts")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate",
        help=(
            "Validate every *.json example under a directory against its matching "
            "generated JSON Schema AND the matching typed Pydantic model."
        ),
    )
    validate_parser.add_argument(
        "directory", help="Directory of example JSON files (searched recursively)."
    )
    validate_parser.set_defaults(func=_cmd_validate)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
