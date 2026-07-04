#!/usr/bin/env python3
"""Compare win vs loss replays."""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python-client"))

PID = 2941


def load_frames(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def analyze(path: Path, label: str) -> None:
    frames = load_frames(path)
    meta = frames[0]
    last = frames[-1]
    me = next(p for p in last["players"] if p["playerId"] == PID)
    opp = next(p for p in last["players"] if p["playerId"] != PID)
    sd = me.get("scoreDetail") or {}

    rejects = Counter()
    tasks = []
    guard_events = []
    delivers = []
    verifies = []
    s09_edge = 0
    s09_idle_wait = 0
    milestones = []

    for fr in frames[1:]:
        r = fr.get("round", 0)
        pl = next((p for p in fr["players"] if p.get("playerId") == PID), None)
        if pl is None:
            continue
        for m in fr.get("messages") or []:
            t = m.get("type")
            p = m.get("payload") or {}
            if t == "ACTION_REJECTED" and p.get("playerId") == PID:
                rejects[p.get("errorCode", "?")] += 1
            if t == "TASK_COMPLETE" and p.get("playerId") == PID:
                tasks.append((r, p.get("taskId"), p.get("taskScore")))
            if t in ("GUARD_SET", "GUARD_BREAK", "BREAK_GUARD", "FORCED_PASS"):
                if p.get("playerId") == PID or t == "GUARD_SET":
                    guard_events.append((r, t, p.get("nodeId") or p.get("targetNodeId"), p.get("defense")))
            if t == "DELIVER_SUCCESS" and p.get("playerId") == PID:
                delivers.append(r)
            if t == "VERIFY_GATE_COMPLETE" and p.get("playerId") == PID:
                verifies.append(r)

        if pl.get("currentNodeId") == "S09" and pl.get("nextNodeId") == "S10":
            s09_edge += 1
        if pl.get("currentNodeId") == "S09" and pl.get("state") == "IDLE":
            for m in fr.get("messages") or []:
                if m.get("type") == "WAIT" and (m.get("payload") or {}).get("playerId") == PID:
                    s09_idle_wait += 1
                    break

        if r in (240, 244, 280, 287, 300, 330, 344, 390, 403, 448, 451, 465, 475, 490, 520, 560, 580):
            milestones.append(
                (r, pl.get("currentNodeId"), pl.get("state"), pl.get("nextNodeId"), round(pl.get("freshness", 0), 1))
            )

    print(f"\n{'='*60}")
    print(f"{label}: {path.name}")
    print(f"match: {meta.get('matchId')}")
    print(f"opp: {opp.get('playerId')}  score={opp.get('totalScore')} delivered={opp.get('delivered')}")
    print(f"me:  score={me.get('totalScore')} delivered={me.get('delivered')} fresh={me.get('freshness')}")
    print(f"detail: delivery={sd.get('delivery')} tasks={sd.get('tasks')} good={sd.get('goodFruit')} fresh={sd.get('freshness')} time={sd.get('time')} bounty={sd.get('bounty')}")
    print(f"tasks ({len(tasks)}): {tasks}")
    print(f"deliver R{delivers} verify R{verifies}")
    print(f"rejects: {dict(rejects)}")
    print(f"S09->S10 edge rounds: {s09_edge}")
    print(f"guard sample: {guard_events[:8]}")
    print("milestones:")
    for m in milestones:
        print(f"  R{m[0]} @{m[1]} {m[2]} next={m[3]} fresh={m[4]}")


if __name__ == "__main__":
    root = Path(__file__).parent
    analyze(root / "2616" / "replay (16).txt", "WIN vs 2616")
    analyze(root / "2614" / "replay (15).txt", "LOSS vs 2614")
