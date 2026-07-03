#!/usr/bin/env python3
"""Build lychee-python-client.zip for platform submission."""

from __future__ import annotations

import argparse
import stat
import zipfile
from pathlib import Path

from pack_checks import check_source_tree, run_unit_tests, validate_zip

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "lychee-python-client.zip"
TOP_LEVEL = ["start.sh", "basic_client.py", "pyproject.toml"]


def build_zip(out: Path) -> None:
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in TOP_LEVEL:
            path = ROOT / name
            if name == "start.sh":
                info = zipfile.ZipInfo(name)
                info.external_attr = (
                    stat.S_IRUSR
                    | stat.S_IWUSR
                    | stat.S_IXUSR
                    | stat.S_IRGRP
                    | stat.S_IXGRP
                    | stat.S_IROTH
                    | stat.S_IXOTH
                ) << 16
                zf.writestr(info, path.read_bytes())
            else:
                zf.write(path, name)

        for path in sorted((ROOT / "lychee_basic_client").rglob("*.py")):
            zf.write(path, path.relative_to(ROOT).as_posix())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip unit tests (not recommended for platform uploads)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=OUT,
        help=f"Output zip path (default: {OUT})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out = args.output.resolve()

    print("[1/4] Checking source tree...", flush=True)
    check_source_tree()

    if args.skip_tests:
        print("[2/4] Skipping unit tests (--skip-tests)", flush=True)
    else:
        print("[2/4] Running unit tests...", flush=True)
        run_unit_tests()

    print(f"[3/4] Building {out}...", flush=True)
    build_zip(out)

    print("[4/4] Validating zip...", flush=True)
    validate_zip(out)

    print(f"Created {out}", flush=True)


if __name__ == "__main__":
    main()
