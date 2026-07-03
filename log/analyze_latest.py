import json
from collections import defaultdict
from pathlib import Path

ME = 2941


def analyze(path: Path) -> None:
    lines = path.read_text(encoding="utf-8").splitlines()
    events: dict[str, list] = defaultdict(list)
    for line in lines[1:]:
        frame = json.loads(line)
        rnd = frame.get("round")
        for msg in frame.get("messages") or []:
            events[msg["type"]].append((rnd, msg.get("payload") or {}))

    last = json.loads(lines[-1])
    players = last.get("players") or []
    opp = next(p.get("playerId") for p in players if p.get("playerId") != ME)

    print(f"\n{'=' * 60}")
    print(f"{path}")
    print("=" * 60)
    for pl in players:
        sd = pl.get("scoreDetail") or {}
        print(
            f"  {pl.get('playerId')} {pl.get('playerName', '')}: "
            f"total={pl.get('totalScore')} delivered={pl.get('delivered')} "
            f"R{pl.get('deliverRound')} fresh={pl.get('freshness')} "
            f"good={pl.get('goodFruit')} bad={pl.get('badFruit')}"
        )
        print(
            f"    delivery={sd.get('delivery')} good={sd.get('goodFruit')} "
            f"fresh={sd.get('freshness')} time={sd.get('time')} tasks={sd.get('tasks')}"
        )
        print(
            f"    route main={pl.get('mainRoute')} road={pl.get('roadRounds')} "
            f"water={pl.get('waterRounds')}"
        )

    print("  My TASK_COMPLETE rounds:", [r for r, p in events.get("TASK_COMPLETE", []) if p.get("playerId") == ME])
    print("  Opp TASK_COMPLETE rounds:", [r for r, p in events.get("TASK_COMPLETE", []) if p.get("playerId") == opp])

    guards = events.get("GUARD_SET", [])
    if guards:
        print("  GUARD_SET:")
        for rnd, p in guards:
            print(f"    r{rnd} node={p.get('nodeId')} def={p.get('defense')} team={p.get('ownerTeamId')}")

    for action in ("BREAK_GUARD", "FORCED_PASS", "VERIFY_GATE_COMPLETE", "DELIVER_SUCCESS"):
        hits = [(r, p) for r, p in events.get(action, []) if p.get("playerId") == ME]
        if hits:
            print(f"  My {action}: {len(hits)} -> first/last r{hits[0][0]}/r{hits[-1][0]}")

    rejects: dict[str, int] = defaultdict(int)
    for rnd, p in events.get("ACTION_REJECTED", []):
        if p.get("playerId") == ME:
            rejects[p.get("errorCode", "?")] += 1
    if rejects:
        print("  My ACTION_REJECTED:", dict(rejects))

    timeouts = sum(
        1
        for r, p in events.get("DISCONNECT_WARNING", [])
        if p.get("playerId") == ME
    )
    if timeouts:
        print(f"  My DISCONNECT_WARNING: {timeouts}")

    # action summary from client if no replay actions - count key events
    moves = sum(1 for r, p in events.get("MOVE_PROGRESS", []) if p.get("playerId") == ME)
    waits = sum(1 for r, p in events.get("WAIT", []) if p.get("playerId") == ME)
    print(f"  My MOVE_PROGRESS={moves} WAIT events={waits}")

    prev = None
    milestones = []
    for line in lines[1:]:
        frame = json.loads(line)
        rnd = frame.get("round")
        pl = next((x for x in frame.get("players") or [] if x.get("playerId") == ME), None)
        if pl is None:
            continue
        key = (pl.get("currentNodeId"), pl.get("state"), pl.get("delivered"), pl.get("verified"))
        if key != prev:
            milestones.append((rnd, pl.get("currentNodeId"), pl.get("state"), round(pl.get("freshness", 0), 1), pl.get("verified")))
            prev = key
    print("  Milestones (first 15):", milestones[:15])
    print("  Milestones (last 8):", milestones[-8:])


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    analyze(root / "2614" / "replay (3).txt")
    analyze(root / "2616" / "replay (2).txt")
