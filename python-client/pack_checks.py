"""Preflight checks run before building the submission ZIP."""

from __future__ import annotations

import stat
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REQUIRED_TOP_LEVEL = ("start.sh", "basic_client.py", "pyproject.toml")
REQUIRED_PACKAGE_FILES = (
    "lychee_basic_client/__init__.py",
    "lychee_basic_client/cli.py",
    "lychee_basic_client/strategy.py",
    "lychee_basic_client/session.py",
)


def check_source_tree() -> None:
    missing = [name for name in REQUIRED_TOP_LEVEL if not (ROOT / name).is_file()]
    for rel in REQUIRED_PACKAGE_FILES:
        if not (ROOT / rel).is_file():
            missing.append(rel)
    if missing:
        raise SystemExit(f"preflight failed: missing source files: {', '.join(missing)}")

    start_sh = ROOT / "start.sh"
    if not start_sh.read_text(encoding="utf-8").startswith("#!/"):
        raise SystemExit("preflight failed: start.sh must begin with a shebang")


def run_unit_tests() -> None:
    suite = unittest.TestLoader().discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(f"preflight failed: {len(result.failures)} failed, {len(result.errors)} error(s)")


def validate_zip(zip_path: Path) -> None:
    if not zip_path.is_file():
        raise SystemExit(f"postflight failed: zip not found: {zip_path}")

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        if not names:
            raise SystemExit("postflight failed: zip is empty")

        for name in REQUIRED_TOP_LEVEL:
            if name not in names:
                raise SystemExit(f"postflight failed: zip missing {name}")

        for rel in REQUIRED_PACKAGE_FILES:
            if rel not in names:
                raise SystemExit(f"postflight failed: zip missing {rel}")

        for name in names:
            if name.endswith("/"):
                continue
            if "\\" in name or name.startswith("/"):
                raise SystemExit(f"postflight failed: invalid zip path {name!r}")
            parts = name.split("/")
            if len(parts) > 1 and parts[0] != "lychee_basic_client":
                raise SystemExit(f"postflight failed: unexpected zip entry {name!r}")

        info = zf.getinfo("start.sh")
        mode = (info.external_attr >> 16) & 0o7777
        if not mode & stat.S_IXUSR:
            raise SystemExit("postflight failed: start.sh is not marked executable in zip")

        if "lychee_basic_client/strategy.py" not in names:
            raise SystemExit("postflight failed: strategy.py missing from zip")

    print(f"postflight ok: {zip_path.name} ({len(names)} entries, start.sh executable)")
