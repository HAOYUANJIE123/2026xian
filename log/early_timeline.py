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
    path = Path(sys.argv[1])
    fs = load(path)
    opp = next(p["playerId"] for p in fs[0]["players"] if p["playerId"] != PID)
    print(f"=== early {path.name} vs {opp} ===")
    for fr in fs[1:]:
        r = fr.get("round", 0)
        if r > 120 and r not in (173, 203, 240):
            continue
        me = player(fr, PID)
        op = player(fr, opp)
        nid = me.get("currentNodeId") or "?"
        onid = op.get("currentNodeId") or "?"
        print(
            f"R{r:3d} me {nid:4s} {me.get('state'):10s} route={me.get('mainRoute')} "
            f"task={me.get('routeTaskScore')!s} | opp {onid:4s} {op.get('state'):10s} "
            f"proc={op.get('processType')}"
        )


if __name__ == "__main__":
    main()
