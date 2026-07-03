#!/usr/bin/env python3
import json
from pathlib import Path

PID = 1001
path = Path(r"d:/pythonProj/gaming/2026xian/比赛资料/比赛资料/调测包及赛题相关文档_V1/调测/server/replay.txt")

tasks = []
wait_rounds = 0
hold_rounds = 0
last_node = None
last_state = None

for line in path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line:
        continue
    try:
        fr = json.loads(line)
    except json.JSONDecodeError:
        continue
    r = fr.get("round")
    me = next((p for p in fr.get("players", []) if p.get("playerId") == PID), None)
    if not me:
        continue
    node = me.get("currentNodeId")
    state = me.get("state")
    if state == "WAITING" and node in ("S09", "S10", "S11", "S12"):
        hold_rounds += 1
    for m in fr.get("messages", []):
        if m.get("type") != "TASK_COMPLETE":
            continue
        p = m.get("payload") or {}
        if p.get("playerId") != PID:
            continue
        tasks.append(
            {
                "round": r,
                "taskId": p.get("taskId"),
                "score": p.get("score"),
                "taskScore": p.get("taskScore"),
                "nodeId": p.get("nodeId"),
                "routeBucket": p.get("routeBucket"),
            }
        )
    last_node = node
    last_state = state

me = next((p for p in json.loads(path.read_text(encoding="utf-8").splitlines()[-2]).get("players", []) if p.get("playerId") == PID), {})

print("=== TASK_COMPLETE ===")
task_sum = 0
for t in tasks:
    print(t)
    task_sum += int(t.get("score") or 0)
print("sum(score):", task_sum)

print("\n=== FINAL SCORE ===")
print("totalScore:", me.get("totalScore"))
print("scoreDetail:", me.get("scoreDetail"))
print("delivered:", me.get("delivered"))
print("node:", me.get("currentNodeId"), "state:", me.get("state"))

print("\n=== TIME SINKS (approx) ===")
print("guard-hold-like WAITING @ S09-S12:", hold_rounds, "rounds")

# milestones
frames = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
prev = None
print("\n=== ROUTE MILESTONES ===")
for fr in frames:
    r = fr.get("round")
    me = next(p for p in fr["players"] if p["playerId"] == PID)
    key = (me["currentNodeId"], me["state"], me.get("nextNodeId"))
    if key != prev:
        if r in (42, 47, 96, 173, 177, 220, 259, 298, 350, 450, 517, 568, 600):
            print(f"r{r:3d} {key} total={me.get('totalScore')}")
        prev = key
