import json
from collections import Counter
from pathlib import Path

PID = 2941
SKIP = {"MOVE_PROGRESS", "FRESHNESS_DROP", "PLAYER_STATE"}


def analyze(path: str) -> None:
    lines = Path(path).read_text(encoding="utf-8").strip().splitlines()
    events = []
    for line in lines[1:]:
        d = json.loads(line)
        for m in d.get("messages", []):
            p = m.get("payload") or {}
            t = m.get("type")
            if p.get("playerId") == PID or t in (
                "GUARD_SET",
                "GUARD_CLEAR",
                "BREAK_GUARD",
                "FORCED_PASS",
                "DELIVER",
                "VERIFY_GATE",
                "MOVE_BLOCKED_BY_GUARD",
                "CONTEST_START",
                "CONTEST_END",
                "ACTION_REJECTED",
            ):
                events.append((m.get("round"), t, p))

    print("===", path, "===")
    print("Event types:", dict(Counter(t for _, t, _ in events)))

    interesting = [e for e in events if e[1] not in SKIP]
    print("Last 30 interesting:")
    for r, t, p in interesting[-30:]:
        keys = (
            "nodeId",
            "targetNodeId",
            "fromNodeId",
            "toNodeId",
            "action",
            "reason",
            "defense",
            "ownerTeamId",
            "playerId",
            "goodFruit",
            "badFruit",
        )
        brief = {k: p[k] for k in keys if k in p}
        print(f"  r{r} {t} {brief}")

    rounds = [185, 187, 191, 298, 330, 365, 490, 517, 568, 574, 600]
    for target_r in rounds:
        for line in lines[1:]:
            d = json.loads(line)
            if d.get("round") != target_r:
                continue
            for pl in d.get("players", []):
                if pl.get("playerId") == PID:
                    print(
                        f"  r{target_r} me: state={pl.get('state')} "
                        f"node={pl.get('currentNodeId')} edge={pl.get('routeEdgeId')} "
                        f"next={pl.get('nextNodeId')} good={pl.get('goodFruit')} "
                        f"bad={pl.get('badFruit')} team={pl.get('teamId')}"
                    )
            for n in d.get("nodes", []):
                g = n.get("guard") or {}
                if g.get("active") and n.get("nodeId") in ("S07", "S09", "S10", "S11"):
                    print(
                        f"  r{target_r} guard {n['nodeId']}: "
                        f"def={g.get('defense')} owner={g.get('ownerTeamId')} "
                        f"keys={list(g.keys())}"
                    )
            break
    print()


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    analyze(str(root / "2614" / "replay (3).txt"))
    analyze(str(root / "2616" / "replay (2).txt"))
