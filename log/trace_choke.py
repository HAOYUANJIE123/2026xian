#!/usr/bin/env python3
import json
import sys
from pathlib import Path

PID = 2941


def trace(path: str) -> None:
    frames = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    print("===", path, "===")
    rounds = [1, 92, 173, 177, 280, 288, 290, 298, 350, 400, 450, 490, 517, 568, 600]
    for r in rounds:
        fr = next((f for f in frames if f.get("round") == r), None)
        if not fr:
            continue
        me = next(p for p in fr["players"] if p["playerId"] == PID)
        s10 = next((n for n in fr.get("nodes", []) if n.get("nodeId") == "S10"), {})
        g = s10.get("guard") or {}
        print(
            f"R{r:3d} {me.get('currentNodeId')} {me.get('state'):10s} "
            f"next={me.get('nextNodeId')} good={me.get('goodFruit')} "
            f"fresh={me.get('freshness', 0):.1f} "
            f"S10={g.get('active')} def={g.get('defense')} own={g.get('ownerTeamId')}"
        )
    breaks = [
        (fr.get("round"), m.get("payload"))
        for fr in frames
        for m in fr.get("messages") or []
        if m.get("type") == "BREAK_GUARD" and (m.get("payload") or {}).get("playerId") == PID
    ]
    guard_sets = [
        (fr.get("round"), (m.get("payload") or {}).get("nodeId"), (m.get("payload") or {}).get("defense"))
        for fr in frames
        for m in fr.get("messages") or []
        if m.get("type") == "GUARD_SET" and (m.get("payload") or {}).get("playerId") != PID
    ]
    print("enemy GUARD_SET:", guard_sets[:10])
    print("our BREAK_GUARD:", breaks)


if __name__ == "__main__":
    for p in sys.argv[1:] or ["2616/replay (11).txt", "2614/replay (12).txt"]:
        trace(p)
        print()
