#!/usr/bin/env python3
"""Analyze one or more replay files."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

PID = 2941


def load_frames(path: str) -> list[dict]:
    frames = []
    for i, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            frames.append(json.loads(line))
        except json.JSONDecodeError as exc:
            print(f"  skip line {i}: {exc}")
    return frames


def analyze(path: str) -> None:
    frames = load_frames(path)
    if not frames:
        return
    last = frames[-1]
    me = next(p for p in last["players"] if p["playerId"] == PID)
    opp = next(p for p in last["players"] if p["playerId"] != PID)

    rejects: Counter[str] = Counter()
    guard_sets: list[str] = []
    breaks = forced = delivers = verifies = blocked = forbidden = 0
    tasks: list[int] = []
    milestones: list[tuple] = []

    for fr in frames[1:]:
        rnd = fr.get("round")
        for m in fr.get("messages", []):
            t = m.get("type")
            p = m.get("payload") or {}
            if t == "ACTION_REJECTED" and p.get("playerId") == PID:
                reason = p.get("reason") or p.get("errorCode", "?")
                rejects[reason] += 1
                if reason == "MOVING_ACTION_FORBIDDEN":
                    forbidden += 1
            if t == "GUARD_SET":
                guard_sets.append(f"r{rnd} {p.get('nodeId')} def={p.get('defense')}")
            if t == "BREAK_GUARD" and p.get("playerId") == PID:
                breaks += 1
            if t == "FORCED_PASS" and p.get("playerId") == PID:
                forced += 1
            if t in ("DELIVER_SUCCESS", "DELIVER") and p.get("playerId") == PID:
                delivers += 1
            if t == "VERIFY_GATE_COMPLETE" and p.get("playerId") == PID:
                verifies += 1
            if t == "MOVE_BLOCKED_BY_GUARD" and p.get("playerId") == PID:
                blocked += 1
            if t == "TASK_COMPLETE" and p.get("playerId") == PID:
                tasks.append(rnd)

        pl = next((x for x in fr.get("players", []) if x.get("playerId") == PID), None)
        if pl and rnd in (1, 42, 187, 191, 298, 330, 365, 490, 517, 568, 574, 600):
            milestones.append(
                (
                    rnd,
                    pl.get("currentNodeId"),
                    pl.get("state"),
                    round(pl.get("freshness", 0), 1),
                    pl.get("nextNodeId"),
                )
            )

    meta = frames[0]
    match_id = meta.get("matchId", "?")
    sd = me.get("scoreDetail") or {}
    print(f"\n{'=' * 60}\n{path}")
    print(f"  match={match_id}")
    print(f"  me: total={me.get('totalScore')} delivered={me.get('delivered')} fresh={me.get('freshness'):.2f}")
    print(f"    detail: delivery={sd.get('delivery')} tasks={sd.get('tasks')} good={sd.get('goodFruit')}")
    print(f"  opp ({opp.get('name')}): total={opp.get('totalScore')} delivered={opp.get('delivered')}")
    print(f"  TASK_COMPLETE @ {tasks}")
    print(f"  BREAK_GUARD={breaks} FORCED_PASS={forced} BLOCKED={blocked} FORBIDDEN={forbidden}")
    print(f"  DELIVER={delivers} VERIFY={verifies} REJECTED={dict(rejects)}")
    if guard_sets:
        print(f"  GUARD_SET: {guard_sets}")
    print("  Milestones:")
    for m in milestones:
        print(f"    {m}")


if __name__ == "__main__":
    paths = sys.argv[1:] or [
        str(Path(__file__).parent / "2614" / "replay (1).txt"),
        str(Path(__file__).parent / "2616" / "replay (2).txt"),
    ]
    for p in paths:
        if Path(p).exists():
            analyze(p)
