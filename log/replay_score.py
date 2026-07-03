#!/usr/bin/env python3
"""Print replay scores (replaces manual battle screenshots)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python-client"))

from replay_gate import audit_outcome, detect_player_id, load_frames


def print_replay_report(path: Path, player_id: int | None = None) -> None:
    frames = load_frames(path)
    if not frames:
        print(f"{path}: empty")
        return

    pid = detect_player_id(path, player_id)
    last = frames[-1]
    me = next(p for p in last.get("players", []) if p.get("playerId") == pid)
    opp = next(p for p in last.get("players", []) if p.get("playerId") != pid)
    audit = audit_outcome(path, pid)

    print(f"=== {path.name} ===")
    print(f"rounds: {last.get('round') or frames[0].get('durationRound')}")
    print()
    print("我方")
    print(f"  总分: {me.get('totalScore')}")
    print(f"  送达: {'是' if me.get('delivered') else '否'}")
    detail = me.get("scoreDetail") or {}
    print(f"  送达分: {detail.get('delivery', 0)}")
    print(f"  任务分: {detail.get('tasks', 0)}")
    print(f"  好果分: {detail.get('goodFruit', 0)}")
    print(f"  鲜度分: {detail.get('freshness', 0)}")
    print(f"  时间分: {detail.get('time', 0)}")
    print(f"  赏金分: {detail.get('bounty', 0)}")
    print(f"  扣分: {detail.get('penalty', 0)}")
    print(f"  鲜度: {me.get('freshness')}")
    print()
    print("对手")
    print(f"  总分: {opp.get('totalScore')}")
    print(f"  送达: {'是' if opp.get('delivered') else '否'}")
    if audit.rejects:
        print(f"  拒动作: {dict(audit.rejects)}")


def main() -> None:
    paths = [Path(p) for p in sys.argv[1:]] or [
        Path("log/2614/replay (12).txt"),
        Path("log/2616/replay (11).txt"),
    ]
    root = Path(__file__).resolve().parent.parent
    for path in paths:
        full = path if path.is_file() else root / path
        if full.is_file():
            print_replay_report(full)
            print()


if __name__ == "__main__":
    main()
