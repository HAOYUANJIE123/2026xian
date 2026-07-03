#!/usr/bin/env python3
"""Audit strategy decisions against a replay frame sequence."""
import json
import sys
from collections import Counter
from pathlib import Path

PID = 2941


def load_frames(path: str) -> list[dict]:
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


def audit_replay(path: str) -> None:
    from lychee_basic_client.strategy import RouteStrategy

    frames = load_frames(path)
    if not frames:
        print(f"no frames: {path}")
        return

    s = RouteStrategy()
    s.load_start({"edges": frames[0].get("edges", []), "map": frames[0].get("map") or {
        "gameplay": {"roles": {"gateNodeId": "S14", "terminalNodeIds": ["S15"]}}
    }})

    actions_counter: Counter = Counter()
    empty_rounds: list[int] = []
    last_node = None
    milestones: list[tuple] = []

    for fr in frames:
        r = fr.get("round")
        if r is None:
            continue
        me = next((p for p in fr.get("players", []) if p.get("playerId") == PID), None)
        if not me:
            continue
        node = me.get("currentNodeId")
        state = me.get("state")
        actions = s.decide(fr, PID)
        if not actions:
            empty_rounds.append(r)
        for a in actions:
            actions_counter[a.get("action", "?")] += 1
        if node != last_node or (r in (42, 43, 44, 50, 61, 100, 186, 191, 259, 298, 300, 517, 600)):
            milestones.append((r, node, state, actions))
        last_node = node

    me = next((p for p in frames[-1].get("players", []) if p.get("playerId") == PID), {})
    print(f"\n=== {Path(path).name} ===")
    print(f"  final: node={me.get('currentNodeId')} state={me.get('state')} score={me.get('totalScore')} delivered={me.get('delivered')}")
    print(f"  actions: {dict(actions_counter)}")
    print(f"  empty action rounds: {len(empty_rounds)}")
    print(f"  failed_moves: {s._failed_moves}")
    print(f"  process_attempted: {sorted(s.process_attempted)}")
    print("  milestones:")
    for m in milestones[:25]:
        print(f"    r{m[0]} {m[1]} {m[2]} -> {m[3]}")


def main() -> None:
    log = Path(__file__).parent
    paths = sys.argv[1:] or [
        str(log / "2616" / "replay (3).txt"),
        str(log / "2616" / "replay (7).txt"),
        str(log / "2614" / "replay (8).txt"),
    ]
    for p in paths:
        if Path(p).exists():
            audit_replay(p)


if __name__ == "__main__":
    main()
