#!/usr/bin/env python3
"""Build lychee-python-client.zip for platform submission."""

from __future__ import annotations

import stat
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / "lychee-python-client.zip"
TOP_LEVEL = ["start.sh", "basic_client.py", "pyproject.toml"]


def main() -> None:
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
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

    print(f"Created {OUT} ({len(zipfile.ZipFile(OUT).namelist())} files)")


if __name__ == "__main__":
    main()
