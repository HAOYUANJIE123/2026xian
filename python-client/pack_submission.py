#!/usr/bin/env python3
"""Build lychee-python-client.zip for platform submission."""

from __future__ import annotations

import argparse
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

from pack_checks import validate_zip

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "lychee-python-client.zip"
TOP_LEVEL = ["start.sh", "basic_client.py", "pyproject.toml"]
VALIDATE = ROOT / "validate_before_upload.py"


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
        "--skip-validate",
        action="store_true",
        help="Skip validate_before_upload (NOT for platform uploads)",
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

    if not args.skip_validate:
        cmd = [sys.executable, str(VALIDATE)]
        print("Running validate_before_upload.py ...", flush=True)
        result = subprocess.run(cmd, cwd=str(ROOT))
        if result.returncode != 0:
            raise SystemExit(result.returncode)

    print(f"Building {out}...", flush=True)
    build_zip(out)

    print("Validating zip...", flush=True)
    validate_zip(out)

    print(f"Created {out}", flush=True)


if __name__ == "__main__":
    main()
