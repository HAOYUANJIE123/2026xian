#!/usr/bin/env python3
import json
import sys
from pathlib import Path

PID = 2941


def main():
    path = Path(sys.argv[1])
    opp_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
    fs = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if opp_id is None:
        opp_id = next(p["playerId"] for p in fs[0]["players"] if p["playerId"] != PID)
    for r in range(50, 180):
        fr = fs[r]
        me = next(p for p in fr["players"] if p["playerId"] == PID)
        op = next(p for p in fr["players"] if p["playerId"] == opp_id)
        if r % 15 != 0 and r not in (55, 54, 166, 165, 173):
            continue
        print(
            f"R{r:3d} me {me.get('currentNodeId')} {me.get('state'):10s} "
            f"next={me.get('nextNodeId')} | opp {op.get('currentNodeId')} {op.get('state'):10s} "
            f"next={op.get('nextNodeId')}"
        )


if __name__ == "__main__":
    main()
