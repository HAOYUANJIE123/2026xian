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


def main() -> None:
    path = sys.argv[1]
    prev = None
    for fr in frames(path):
        r = fr.get("round")
        if r is None or r > 300:
            continue
        me = next((p for p in fr.get("players", []) if p.get("playerId") == PID), {})
        node = me.get("currentNodeId")
        st = me.get("state")
        nxt = me.get("nextNodeId")
        key = (node, st, nxt)
        if key != prev:
            print(f"r{r} {node} {st} next={nxt} horse={me.get('resources',{}).get('FAST_HORSE')} buffs={me.get('buffs')}")
            prev = key


if __name__ == "__main__":
    main()
