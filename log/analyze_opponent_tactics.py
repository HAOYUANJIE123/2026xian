#!/usr/bin/env python3
"""Extract tactical patterns from opponent replays (2614/2616)."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

MY_IDS = {2941, 1001}


def load_frames(path: Path) -> list[dict]:
    frames = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            frames.append(json.loads(line))
    return frames


def opponent_id(frames: list[dict]) -> int:
    last = frames[-1]
    for player in last.get("players") or []:
        pid = player.get("playerId")
        if pid not in MY_IDS:
            return int(pid)
    raise ValueError("opponent not found")


def analyze(path: Path) -> dict:
    frames = load_frames(path)
    opp = opponent_id(frames)
    last_player = next(p for p in frames[-1]["players"] if p["playerId"] == opp)

    accepted = Counter()
    guard_sets: list[tuple] = []
    break_guards: list[tuple] = []
    forced_pass: list[tuple] = []
    tasks: list[tuple] = []
    squads: list[tuple] = []
    resource_claim: Counter[str] = Counter()
    resource_use: Counter[str] = Counter()
    window_plays: list[tuple] = []
    contests_started: list[tuple] = []
    bounties: list[tuple] = []
    set_guard_process: list[tuple] = []

    for frame in frames[1:]:
        rnd = frame.get("round", 0)
        for msg in frame.get("messages") or []:
            t = msg.get("type", "")
            p = msg.get("payload") or {}

            if t == "GUARD_SET":
                guard_sets.append(
                    (rnd, p.get("nodeId"), p.get("defense"), p.get("ownerTeamId"))
                )
            elif t == "TASK_COMPLETE" and p.get("playerId") == opp:
                tasks.append(
                    (
                        rnd,
                        p.get("taskTemplateId"),
                        p.get("nodeId"),
                        p.get("baseScore", p.get("score")),
                    )
                )
            elif t == "BREAK_GUARD" and p.get("playerId") == opp:
                break_guards.append(
                    (rnd, p.get("targetNodeId"), p.get("goodFruit"), p.get("badFruit"))
                )
            elif t == "FORCED_PASS" and p.get("playerId") == opp:
                forced_pass.append((rnd, p.get("targetNodeId")))
            elif t in ("SQUAD_DISPATCH", "SQUAD_ARRIVE", "SQUAD_CLEAR_START", "SQUAD_CLEAR_COMPLETE"):
                if p.get("playerId") == opp or p.get("ownerPlayerId") == opp:
                    squads.append((rnd, t, p.get("action"), p.get("targetNodeId"), p.get("orderId")))
            elif t == "RESOURCE_CLAIM" and p.get("playerId") == opp:
                resource_claim[p.get("resourceType", "?")] += 1
            elif t == "RESOURCE_USE" and p.get("playerId") == opp:
                resource_use[p.get("resourceType", "?")] += 1
            elif t == "WINDOW_CARD_PLAYED" and p.get("playerId") == opp:
                window_plays.append((rnd, p.get("card"), p.get("contestType"), p.get("won")))
            elif t == "CONTEST_START":
                contests_started.append((rnd, p.get("contestType"), p.get("objectId")))
            elif t in ("BOUNTY_CREATE", "BOUNTY_COMPLETE", "BOUNTY_CLAIM"):
                bounties.append((rnd, t, p))
            elif t == "PROCESS_COMPLETE" and p.get("playerId") == opp:
                if p.get("processType") == "SET_GUARD":
                    set_guard_process.append((rnd, p.get("targetNodeId")))

        for result in frame.get("actionResults") or []:
            if result.get("playerId") != opp:
                continue
            if result.get("accepted"):
                accepted[result.get("action", "?")] += 1

    milestones: list[tuple] = []
    prev = None
    for frame in frames[1:]:
        rnd = frame.get("round", 0)
        pl = next((x for x in frame.get("players") or [] if x.get("playerId") == opp), None)
        if pl is None:
            continue
        key = (pl.get("currentNodeId"), pl.get("state"), pl.get("nextNodeId"))
        if key != prev:
            milestones.append(
                (
                    rnd,
                    pl.get("currentNodeId"),
                    pl.get("state"),
                    round(float(pl.get("freshness") or 0), 1),
                    pl.get("nextNodeId"),
                )
            )
            prev = key

    sd = last_player.get("scoreDetail") or {}
    opp_guards = [g for g in guard_sets if g[3] and str(g[3]) != str(last_player.get("teamId"))]
    own_guards = [g for g in guard_sets if g[3] == last_player.get("teamId")]

    return {
        "path": str(path),
        "opp_id": opp,
        "name": last_player.get("playerName", ""),
        "total": last_player.get("totalScore"),
        "deliver_round": last_player.get("deliverRound"),
        "main_route": last_player.get("mainRoute"),
        "score_detail": sd,
        "tasks": tasks,
        "accepted": accepted,
        "own_guard_sets": own_guards,
        "opp_guard_sets": opp_guards,
        "set_guard_process": set_guard_process,
        "break_guards": break_guards,
        "forced_pass": forced_pass,
        "squads": squads,
        "resource_claim": resource_claim,
        "resource_use": resource_use,
        "window_plays": window_plays,
        "contests_started": contests_started,
        "bounties": bounties,
        "milestones": milestones,
    }


def print_report(data: dict) -> None:
    sd = data["score_detail"]
    print("=" * 72)
    print(data["path"])
    print(
        f"  Opp {data['opp_id']} ({data['name']}): total={data['total']} "
        f"deliverR={data['deliver_round']} route={data['main_route']}"
    )
    print(
        f"  delivery={sd.get('delivery')} tasks={sd.get('tasks')} "
        f"good={sd.get('goodFruit')} fresh={sd.get('freshness')} "
        f"time={sd.get('time')} bounty={sd.get('bounty')}"
    )
    print(f"  Tasks: {data['tasks']}")
    print(f"  Accepted actions: {dict(data['accepted'].most_common(12))}")
    print(f"  Own SET_GUARD (process): {data['set_guard_process']}")
    print(f"  Own GUARD_SET events: {data['own_guard_sets']}")
    print(f"  BREAK_GUARD: {data['break_guards']}")
    print(f"  FORCED_PASS: {data['forced_pass']}")
    print(f"  Squad events ({len(data['squads'])}):")
    for item in data["squads"][:15]:
        print(f"    {item}")
    if len(data["squads"]) > 15:
        print(f"    ... +{len(data['squads']) - 15} more")
    print(f"  Resource claim: {dict(data['resource_claim'])}")
    print(f"  Resource use: {dict(data['resource_use'])}")
    print(f"  Window plays: {data['window_plays'][:10]}")
    print(f"  Contests nearby: {data['contests_started'][:8]}")
    print(f"  Bounties: {data['bounties'][:8]}")
    ms = data["milestones"]
    print("  Key milestones:")
    shown = set()
    for m in ms:
        if m[0] in shown:
            continue
        if m[0] <= 60 or m[0] % 40 == 0 or m[0] >= (data["deliver_round"] or 600) - 30:
            print(
                f"    R{m[0]:3d} @ {(m[1] or '?'):4s} {(m[2] or '?'):12s} "
                f"fresh={m[3]} next={m[4]}"
            )
            shown.add(m[0])
    print()


def summarize_tactics(all_data: list[dict]) -> None:
    print("\n" + "=" * 72)
    print("TACTICAL SUMMARY (2614 + 2616)")
    print("=" * 72)

    guard_nodes: Counter[str] = Counter()
    guard_rounds: list[int] = []
    squad_actions: Counter[str] = Counter()
    task_templates: Counter[str] = Counter()
    routes: Counter[str] = Counter()
    break_targets: Counter[str] = Counter()

    for d in all_data:
        routes[d["main_route"] or "?"] += 1
        for rnd, node in d["set_guard_process"]:
            guard_nodes[node or "?"] += 1
            guard_rounds.append(rnd)
        for item in d["squads"]:
            squad_actions[item[2] or item[1]] += 1
        for _, tmpl, _, _ in d["tasks"]:
            task_templates[tmpl or "?"] += 1
        for _, target, _, _ in d["break_guards"]:
            break_targets[target or "?"] += 1

    print(f"Routes: {dict(routes)}")
    print(f"Guard placement (SET_GUARD process): {dict(guard_nodes.most_common())}")
    if guard_rounds:
        print(f"Guard timing: early={min(guard_rounds)} late={max(guard_rounds)} avg={sum(guard_rounds)/len(guard_rounds):.0f}")
    print(f"Squad action types: {dict(squad_actions.most_common())}")
    print(f"Task templates completed: {dict(task_templates.most_common())}")
    print(f"BREAK_GUARD targets: {dict(break_targets.most_common())}")


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    paths = [Path(p) for p in sys.argv[1:]] if len(sys.argv) > 1 else [
        root / "2614" / "replay.txt",
        root / "2614" / "replay (1).txt",
        root / "2616" / "replay (1).txt",
        root / "2616" / "replay (2).txt",
    ]
    results = []
    for path in paths:
        if not path.exists():
            continue
        data = analyze(path)
        print_report(data)
        results.append(data)
    if results:
        summarize_tactics(results)
