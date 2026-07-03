#!/usr/bin/env python3
"""Create or refresh an annotated git tag from VERSION_TAGS.md."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = Path(__file__).resolve().parent / "VERSION_TAGS.md"


def parse_section(doc: str, tag: str) -> tuple[str | None, str | None]:
    pattern = rf"^## {re.escape(tag)}([^\n]*)\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, doc, re.MULTILINE | re.DOTALL)
    if not match:
        return None, None
    header_rest = match.group(1)
    body = match.group(2).strip()
    commit_match = re.search(r"`([0-9a-f]{7,40})`", header_rest)
    commit = commit_match.group(1) if commit_match else None
    lines = [line.rstrip() for line in body.splitlines()]
    return "\n".join(lines), commit


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", help="Tag name, e.g. v4.2-contest-guard")
    parser.add_argument(
        "--recommend",
        action="store_true",
        help="Append '(recommended)' to the tag title line",
    )
    parser.add_argument(
        "--commit",
        help="Commit to tag (default: parse from VERSION_TAGS.md header backticks)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing tag",
    )
    args = parser.parse_args()

    if not DOC.exists():
        print(f"missing {DOC}", file=sys.stderr)
        return 1

    section, doc_commit = parse_section(DOC.read_text(encoding="utf-8"), args.tag)
    if section is None:
        print(f"no section for tag {args.tag!r} in {DOC.name}", file=sys.stderr)
        return 1

    commit = args.commit or doc_commit or git("rev-parse", "HEAD")
    commit = git("rev-parse", f"{commit}^{{commit}}")

    title = args.tag
    if args.recommend:
        title = f"{args.tag} (recommended)"

    message = f"{title}\n\n{section}\n\ncommit: {commit}\n"
    cmd = ["tag", "-a", args.tag, "-m", message]
    if args.force:
        cmd.insert(1, "-f")
    cmd.append(commit)

    subprocess.run(["git", "-C", str(ROOT), *cmd], check=True)
    print(f"Tagged {args.tag} at {commit[:8]}")
    print("Preview:")
    print(message[:800])
    if len(message) > 800:
        print("...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
