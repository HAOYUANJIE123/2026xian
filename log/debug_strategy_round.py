#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python-client"))
from lychee_basic_client.strategy import RouteStrategy

PID = 2941


def load_frames(path: str) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def replay_strategy(path: str, rounds: list[int]) -> None:
    frames = load_frames(path)
    s = RouteStrategy()
    s.load_start(
        {
            "edges": frames[0].get("edges", []),
            "map": frames[0].get("map")
            or {"gameplay": {"roles": {"gateNodeId": "S14", "terminalNodeIds": ["S15"]}}},
        }
    )

    for fr in frames:
        r = fr.get("round")
        if r is None:
            continue
        s.decide(fr, PID)
        if r in rounds:
            me = next(p for p in fr["players"] if p["playerId"] == PID)
            acts = s.decide(fr, PID)
            print(f"R{r} node={me.get('currentNodeId')} state={me.get('state')} good={me.get('goodFruit')} -> {acts}")


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "2614/replay (10).txt"
    rounds = [int(x) for x in sys.argv[2:]] if len(sys.argv) > 2 else [247, 298, 347]
    replay_strategy(path, rounds)
