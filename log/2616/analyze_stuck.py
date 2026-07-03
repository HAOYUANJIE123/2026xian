import json
from pathlib import Path

lines = Path(r"d:\pythonProj\gaming\2026xian\log\replay (1).txt").read_text(encoding="utf-8").splitlines()

print("=== 2941 movement r250-r600 ===")
for line in lines[250:601]:
    frame = json.loads(line)
    rnd = frame.get("round")
    pl = next((p for p in frame.get("players") or [] if p.get("playerId") == 2941), None)
    if not pl:
        continue
    node = pl.get("currentNodeId")
    state = pl.get("state")
    if rnd < 250:
        continue
    guards = {}
    for nid in ("S09", "S10", "S11", "S08"):
        n = next((x for x in frame.get("nodes") or [] if x.get("nodeId") == nid), {})
        g = n.get("guard") or {}
        if g.get("active"):
            guards[nid] = g.get("defense")
    if rnd in (250, 260, 261, 300, 350, 400, 450, 500, 516, 517, 550, 588, 589, 600) or state != "MOVING":
        print(
            f"r{rnd:3d} {node:3s} {state:12s} fresh={pl.get('freshness', 0):5.1f} guards={guards}"
        )

print("\n=== When opponent set guards ===")
for line in lines[1:]:
    frame = json.loads(line)
    rnd = frame.get("round")
    for msg in frame.get("messages") or []:
        if msg.get("type") == "GUARD_SET":
            p = msg.get("payload") or {}
            print(f"r{rnd}", p)

print("\n=== 2941 last position frames ===")
for line in lines[-5:]:
    frame = json.loads(line)
    rnd = frame.get("round")
    pl = next((p for p in frame.get("players") or [] if p.get("playerId") == 2941), None)
    print(f"r{rnd}", pl.get("currentNodeId"), pl.get("state"), "fresh", pl.get("freshness"))
