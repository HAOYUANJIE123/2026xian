import json
from collections import Counter, defaultdict
from pathlib import Path

OPP = 2616
US = 2941
REPLAY_DIR = Path(__file__).resolve().parent


def load_replay(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    return lines, json.loads(lines[-1])


def events_for_player(lines, player_id: int):
    events: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    for line in lines[1:]:
        frame = json.loads(line)
        rnd = frame.get("round")
        for msg in frame.get("messages") or []:
            payload = msg.get("payload") or {}
            if payload.get("playerId") != player_id:
                continue
            events[msg["type"]].append((rnd, payload))
    return events


def guard_sets(lines, player_id: int):
    out = []
    for line in lines[1:]:
        frame = json.loads(line)
        rnd = frame.get("round")
        for msg in frame.get("messages") or []:
            if msg.get("type") != "GUARD_SET":
                continue
            payload = msg.get("payload") or {}
            if payload.get("playerId") != player_id:
                continue
            out.append((rnd, payload.get("nodeId"), payload.get("defense")))
    return out


def squad_summary(events):
    counts: Counter[str] = Counter()
    targets: Counter[str] = Counter()
    for event_type, items in events.items():
        if "SQUAD" not in event_type:
            continue
        for _, payload in items:
            action = payload.get("action") or event_type.replace("SQUAD_", "")
            target = payload.get("targetNodeId") or "?"
            counts[action] += 1
            if action in ("SCOUT", "CLEAR", "WEAKEN", "REINFORCE"):
                targets[f"{action}@{target}"] += 1
    return counts, targets


def main_route(lines, player_id: int):
    for line in lines[1:50]:
        frame = json.loads(line)
        for player in frame.get("players") or []:
            if player.get("playerId") == player_id and player.get("mainRoute"):
                return player.get("mainRoute")
    return None


def node_milestones(lines, player_id: int, limit: int = 12):
    milestones = []
    prev = None
    for line in lines[1:]:
        frame = json.loads(line)
        rnd = frame.get("round")
        for player in frame.get("players") or []:
            if player.get("playerId") != player_id:
                continue
            node = player.get("currentNodeId")
            if node != prev:
                milestones.append((rnd, node, player.get("state")))
                prev = node
    return milestones[-limit:]


def summarize_replay(path: Path):
    lines, last = load_replay(path)
    opp = next(p for p in last.get("players") or [] if p.get("playerId") == OPP)
    us = next((p for p in last.get("players") or [] if p.get("playerId") == US), {})
    events = events_for_player(lines, OPP)
    guards = guard_sets(lines, OPP)
    squad_counts, squad_targets = squad_summary(events)
    tasks = events.get("TASK_COMPLETE", [])
    window_types = Counter(
        msg_type
        for msg_type in events
        if "WINDOW" in msg_type
        for _ in events[msg_type]
    )
    return {
        "file": path.name,
        "score": opp.get("totalScore"),
        "delivered": opp.get("delivered"),
        "deliver_round": opp.get("deliverRound"),
        "freshness": opp.get("freshness"),
        "us_score": us.get("totalScore"),
        "route": main_route(lines, OPP),
        "guards": Counter(node for _, node, _ in guards),
        "guard_timeline": guards,
        "squad": squad_counts,
        "squad_targets": squad_targets.most_common(8),
        "tasks": len(tasks),
        "task_total": sum(p.get("score", 0) for _, p in tasks),
        "window": dict(window_types),
        "milestones": node_milestones(lines, OPP),
    }


def print_key_moments(path: Path, lo: int, hi: int):
    lines, _ = load_replay(path)
    print(f"--- {path.name} R{lo}-R{hi} ---")
    interesting = {
        "GUARD_SET",
        "GUARD_BREAK",
        "SQUAD_DISPATCH",
        "SQUAD_WEAKEN",
        "SQUAD_CLEAR",
        "SQUAD_SCOUT",
        "PROCESS_PROGRESS",
        "TASK_COMPLETE",
        "ACTION_REJECTED",
        "WAIT",
        "DELIVER",
    }
    keys = (
        "action",
        "targetNodeId",
        "nodeId",
        "defense",
        "processType",
        "errorCode",
        "attackValue",
        "result",
        "taskId",
        "score",
    )
    for line in lines[1:]:
        frame = json.loads(line)
        rnd = frame.get("round")
        if rnd < lo or rnd > hi:
            continue
        for msg in frame.get("messages") or []:
            msg_type = msg.get("type")
            if msg_type not in interesting:
                continue
            payload = msg.get("payload") or {}
            pid = payload.get("playerId")
            if pid not in (OPP, US):
                continue
            if msg_type == "PROCESS_PROGRESS" and payload.get("processType") not in (
                "SET_GUARD",
                "CLAIM_TASK",
            ):
                continue
            brief = {k: payload[k] for k in keys if k in payload}
            print(f"  R{rnd} P{pid} {msg_type} {brief}")


if __name__ == "__main__":
    print("=== 2616 STRATEGY SUMMARY ===\n")
    for replay in sorted(REPLAY_DIR.glob("replay*.txt")):
        info = summarize_replay(replay)
        print(
            f"{info['file']}: 2616={info['score']} deliver=R{info['deliver_round']} "
            f"vs 2941={info['us_score']} route={info['route']}"
        )
        print(f"  guards={dict(info['guards'])} squad={dict(info['squad'])} tasks={info['tasks']}({info['task_total']}pts)")
        if info["guard_timeline"]:
            sample = info["guard_timeline"][:5]
            extra = f" ... +{len(info['guard_timeline']) - 5}" if len(info["guard_timeline"]) > 5 else ""
            print(f"  guard rounds: {sample}{extra}")
        print(f"  squad targets: {info['squad_targets']}")
        print(f"  late path: {info['milestones']}")
        print()

    for name in ("replay (16).txt", "replay (18).txt"):
        path = REPLAY_DIR / name
        if path.exists():
            print_key_moments(path, 280, 310)
            print()
