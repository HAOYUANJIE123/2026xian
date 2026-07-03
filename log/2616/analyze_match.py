import json
from collections import defaultdict
from pathlib import Path

replay = Path(r"d:\pythonProj\gaming\2026xian\log\replay (1).txt")
lines = replay.read_text(encoding="utf-8").splitlines()
events = defaultdict(list)
for line in lines[1:]:
    frame = json.loads(line)
    rnd = frame.get("round")
    for msg in frame.get("messages") or []:
        events[msg["type"]].append((rnd, msg.get("payload") or {}))

last = json.loads(lines[-1])
print("=== FINAL SCORES ===")
for pl in last.get("players") or []:
    print(
        pl.get("playerId"),
        pl.get("playerName"),
        "total=",
        pl.get("totalScore"),
        "delivered=",
        pl.get("delivered"),
        "deliverRound=",
        pl.get("deliverRound"),
        "retired=",
        pl.get("retired"),
        "freshness=",
        pl.get("freshness"),
        "good=",
        pl.get("goodFruit"),
        "detail=",
        pl.get("scoreDetail"),
    )

print("\n=== 2941 TASK COMPLETE ===")
for rnd, p in events["TASK_COMPLETE"]:
    if p.get("playerId") == 2941:
        print(f"  r{rnd}", p)

print("\n=== 2941 DELIVER / RETIRE / PENALTY ===")
for t in sorted(events):
    if any(x in t for x in ["DELIVER", "RETIRE", "PENALTY", "MISSING", "TIMEOUT", "ERROR"]):
        for rnd, p in events[t]:
            if p.get("playerId") in (2941, None) or t.endswith("PENALTY"):
                print(t, rnd, p)

print("\n=== 2941 SET_GUARD on our path ===")
for rnd, p in events.get("GUARD_SET", events.get("SET_GUARD", [])):
    print(rnd, p)

print("\n=== CONTEST events involving stalls ===")
for t in sorted(events):
    if "CONTEST" in t or "WINDOW" in t:
        print(t, len(events[t]))

print("\n=== 2941 player state milestones ===")
milestones = []
prev = {}
for line in lines[1:]:
    frame = json.loads(line)
    rnd = frame.get("round")
    for pl in frame.get("players") or []:
        if pl.get("playerId") != 2941:
            continue
        key = (pl.get("currentNodeId"), pl.get("state"), pl.get("delivered"), pl.get("retired"), pl.get("verified"))
        if prev.get("key") != key:
            milestones.append((rnd, pl.get("currentNodeId"), pl.get("state"), pl.get("delivered"), pl.get("retired"), pl.get("verified"), pl.get("freshness"), pl.get("goodFruit")))
            prev["key"] = key
for m in milestones[:40]:
    print(m)
print("... total milestones", len(milestones))
print("last milestones:")
for m in milestones[-15:]:
    print(m)
