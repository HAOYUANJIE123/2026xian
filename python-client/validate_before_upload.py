#!/usr/bin/env python3
"""
One gate before upload. Do not upload until this passes.

  cd python-client
  python validate_before_upload.py

Checks:
  1. unit tests
  2. strategy regression on opponent replays (2614/2616) — mandatory
  3. headless local Demo match (score>=700, delivered) — mandatory if server exists
  4. optional: build zip (--pack)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pack_checks import check_source_tree, run_unit_tests, validate_zip
from pack_submission import OUT, build_zip
from preflight_replay import REQUIRED_REPLAYS, run_preflight

try:
    from local_match import validate_local_match
except ImportError:
    validate_local_match = None  # type: ignore[misc, assignment]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-local-match",
        action="store_true",
        help="Skip headless Demo match (not recommended)",
    )
    parser.add_argument(
        "--skip-opponent-replays",
        action="store_true",
        help="Skip 2614/2616 regression (not recommended)",
    )
    parser.add_argument(
        "--pack",
        action="store_true",
        help="Also build lychee-python-client.zip after all checks pass",
    )
    parser.add_argument(
        "--round-timeout-ms",
        type=int,
        default=80,
        help="Local match round timeout (default 80)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("[1/4] Source tree...", flush=True)
    check_source_tree()

    print("[2/4] Unit tests...", flush=True)
    run_unit_tests()

    if args.skip_opponent_replays:
        print("[3/4] Opponent replay regression SKIPPED", flush=True)
    else:
        missing = [p for p in REQUIRED_REPLAYS if not p.is_file()]
        if missing:
            raise SystemExit(
                "missing opponent replays (required for regression):\n"
                + "\n".join(f"  - {p}" for p in missing)
                + "\nPut latest 2614/2616 replays under log/ before upload."
            )
        print("[3/4] Opponent replay regression...", flush=True)
        run_preflight(REQUIRED_REPLAYS, strict=True)

    if args.skip_local_match:
        print("[4/4] Local Demo match SKIPPED", flush=True)
    else:
        if validate_local_match is None:
            raise SystemExit("local_match module unavailable")
        print("[4/4] Local Demo match (headless)...", flush=True)
        validate_local_match(round_timeout_ms=args.round_timeout_ms)

    print("\nALL CHECKS PASSED — safe to upload.", flush=True)

    if args.pack:
        print(f"\nBuilding {OUT}...", flush=True)
        build_zip(OUT)
        validate_zip(OUT)
        print(f"Created {OUT}", flush=True)


if __name__ == "__main__":
    main()
