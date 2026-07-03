#!/usr/bin/env python3
import json
import sys
from pathlib import Path

PID = 2941


def frames(path: str) -> list[dict]:
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


def main() -> None:
    path = sys.argv[1]
    for fr in frames(path):
        r = fr.get("round")
        if r is None or r > 70:
            continue
        me = next((p for p in fr.get("players", []) if p.get("playerId") == PID), {})
        evs = []
        for m in fr.get("messages", []):
            t = m.get("type")
            p = m.get("payload") or {}
            if t in ("ACTION_REJECTED", "PROCESS_PROGRESS", "PROCESS_COMPLETE", "MOVE_PROGRESS"):
                if p.get("playerId") in (PID, None) or t == "PROCESS_COMPLETE":
                    evs.append((t, p.get("errorCode") or p.get("processType") or p.get("action")))
        node = next((n for n in fr.get("nodes", []) if n.get("nodeId") == "S02"), {})
        if r <= 70 or me.get("state") != "IDLE" or evs:
            if r <= 65:
                print(
                    f"r{r:3d} {me.get('currentNodeId')} {me.get('state'):10s} "
                    f"next={me.get('nextNodeId')} proc={node.get('processRound')} "
                    f"type={node.get('processType')}"
                )
                for ev in evs[:4]:
                    print(f"      {ev}")


if __name__ == "__main__":
    main()
