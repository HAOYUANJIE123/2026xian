import json
from pathlib import Path

from lychee_basic_client.strategy import RouteStrategy


def _load_replay(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_process_complete_from_messages_marks_node_done():
    path = Path(__file__).resolve().parent.parent / "log" / "2614" / "replay (15).txt"
    frames = _load_replay(path)
    strategy = RouteStrategy()
    strategy.load_start(
        {
            "edges": frames[0].get("edges", []),
            "map": frames[0].get("map") or {},
        }
    )
    player_id = 2941

    for frame in frames[1:55]:
        strategy.decide(frame, player_id)

    frame55 = frames[55]
    me = next(p for p in frame55["players"] if p["playerId"] == player_id)
    actions = strategy.decide(frame55, player_id)
    main = next(a for a in actions if a.get("action") != "WINDOW_CARD")

    assert me["currentNodeId"] == "S02"
    assert me["state"] == "WAITING"
    assert "S02" in strategy.process_attempted
    assert main["action"] == "MOVE"
    assert main["targetNodeId"] == "S03"
