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

    print(f"=== {path.parent.name}/{path.name} ===")
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

    print("  My TASK_COMPLETE:")
    for rnd, p in events.get("TASK_COMPLETE", []):
        if p.get("playerId") == ME:
            print(
                f"    r{rnd} {p.get('taskTemplateId')} node={p.get('nodeId')} "
                f"base={p.get('baseScore')}"
            )

    print("  Opp TASK_COMPLETE:")
    for rnd, p in events.get("TASK_COMPLETE", []):
        if p.get("playerId") == opp:
            print(
                f"    r{rnd} {p.get('taskTemplateId')} node={p.get('nodeId')} "
                f"base={p.get('baseScore')}"
            )

    guards = events.get("GUARD_SET", [])
    if guards:
        print("  GUARD_SET:")
        for rnd, p in guards:
            print(f"    r{rnd} node={p.get('nodeId')} def={p.get('defense')}")

    rejects = [x for x in events.get("ACTION_REJECTED", []) if x[1].get("playerId") == ME]
    if rejects:
        print(f"  My ACTION_REJECTED ({len(rejects)}):")
        codes: dict[str, int] = defaultdict(int)
        for rnd, p in rejects:
            codes[p.get("errorCode", "?")] += 1
        for code, count in sorted(codes.items(), key=lambda x: -x[1]):
            print(f"    {code}: {count}")

    print("  My node milestones:")
    prev = None
    milestones = []
    for line in lines[1:]:
        frame = json.loads(line)
        rnd = frame.get("round")
        pl = next((x for x in frame.get("players") or [] if x.get("playerId") == ME), None)
        if pl is None:
            continue
        key = (
            pl.get("currentNodeId"),
            pl.get("state"),
            pl.get("delivered"),
            pl.get("verified"),
        )
        if key != prev:
            milestones.append(
                (
                    rnd,
                    pl.get("currentNodeId"),
                    pl.get("state"),
                    round(pl.get("freshness", 0), 1),
                    pl.get("verified"),
                    pl.get("delivered"),
                )
            )
            prev = key
    for m in milestones[:20]:
        print("   ", m)
    print("   ... last 6:", milestones[-6:])
    print()


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    analyze(root / "2614" / "replay.txt")
    analyze(root / "2616" / "replay (1).txt")
