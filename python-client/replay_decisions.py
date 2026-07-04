#!/usr/bin/env python3
"""Replay strategy decisions at key rounds."""
import json
import sys
from pathlib import Path

from lychee_basic_client.strategy import RouteStrategy

PID = 2941


def load(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    path = Path(sys.argv[1])
    rounds = {int(x) for x in sys.argv[2:]}
    fs = load(path)
    s = RouteStrategy()
    s.load_start({"edges": fs[0].get("edges", []), "map": fs[0].get("map") or {}})
    for fr in fs[1:]:
        r = fr.get("round", 0)
        if r not in rounds:
            continue
        me = next(p for p in fr["players"] if p["playerId"] == PID)
        acts = s.decide(fr, PID)
        main = next((a for a in acts if a.get("action") != "WINDOW_CARD"), None)
        print(
            f"R{r} @{me.get('currentNodeId')} {me.get('state')} next={me.get('nextNodeId')} "
            f"proc_attempted={s.process_attempted} failed_moves={s._failed_moves} -> {main}"
        )


if __name__ == "__main__":
    main()
