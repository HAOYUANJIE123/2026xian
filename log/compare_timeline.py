#!/usr/bin/env python3
import json
import sys
from pathlib import Path

PID = 2941


def load(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def player(fr, pid):
    return next(p for p in fr["players"] if p["playerId"] == pid)


def main():
    paths = sys.argv[1:]
    for path in paths:
        fs = load(path)
        opp = next(p["playerId"] for p in fs[0]["players"] if p["playerId"] != PID)
        print(f"\n=== {Path(path).name} vs {opp} ===")
        for fr in fs[1:]:
            r = fr.get("round", 0)
            if r > 360 or (r % 20 != 0 and r not in (92, 173, 177, 203, 240, 244, 280, 300, 324, 330)):
                continue
            me = player(fr, PID)
            op = player(fr, opp)
            nid = me.get("currentNodeId") or "?"
            onid = op.get("currentNodeId") or "?"
            print(
                f"R{r:3d} me {nid:4s} {me.get('state'):10s} "
                f"route={me.get('mainRoute')} task={me.get('routeTaskScore',0)!s:>3s} "
                f"fresh={me.get('freshness',0):5.1f} | "
                f"opp {onid:4s} {op.get('state'):10s} task={op.get('routeTaskScore',0)!s:>3s}"
            )


if __name__ == "__main__":
    main()
