#!/usr/bin/env python3
"""Replay-based preflight checks to catch hidden strategy failures before upload."""

from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from lychee_basic_client.strategy import RouteStrategy

DEFAULT_PID = 2941
REQUIRED_REPLAYS = (
    Path(__file__).resolve().parent.parent / "log" / "2614" / "replay (12).txt",
    Path(__file__).resolve().parent.parent / "log" / "2614" / "replay (15).txt",
    Path(__file__).resolve().parent.parent / "log" / "2614" / "replay (17).txt",
    Path(__file__).resolve().parent.parent / "log" / "2616" / "replay (11).txt",
    Path(__file__).resolve().parent.parent / "log" / "2616" / "replay (14).txt",
    Path(__file__).resolve().parent.parent / "log" / "2616" / "replay (16).txt",
)
REPLAY_PATHS = REQUIRED_REPLAYS


@dataclass
class ReplayAudit:
    path: Path
    issues: list[str] = field(default_factory=list)
    main_actions: Counter = field(default_factory=Counter)
    choke_idle_rounds: int = 0
    choke_idle_no_progress: int = 0
    edge_wait_rounds: int = 0
    edge_move_while_blocked: int = 0
    break_guard_count: int = 0
    repeated_claim_rounds: int = 0
    repeated_set_guard_rounds: int = 0
    edge_stuck_missed_weaken: int = 0
    claim_at_contested_choke: int = 0
    s02_waiting_no_move: int = 0
    s02_process_spam: int = 0
    s09_hold_while_racing: int = 0

    @property
    def ok(self) -> bool:
        return not self.issues


def load_frames(path: Path) -> list[dict]:
    frames: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            frames.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return frames


def _main_action(actions: list[dict]) -> dict | None:
    for action in actions:
        if action.get("action") != "WINDOW_CARD":
            return action
    return None


def _edge_blocked(frame: dict, me: dict, player_id: int) -> bool:
    next_node = me.get("nextNodeId")
    if not next_node:
        return False
    team_id = me.get("teamId", "")
    for node in frame.get("nodes") or []:
        if node.get("nodeId") != next_node:
            continue
        guard = node.get("guard") or {}
        if not guard.get("active"):
            return False
        owner = guard.get("ownerTeamId")
        defense = int(guard.get("defense") or 0)
        return bool(owner and owner != team_id and defense > 1)
    return False


def audit_replay(path: Path, player_id: int = DEFAULT_PID) -> ReplayAudit:
    audit = ReplayAudit(path=path)
    frames = load_frames(path)
    if not frames:
        audit.issues.append("empty replay")
        return audit

    strategy = RouteStrategy()
    strategy.load_start(
        {
            "edges": frames[0].get("edges", []),
            "map": frames[0].get("map")
            or {"gameplay": {"roles": {"gateNodeId": "S14", "terminalNodeIds": ["S15"]}}},
        }
    )

    last_main_key: tuple[str, str] | None = None

    for frame in frames[1:]:
        me = next((p for p in frame.get("players", []) if p.get("playerId") == player_id), None)
        if me is None:
            continue

        actions = strategy.decide(frame, player_id)
        main = _main_action(actions)
        for action in actions:
            act = action.get("action")
            if act and act != "WINDOW_CARD":
                audit.main_actions[act] += 1
        if main:
            action_name = main.get("action", "?")
            if action_name == "BREAK_GUARD":
                audit.break_guard_count += 1

            main_key = (action_name, json.dumps(main, sort_keys=True))
            if main_key == last_main_key:
                if action_name == "CLAIM_TASK":
                    audit.repeated_claim_rounds += 1
                if action_name == "SET_GUARD":
                    audit.repeated_set_guard_rounds += 1
            last_main_key = main_key

        node = me.get("currentNodeId")
        state = me.get("state")
        if node == "S09" and state == "IDLE":
            audit.choke_idle_rounds += 1
            if main and main.get("action") not in ("MOVE", "BREAK_GUARD", "PROCESS", "CLEAR"):
                audit.choke_idle_no_progress += 1
            if main and main.get("action") == "CLAIM_TASK":
                enemy = next(
                    (p for p in frame.get("players", []) if p.get("playerId") != player_id),
                    None,
                )
                if enemy and enemy.get("currentNodeId") in ("S09", "S10"):
                    audit.claim_at_contested_choke += 1

        if node == "S09" and state in ("WAITING", "MOVING") and me.get("nextNodeId") == "S10":
            audit.edge_wait_rounds += 1
            if main and main.get("action") == "MOVE" and _edge_blocked(frame, me, player_id):
                audit.edge_move_while_blocked += 1
            squad = int(me.get("squadAvailable") or 0)
            if (
                squad >= 2
                and _edge_blocked(frame, me, player_id)
                and "SQUAD_WEAKEN" not in {a.get("action") for a in actions}
            ):
                audit.edge_stuck_missed_weaken += 1

        if node == "S09" and state in ("IDLE", "WAITING") and not me.get("nextNodeId"):
            if main and main.get("action") == "WAIT" and strategy._ahead_of_opponent(
                frame, player_id
            ):
                audit.s09_hold_while_racing += 1

        if node == "S02" and state == "WAITING" and not me.get("nextNodeId"):
            if main and main.get("action") == "PROCESS":
                audit.s02_process_spam += 1
            elif main and main.get("action") != "MOVE":
                audit.s02_waiting_no_move += 1

    if audit.repeated_claim_rounds > 20:
        audit.issues.append(
            f"strategy repeats identical CLAIM_TASK {audit.repeated_claim_rounds} rounds"
        )
    if audit.repeated_set_guard_rounds > 5:
        audit.issues.append(
            f"strategy repeats identical SET_GUARD {audit.repeated_set_guard_rounds} rounds"
        )
    if audit.choke_idle_no_progress > 30:
        audit.issues.append(
            f"S09 IDLE {audit.choke_idle_no_progress} rounds without MOVE/BREAK/PROCESS"
        )
    if audit.edge_move_while_blocked > 5:
        audit.issues.append(
            f"strategy keeps MOVE on blocked S09->S10 edge x{audit.edge_move_while_blocked}"
        )
    if audit.edge_stuck_missed_weaken > 10:
        audit.issues.append(
            f"squad available but no SQUAD_WEAKEN on blocked edge x{audit.edge_stuck_missed_weaken}"
        )
    if audit.claim_at_contested_choke > 0:
        audit.issues.append(
            f"CLAIM_TASK at contested S09 choke x{audit.claim_at_contested_choke}"
        )
    if audit.s02_process_spam > 5:
        audit.issues.append(
            f"S02 WAITING repeats PROCESS x{audit.s02_process_spam} instead of leaving"
        )
    if audit.s02_waiting_no_move > 30:
        audit.issues.append(
            f"S02 WAITING {audit.s02_waiting_no_move} rounds without MOVE"
        )
    if audit.s09_hold_while_racing > 10:
        audit.issues.append(
            f"S09 WAIT while ahead/racing x{audit.s09_hold_while_racing}"
        )

    return audit


def run_preflight(
    paths: list[Path] | None = None,
    player_id: int = DEFAULT_PID,
    *,
    strict: bool = False,
) -> None:
    expected = list(paths or REQUIRED_REPLAYS)
    targets = [p for p in expected if p.is_file()]
    if strict and len(targets) != len(expected):
        missing = [p for p in expected if not p.is_file()]
        raise SystemExit(
            "preflight replay: missing required files:\n"
            + "\n".join(f"  - {p}" for p in missing)
        )
    if not targets:
        print("preflight replay: no replay files found, skipping")
        return

    failed = 0
    for path in targets:
        audit = audit_replay(path, player_id)
        print(f"\n=== preflight replay: {path.name} ===")
        print(f"  main actions: {dict(audit.main_actions)}")
        print(
            "  S09 idle:",
            audit.choke_idle_rounds,
            "no-progress:",
            audit.choke_idle_no_progress,
            "edge wait:",
            audit.edge_wait_rounds,
        )
        print(f"  BREAK_GUARD decisions: {audit.break_guard_count}")
        if audit.issues:
            failed += 1
            for issue in audit.issues:
                print(f"  ISSUE: {issue}")
        else:
            print("  ok")

    if failed:
        raise SystemExit(f"preflight replay failed: {failed} replay(s) with issues")


def main() -> None:
    paths = [Path(p) for p in sys.argv[1:]] if len(sys.argv) > 1 else None
    run_preflight(paths)


if __name__ == "__main__":
    main()
