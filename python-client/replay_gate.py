#!/usr/bin/env python3
"""Shared replay outcome checks for local and opponent regression."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ReplayOutcome:
    path: Path
    player_id: int
    total_score: int = 0
    delivered: bool = False
    rejects: Counter = field(default_factory=Counter)
    break_guard: int = 0
    issues: list[str] = field(default_factory=list)

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


def detect_player_id(path: Path, preferred: int | None = None) -> int:
    if preferred is not None:
        return preferred
    frames = load_frames(path)
    if not frames:
        return 1001
    last = frames[-1]
    ids = [int(p.get("playerId")) for p in last.get("players") or [] if p.get("playerId") is not None]
    for candidate in (2941, 1001):
        if candidate in ids:
            return candidate
    for player in last.get("players") or []:
        name = str(player.get("name") or "")
        if "python" in name.lower():
            return int(player.get("playerId") or 1001)
    if ids:
        return ids[0]
    return 1001


def audit_outcome(
    path: Path,
    player_id: int | None = None,
    *,
    require_delivery: bool = False,
    min_score: int | None = None,
    max_resource_reject: int = 5,
) -> ReplayOutcome:
    pid = detect_player_id(path, player_id)
    audit = ReplayOutcome(path=path, player_id=pid)
    frames = load_frames(path)
    if not frames:
        audit.issues.append("empty replay")
        return audit

    for frame in frames[1:]:
        for message in frame.get("messages") or []:
            msg_type = message.get("type")
            payload = message.get("payload") or {}
            if msg_type == "ACTION_REJECTED" and payload.get("playerId") == pid:
                audit.rejects[payload.get("errorCode", "?")] += 1
            if msg_type == "BREAK_GUARD" and payload.get("playerId") == pid:
                audit.break_guard += 1

    me = next((p for p in frames[-1].get("players", []) if p.get("playerId") == pid), {})
    audit.total_score = int(me.get("totalScore") or 0)
    audit.delivered = bool(me.get("delivered"))

    if require_delivery and not audit.delivered:
        audit.issues.append("not delivered")
    if min_score is not None and audit.total_score < min_score:
        audit.issues.append(f"score {audit.total_score} < {min_score}")
    if audit.rejects["RESOURCE_NOT_ENOUGH"] > max_resource_reject:
        audit.issues.append(
            f"RESOURCE_NOT_ENOUGH x{audit.rejects['RESOURCE_NOT_ENOUGH']}"
        )
    if audit.rejects["MOVE_BLOCKED_BY_GUARD"] > 20 and audit.break_guard == 0:
        audit.issues.append(
            f"MOVE_BLOCKED_BY_GUARD x{audit.rejects['MOVE_BLOCKED_BY_GUARD']} with 0 BREAK_GUARD"
        )
    return audit
