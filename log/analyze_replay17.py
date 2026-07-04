#!/usr/bin/env python3
import json
import sys
from collections import Counter
from pathlib import Path

PID = 2941


def load(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def analyze(path: Path):
    fs = load(path)
    opp = next(p["playerId"] for p in fs[0]["players"] if p["playerId"] != PID)
    me_last = next(p for p in fs[-1]["players"] if p["playerId"] == PID)
    opp_last = next(p for p in fs[-1]["players"] if p["playerId"] == opp)
    sd = me_last.get("scoreDetail") or {}

    tasks, delivers, verifies, squad, guards, rejects = [], [], [], [], [], Counter()
    s02_wait = 0

    for fr in fs[1:]:
        r = fr.get("round", 0)
        me = next(p for p in fr["players"] if p["playerId"] == PID)
        if me.get("currentNodeId") == "S02" and me.get("state") == "WAITING" and not me.get("nextNodeId"):
            s02_wait += 1
        for m in fr.get("messages") or []:
            t, p = m.get("type"), m.get("payload") or {}
            if p.get("playerId") == PID and t == "ACTION_REJECTED":
                rejects[p.get("errorCode", "?")] += 1
            if p.get("playerId") == PID and t == "TASK_COMPLETE":
                tasks.append((r, p.get("taskId"), p.get("taskScore"), p.get("routeBucket")))
            if p.get("playerId") == PID and t == "DELIVER_SUCCESS":
                delivers.append(r)
            if p.get("playerId") == PID and t == "VERIFY_GATE_COMPLETE":
                verifies.append(r)
            if p.get("playerId") == PID and t == "SQUAD_DISPATCH":
                squad.append((r, p.get("action"), p.get("targetNodeId")))
            if t in ("GUARD_SET", "GUARD_BREAK") and (
                p.get("playerId") == PID or (t == "GUARD_SET" and p.get("ownerTeamId"))
            ):
                guards.append((r, t, p.get("nodeId"), p.get("defense")))

    print(f"\n=== {path.name} vs {opp} ===")
    print(f"match: {fs[0].get('matchId')}")
    print(f"WIN  {PID}: {me_last.get('totalScore')} delivered={me_last.get('delivered')}")
    print(f"LOSE {opp}: {opp_last.get('totalScore')} delivered={opp_last.get('delivered')}")
    print(
        f"detail: delivery={sd.get('delivery')} tasks={sd.get('tasks')} good={sd.get('goodFruit')} "
        f"fresh={sd.get('freshness')} time={sd.get('time')} bounty={sd.get('bounty')}"
    )
    print(f"tasks ({len(tasks)}): {tasks}")
    print(f"deliver R{delivers} verify R{verifies}")
    print(f"S02 WAITING stall rounds: {s02_wait}")
    print(f"squad open: {squad[:6]}")
    print(f"guard events (first 10): {guards[:10]}")
    print(f"rejects: {dict(rejects)}")

    milestones = [240, 244, 280, 300, 320, 360, 480, 550]
    print("milestones:")
    for fr in fs[1:]:
        r = fr.get("round", 0)
        if r not in milestones:
            continue
        me = next(p for p in fr["players"] if p["playerId"] == PID)
        op = next(p for p in fr["players"] if p["playerId"] == opp)
        print(
            f"  R{r} me {me.get('currentNodeId')} {me.get('state')} task={me.get('routeTaskScore')} "
            f"| opp {op.get('currentNodeId')} {op.get('state')} task={op.get('routeTaskScore')}"
        )


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        analyze(Path(arg))
