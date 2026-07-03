#!/usr/bin/env python3
import json
import sys
from pathlib import Path

PID = 2941


def frames(path: str) -> list[dict]:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def guard_at(fr: dict, node_id: str) -> dict:
    for n in fr.get("nodes", []):
        if n.get("nodeId") == node_id:
            return n.get("guard") or {}
    return {}


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).parent / "2616" / "replay (3).txt")
    for fr in frames(path):
        r = fr.get("round")
        if r is None or r < 270 or r > 520:
            continue
        me = next((p for p in fr.get("players", []) if p.get("playerId") == PID), {})
        g10 = guard_at(fr, "S10")
        g11 = guard_at(fr, "S11")
        evs = []
        for m in fr.get("messages", []):
            t = m.get("type")
            p = m.get("payload") or {}
            if t in ("GUARD_SET", "BREAK_GUARD", "FORCED_PASS", "GUARD_BREAK", "GUARD_CLEAR"):
                evs.append((t, p))
            if t == "ACTION_REJECTED" and p.get("playerId") == PID:
                evs.append((t, p.get("errorCode")))
        if r in (270, 280, 290, 295, 296, 297, 298, 299, 300, 310, 330, 365, 400, 490, 517):
            print(
                f"r{r:3d} {me.get('currentNodeId')} {me.get('state'):10s} "
                f"next={me.get('nextNodeId')} good={me.get('goodFruit')} "
                f"S10={g10.get('defense') if g10.get('active') else 0} "
                f"S11={g11.get('defense') if g11.get('active') else 0}"
            )
            for ev in evs[:5]:
                print(f"      {ev}")


if __name__ == "__main__":
    main()
