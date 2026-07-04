import math
import random
from typing import Any, Optional

from .graph import build_adjacency, build_weighted_adjacency, shortest_weighted_path

WAIT_STATES = frozenset(
    {
        "PROCESSING",
        "VERIFYING",
        "CONTESTING",
        "RESTING",
        "FORCED_PASSING",
        "COST_BANKRUPT",
        "MOVING",
    }
)

TASK_TARGET_BASE = 90
TASK_TARGET_STRETCH = 120
TASK_CLAIM_DEADLINE = 520
MAIN_ROUTE = ("S01", "S02", "S03", "S07", "S09", "S10", "S11", "S12", "S13", "S14", "S15")
ROUTE_TASK_NODES = frozenset({"S03", "S07", "S09", "S10", "S11", "S13"})
ICE_CLAIM_NODES = frozenset({"S03", "S07"})
ICE_STOPS = ("S03", "S07")
HORSE_CLAIM_NODES = frozenset({"S09"})
HORSE_USE_NODES = frozenset({"S07", "S09", "S10", "S11", "S12", "S13"})
RUSH_PROTECT_NODES = frozenset({"S13"})
ROUTE_PROCESS_NODES: dict[str, dict[str, Any]] = {
    "S02": {"processType": "TRANSFER", "processRound": 4, "canWindow": True},
}
SKIP_PROCESS_NODES: frozenset[str] = frozenset()
WINDOW_PLAY_CARDS = ("BING_ZHENG", "YAN_DIE", "QIANG_XING", "XIAN_GONG")
CONTEST_TYPE_PRIORITY = {
    "TASK": 0,
    "RESOURCE": 1,
    "DOCK": 2,
    "OBSTACLE": 3,
    "PASS": 4,
    "GATE": 5,
}
GUARD_HOLD_NODES = frozenset({"S09", "S10", "S11", "S12"})
GUARD_SET_ROUTE_NODES = frozenset({"S10", "S11", "S12"})
GUARD_FORBIDDEN_NODES = frozenset({"S01", "S15"})
MAX_OWN_GUARDS = 2
WINDOW_CARD_PRIORITY = ("XIAN_GONG", "BING_ZHENG", "QIANG_XING", "YAN_DIE")
SCOUT_MARK_TTL = 45
MOVE_WEIGHT_PER_ROUND = 18000
EDGE_MS_PER_ROUND = 1008
GUARD_HOLD_MAX_ROUNDS = 20
MIN_GUARD_LEAD_FRAMES = 6
GUARD_BEFORE_SIDE_NODES = frozenset({"S07", "S09", "S10", "S11", "S12"})
EDGE_GUARD_PASS_AFTER = 8
CLEAR_NEAR_MAX_ROUNDS = 30
ICE_USE_FRESHNESS = 92.0
ICE_USE_LATE_FRESHNESS = 95.0
FIRST_HALF_PROGRESS_NODE = "S09"
NON_BLACKLIST_MOVE_ERRORS = frozenset(
    {
        "PROCESS_REQUIRED",
        "MOVE_BLOCKED_BY_GUARD",
        "OBJECT_BUSY",
        "MOVING_ACTION_FORBIDDEN",
    }
)


class RouteStrategy:
    def __init__(self) -> None:
        self.gate_node_id = "S14"
        self.terminal_node_id = "S15"
        self.adjacency: dict[str, list[str]] = {}
        self.weighted_adjacency: dict[str, list[tuple[str, int]]] = {}
        self.process_attempted: set[str] = set()
        self._failed_moves: set[tuple[str, str]] = set()
        self._failed_clears: set[tuple[str, str]] = set()
        self._failed_breaks: set[tuple[str, str]] = set()
        self._pending_move: Optional[tuple[str, str]] = None
        self._pending_clear: Optional[tuple[str, str]] = None
        self._pending_process: Optional[str] = None
        self._last_node_id: Optional[str] = None
        self._resource_claimed_nodes: set[str] = set()
        self._ice_depleted_nodes: set[str] = set()
        self._completed_task_ids: set[str] = set()
        self._blocked_task_ids: set[str] = set()
        self._pending_task_claim: Optional[str] = None
        self._task_base_total = 0
        self._guard_hold_rounds: dict[str, int] = {}
        self._edge_guard_waits: dict[tuple[str, str], int] = {}
        self._squad_inflight: set[tuple[str, str]] = set()
        self._active_contest_id: Optional[str] = None
        self._last_dock_process_round: Optional[int] = None
        self._global_contest_seq = 0
        self._was_contesting = False
        self._process_started_nodes: set[str] = set()
        self._window_suppressed_nodes: dict[str, int] = {}
        self._window_draw_counts: dict[str, int] = {}
        self._guard_set_nodes: set[str] = set()
        self._pending_set_guard: Optional[str] = None
        self._pending_forced_pass: Optional[tuple[str, str]] = None
        self._opponent_completed_process: set[str] = set()
        self._node_catalog: dict[str, dict[str, Any]] = {}
        self._opp_edge_start_round: dict[tuple[int, str, str], int] = {}
        self._opp_edge_last_progress: dict[tuple[int, str, str], int] = {}
        self._opp_active_edge_key: dict[int, tuple[int, str, str]] = {}

    def load_start(self, data: dict[str, Any]) -> None:
        roles = (data.get("map") or {}).get("gameplay", {}).get("roles", {})
        self.gate_node_id = roles.get("gateNodeId", "S14")
        terminal_ids = roles.get("terminalNodeIds") or ["S15"]
        self.terminal_node_id = terminal_ids[0]
        edges = data.get("edges") or []
        self.adjacency = build_adjacency(edges)
        self.weighted_adjacency = build_weighted_adjacency(edges)
        self.process_attempted.clear()
        self._failed_moves.clear()
        self._failed_clears.clear()
        self._failed_breaks.clear()
        self._pending_move = None
        self._pending_clear = None
        self._pending_process = None
        self._last_node_id = None
        self._resource_claimed_nodes.clear()
        self._ice_depleted_nodes.clear()
        self._completed_task_ids.clear()
        self._blocked_task_ids.clear()
        self._pending_task_claim = None
        self._task_base_total = 0
        self._guard_hold_rounds.clear()
        self._edge_guard_waits.clear()
        self._pending_forced_pass = None
        self._squad_inflight.clear()
        self._active_contest_id = None
        self._last_dock_process_round = None
        self._global_contest_seq = 0
        self._was_contesting = False
        self._process_started_nodes.clear()
        self._window_suppressed_nodes.clear()
        self._window_draw_counts.clear()
        self._guard_set_nodes.clear()
        self._pending_set_guard = None
        self._opponent_completed_process.clear()
        self._node_catalog.clear()
        self._opp_edge_start_round.clear()
        self._opp_edge_last_progress.clear()
        self._opp_active_edge_key.clear()
        for node in data.get("nodes") or []:
            node_id = node.get("nodeId")
            if node_id:
                self._node_catalog[node_id] = dict(node)

    @staticmethod
    def _event_value(event: dict[str, Any], key: str) -> Any:
        payload = event.get("payload") or {}
        if key in payload and payload[key] is not None:
            return payload[key]
        return event.get(key)

    @staticmethod
    def _round_events(data: dict[str, Any]) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        for key in ("events", "messages", "importantEvents"):
            part = data.get(key)
            if part:
                merged.extend(part)
        return merged

    def _resolve_contest_id(self, data: dict[str, Any], player_id: int) -> Optional[str]:
        if self._active_contest_id:
            return self._active_contest_id

        for contest in data.get("contests") or []:
            if contest.get("resolved") or contest.get("status") == "SUPPRESSED":
                continue
            contest_id = contest.get("contestId")
            if not contest_id:
                continue
            participants = (contest.get("redPlayerId"), contest.get("bluePlayerId"))
            if player_id in participants:
                return contest_id

        for event in reversed(self._round_events(data)):
            contest_id = RouteStrategy._event_value(event, "contestId")
            if not contest_id:
                continue
            if event.get("type") in (
                "WINDOW_CONTEST_START",
                "WINDOW_CARD_REVEAL",
                "WINDOW_CONTEST_DRAW",
            ):
                return contest_id

        if self._last_dock_process_round is not None:
            seq = max(self._global_contest_seq, 1)
            return f"C_{self._last_dock_process_round:03d}_{seq:03d}"

        return None

    def _resolve_contest_ids(self, data: dict[str, Any], player_id: int) -> list[str]:
        contest_ids: list[str] = []
        seen: set[str] = set()
        for contest in data.get("contests") or []:
            if contest.get("resolved") or contest.get("status") == "SUPPRESSED":
                continue
            contest_id = contest.get("contestId")
            if not contest_id or contest_id in seen:
                continue
            participants = (contest.get("redPlayerId"), contest.get("bluePlayerId"))
            if player_id in participants:
                contest_ids.append(contest_id)
                seen.add(contest_id)

        if contest_ids:
            return contest_ids

        for event in reversed(self._round_events(data)):
            contest_id = RouteStrategy._event_value(event, "contestId")
            if not contest_id or contest_id in seen:
                continue
            if event.get("type") in (
                "WINDOW_CONTEST_START",
                "WINDOW_CARD_REVEAL",
                "WINDOW_CONTEST_DRAW",
            ):
                contest_ids.append(contest_id)
                seen.add(contest_id)

        if contest_ids:
            return contest_ids

        fallback = self._resolve_contest_id(data, player_id)
        return [fallback] if fallback else []

    def _contest_record(self, data: dict[str, Any], contest_id: str) -> Optional[dict[str, Any]]:
        for contest in data.get("contests") or []:
            if contest.get("contestId") == contest_id:
                return contest
        return None

    def _pick_primary_contest_id(
        self, data: dict[str, Any], contest_ids: list[str]
    ) -> Optional[str]:
        if not contest_ids:
            return None
        best_id = contest_ids[0]
        best_rank = len(CONTEST_TYPE_PRIORITY) + 1
        for contest_id in contest_ids:
            contest = self._contest_record(data, contest_id)
            if contest is None:
                continue
            rank = CONTEST_TYPE_PRIORITY.get(contest.get("contestType", ""), best_rank)
            if rank < best_rank:
                best_rank = rank
                best_id = contest_id
        return best_id

    def _contest_beat_index(self, data: dict[str, Any], contest_id: str) -> int:
        for contest in data.get("contests") or []:
            if contest.get("contestId") != contest_id:
                continue
            round_index = contest.get("roundIndex")
            if isinstance(round_index, int) and round_index >= 1:
                return round_index

        for event in reversed(self._round_events(data)):
            if RouteStrategy._event_value(event, "contestId") != contest_id:
                continue
            if event.get("type") == "WINDOW_CARD_REVEAL":
                round_index = RouteStrategy._event_value(event, "roundIndex")
                if isinstance(round_index, int):
                    return min(3, round_index + 1)
            if event.get("type") == "WINDOW_CONTEST_START":
                return 1
        return 1

    def _contest_target_node(self, data: dict[str, Any], contest_id: str) -> Optional[str]:
        for contest in data.get("contests") or []:
            if contest.get("contestId") == contest_id:
                target = contest.get("targetNodeId")
                if target:
                    return target
        for event in reversed(self._round_events(data)):
            if RouteStrategy._event_value(event, "contestId") != contest_id:
                continue
            target = RouteStrategy._event_value(event, "targetNodeId")
            if target:
                return target
        return None

    def _contest_point_lead(
        self, data: dict[str, Any], contest_id: str, player_id: int
    ) -> Optional[int]:
        contest = self._contest_record(data, contest_id)
        if contest is None:
            return None
        red_id = contest.get("redPlayerId")
        blue_id = contest.get("bluePlayerId")
        red_point = int(contest.get("redPoint") or 0)
        blue_point = int(contest.get("bluePoint") or 0)
        if player_id == red_id:
            return red_point - blue_point
        if player_id == blue_id:
            return blue_point - red_point
        return None

    def decide(self, data: dict[str, Any], player_id: int) -> list[dict[str, Any]]:
        self._sync_squad_feedback(data, player_id)
        self._sync_window_contest_state(data, player_id)
        self._sync_guard_set_feedback(data, player_id)
        self._sync_opponent_edge_tracking(data, player_id)

        me = self._find_player(data, player_id)
        state = me.get("state", "IDLE") if me is not None else "IDLE"

        if state == "CONTESTING":
            window_actions = self._window_actions(data, player_id)
            if window_actions:
                return window_actions
            contest_id = self._pick_primary_contest_id(
                data, self._resolve_contest_ids(data, player_id)
            )
            if contest_id:
                return [
                    {
                        "action": "WINDOW_CARD",
                        "contestId": contest_id,
                        "card": "ABSTAIN",
                    }
                ]
            return [{"action": "WAIT"}]

        actions = []
        main_action = self._main_action(data, player_id)
        if main_action is not None:
            actions.append(main_action)

        squad_action = self._squad_action(data, player_id)
        if squad_action is not None:
            actions.append(squad_action)

        if (
            not actions
            and me is not None
            and not me.get("delivered")
            and not me.get("retired")
        ):
            actions.append({"action": "WAIT"})

        return actions

    def _sync_window_contest_state(self, data: dict[str, Any], player_id: int) -> None:
        me = self._find_player(data, player_id)
        if me is None:
            return

        for event in self._round_events(data):
            event_type = event.get("type")
            contest_id = RouteStrategy._event_value(event, "contestId")
            if event_type == "WINDOW_CONTEST_END":
                target_node = RouteStrategy._event_value(event, "targetNodeId")
                winner = RouteStrategy._event_value(event, "winnerTeamId")
                if target_node and winner not in ("DRAW", "", None):
                    self._window_draw_counts.pop(target_node, None)
                    if winner != me.get("teamId"):
                        self._process_started_nodes.discard(target_node)
                        if self._pending_process == target_node:
                            self._pending_process = None
                if winner in ("DRAW", "", None) and target_node:
                    self._process_started_nodes.discard(target_node)
                    if not self._window_process_suppressed(data, target_node):
                        self.process_attempted.discard(target_node)
                    if self._pending_process == target_node:
                        self._pending_process = None
                if contest_id == self._active_contest_id:
                    self._active_contest_id = None
                continue
            if event_type == "WINDOW_CONTEST_START" and contest_id:
                self._active_contest_id = contest_id
                target_node = RouteStrategy._event_value(event, "targetNodeId")
                if target_node:
                    self._process_started_nodes.discard(target_node)
                    if self._pending_process == target_node:
                        self._pending_process = None
                contest_round = event.get("round")
                if isinstance(contest_round, int):
                    self._last_dock_process_round = contest_round
            elif event_type in ("WINDOW_CARD_REVEAL", "WINDOW_CONTEST_DRAW") and contest_id:
                self._active_contest_id = contest_id
            if event_type == "WINDOW_CONTEST_DRAW":
                target_node = RouteStrategy._event_value(event, "targetNodeId")
                if target_node:
                    draw_count = self._window_draw_counts.get(target_node, 0) + 1
                    self._window_draw_counts[target_node] = draw_count
                    self._process_started_nodes.discard(target_node)
                    if not self._window_process_suppressed(data, target_node):
                        self.process_attempted.discard(target_node)
                    if self._pending_process == target_node:
                        self._pending_process = None
                    contest_round = data.get("round")
                    if draw_count >= 2 and isinstance(contest_round, int):
                        self._window_suppressed_nodes[target_node] = contest_round + 18
                        self.process_attempted.add(target_node)
            if event_type == "WINDOW_CONTEST_REPEAT_SUPPRESSED":
                target_node = RouteStrategy._event_value(event, "targetNodeId")
                suppress_until = RouteStrategy._event_value(event, "suppressUntilRound")
                if target_node and isinstance(suppress_until, int):
                    self._window_suppressed_nodes[target_node] = suppress_until

        for contest in data.get("contests") or []:
            if contest.get("status") == "SUPPRESSED":
                target_node = contest.get("targetNodeId")
                suppress_until = contest.get("suppressUntilRound")
                if (
                    target_node
                    and isinstance(suppress_until, int)
                    and isinstance(data.get("round"), int)
                ):
                    self._window_suppressed_nodes[target_node] = suppress_until
                if contest.get("contestId") == self._active_contest_id:
                    self._active_contest_id = None
                continue
            contest_id = contest.get("contestId")
            if not contest_id:
                continue
            if contest.get("resolved"):
                if contest_id == self._active_contest_id:
                    self._active_contest_id = None
                continue
            participants = (contest.get("redPlayerId"), contest.get("bluePlayerId"))
            if player_id in participants:
                self._active_contest_id = contest_id

        is_contesting = me.get("state") == "CONTESTING"
        if is_contesting and not self._active_contest_id:
            for event in reversed(self._round_events(data)):
                event_type = event.get("type") or ""
                contest_id = RouteStrategy._event_value(event, "contestId")
                if contest_id and event_type.startswith("WINDOW"):
                    self._active_contest_id = contest_id
                    break
            if not self._active_contest_id and self._last_dock_process_round is not None:
                self._global_contest_seq += 1
                self._active_contest_id = (
                    f"C_{self._last_dock_process_round:03d}_{self._global_contest_seq:03d}"
                )
        if not is_contesting:
            self._was_contesting = False
        else:
            self._was_contesting = True

    def _window_actions(self, data: dict[str, Any], player_id: int) -> list[dict[str, Any]]:
        me = self._find_player(data, player_id)
        if me is None:
            return []
        if me.get("state") != "CONTESTING":
            return []

        contest_ids = self._resolve_contest_ids(data, player_id)
        contest_id = self._pick_primary_contest_id(data, contest_ids)
        if not contest_id:
            return []

        beat_index = self._contest_beat_index(data, contest_id)
        target_node = (
            self._contest_target_node(data, contest_id) or me.get("currentNodeId") or ""
        )
        draw_count = self._window_draw_counts.get(target_node, 0)
        card = self._pick_window_card(
            me, beat_index, draw_count, player_id, data, contest_id
        )
        return [
            {
                "action": "WINDOW_CARD",
                "contestId": contest_id,
                "card": card,
            }
        ]

    def _window_action(self, data: dict[str, Any], player_id: int) -> Optional[dict[str, Any]]:
        window_actions = self._window_actions(data, player_id)
        return window_actions[0] if window_actions else None

    @staticmethod
    def _affordable_window_cards(me: dict[str, Any]) -> list[str]:
        cards: list[str] = []
        guard_ap = me.get("guardActionPoint")
        if guard_ap is None:
            guard_ap = 4
        if int(guard_ap) >= 1:
            cards.append("BING_ZHENG")

        resources = me.get("resources") or {}
        if resources.get("PASS_TOKEN", 0) > 0 or resources.get("OFFICIAL_PERMIT", 0) > 0:
            cards.append("YAN_DIE")

        if RouteStrategy._has_move_buff(me):
            cards.append("QIANG_XING")
        elif resources.get("FAST_HORSE", 0) > 0 or resources.get("SHORT_HORSE", 0) > 0:
            cards.append("QIANG_XING")

        if float(me.get("freshness", 0)) >= 80 and int(me.get("goodFruit", 0)) >= 1:
            cards.append("XIAN_GONG")

        return cards

    def _pick_window_card(
        self,
        me: dict[str, Any],
        beat_index: int,
        draw_count: int,
        player_id: int,
        data: dict[str, Any],
        contest_id: str = "",
    ) -> str:
        if beat_index >= 3 and contest_id:
            lead = self._contest_point_lead(data, contest_id, player_id)
            if lead is not None and lead >= 2:
                return "ABSTAIN"
        affordable_set = set(RouteStrategy._affordable_window_cards(me))
        affordable = [card for card in WINDOW_PLAY_CARDS if card in affordable_set]
        if not affordable:
            return "ABSTAIN"
        return random.choice(affordable)

    def _main_action(self, data: dict[str, Any], player_id: int) -> Optional[dict[str, Any]]:
        me = self._find_player(data, player_id)
        if me is None:
            return None

        self._sync_move_feedback(data, player_id)
        self._sync_clear_feedback(data, player_id)
        self._sync_break_feedback(data, player_id)
        self._sync_process_feedback(data, player_id)
        self._sync_task_feedback(data, player_id)
        self._sync_guard_set_feedback(data, player_id)

        state = me.get("state", "IDLE")
        if state == "CONTESTING":
            return None
        if state in WAIT_STATES and state not in ("MOVING", "WAITING"):
            return {"action": "WAIT"}
        if me.get("delivered") or me.get("retired"):
            return None

        current_node = me.get("currentNodeId")
        if not current_node:
            return None

        if self._last_node_id and self._last_node_id != current_node:
            self.process_attempted.discard(self._last_node_id)
            self._guard_hold_rounds.pop(self._last_node_id, None)
        self._last_node_id = current_node

        phase = data.get("phase", "NORMAL")

        if state == "MOVING":
            edge_action = self._edge_guard_response(data, me, phase, current_node)
            if edge_action is not None:
                return edge_action
            next_node = me.get("nextNodeId")
            if next_node:
                node = self._find_node(data, current_node)
                if self._needs_process(node, current_node):
                    if self._opponent_competing_for_process(
                        data, player_id, current_node
                    ):
                        return {"action": "WAIT"}
                    self._pending_process = current_node
                    if current_node == "S02":
                        self._last_dock_process_round = data.get("round")
                    self._process_started_nodes.add(current_node)
                    return {"action": "PROCESS", "targetNodeId": current_node}
                self._pending_move = (current_node, next_node)
                return {"action": "MOVE", "targetNodeId": next_node}
            return None

        if state == "WAITING":
            edge_action = self._edge_guard_response(data, me, phase, current_node)
            if edge_action is not None:
                return edge_action
            node = self._find_node(data, current_node)
            if self._needs_process(node, current_node):
                if self._window_process_suppressed(data, current_node):
                    self.process_attempted.add(current_node)
                    escape = self._escape_process_node_action(
                        data, me, player_id, phase, current_node, node
                    )
                    if escape is not None:
                        return escape
                if not self._opponent_competing_for_process(
                    data, player_id, current_node
                ):
                    self._pending_process = current_node
                    if current_node == "S02":
                        self._last_dock_process_round = data.get("round")
                    self._process_started_nodes.add(current_node)
                    return {"action": "PROCESS", "targetNodeId": current_node}
                return {"action": "WAIT"}
            next_node = me.get("nextNodeId")
            if next_node:
                guard_action = self._set_guard_action(
                    data, me, player_id, current_node, node
                )
                if guard_action is not None:
                    return guard_action
                if self._hold_move_for_guard(data, me, player_id, current_node):
                    return {"action": "WAIT"}
                return {"action": "MOVE", "targetNodeId": next_node}
            if (
                phase == "RUSH"
                and not me.get("verified")
                and current_node == self.gate_node_id
            ):
                return {"action": "VERIFY_GATE", "targetNodeId": self.gate_node_id}
            if me.get("verified") and current_node == self.gate_node_id:
                return {"action": "MOVE", "targetNodeId": self.terminal_node_id}
            escape = self._escape_process_node_action(
                data, me, player_id, phase, current_node, node
            )
            if escape is not None:
                return escape

        node = self._find_node(data, current_node)

        if current_node == self.terminal_node_id:
            if me.get("verified") and self._can_deliver(me):
                return {"action": "DELIVER"}

        if phase == "RUSH" and not me.get("verified") and current_node == self.gate_node_id:
            return {"action": "VERIFY_GATE", "targetNodeId": self.gate_node_id}

        rush_action = self._rush_protect_action(me, phase, current_node)
        if rush_action is not None:
            return rush_action

        set_guard_action = self._set_guard_action(data, me, player_id, current_node, node)
        if set_guard_action is not None:
            return set_guard_action

        if self._needs_process(node, current_node):
            if self._window_process_suppressed(data, current_node):
                self.process_attempted.add(current_node)
                escape = self._escape_process_node_action(
                    data, me, player_id, phase, current_node, node
                )
                if escape is not None:
                    return escape
            if self._opponent_processing_blocks_process(data, player_id, current_node):
                return {"action": "WAIT"}
            self._pending_process = current_node
            if current_node == "S02":
                self._last_dock_process_round = data.get("round")
            self._process_started_nodes.add(current_node)
            return {"action": "PROCESS", "targetNodeId": current_node}

        defer_side = self._defer_side_objectives_for_progress(
            data, player_id, phase, current_node
        )
        guard_blocks_side = self._should_prioritize_guard_over_side_objectives(
            data, player_id, current_node
        )
        skip_side = defer_side or guard_blocks_side
        allow_urgent_ice = self._needs_urgent_ice_claim(
            me, phase
        ) and not guard_blocks_side

        if current_node in GUARD_HOLD_NODES:
            if not skip_side or allow_urgent_ice:
                resource_action = self._claim_resource_action(node, current_node)
                if resource_action is not None:
                    return resource_action
            use_action = self._use_resource_action(me, current_node, phase)
            if use_action is not None:
                return use_action

        if not skip_side:
            task_action = self._task_action(data, current_node, node, player_id)
            if task_action is not None:
                return task_action

        if not skip_side or allow_urgent_ice:
            resource_action = self._claim_resource_action(node, current_node)
            if resource_action is not None:
                return resource_action

        use_action = self._use_resource_action(me, current_node, phase)
        if use_action is not None:
            return use_action

        goal = self._goal(me, phase, data, current_node)
        if goal is None or current_node == goal:
            return None

        clear_action = self._clear_action(data, me, current_node, goal)
        if clear_action is not None:
            return clear_action

        guard_action = self._guard_breakthrough_action(data, me, current_node, goal)
        if guard_action is not None:
            return guard_action

        hold_action = self._guard_hold_action(data, me, player_id, current_node)
        if hold_action is not None:
            return hold_action

        target = self._pick_move_target(data, me, current_node, goal)
        if target is None:
            return None
        if self._hold_move_for_guard(data, me, player_id, current_node):
            return {"action": "WAIT"}
        self._pending_move = (current_node, target)
        return {"action": "MOVE", "targetNodeId": target}

    def _sync_move_feedback(self, data: dict[str, Any], player_id: int) -> None:
        if self._pending_move is None:
            return
        for result in data.get("actionResults") or []:
            if result.get("playerId") != player_id:
                continue
            if result.get("action") != "MOVE":
                continue
            if result.get("accepted"):
                self._failed_moves.discard(self._pending_move)
            elif result.get("errorCode") not in NON_BLACKLIST_MOVE_ERRORS:
                self._failed_moves.add(self._pending_move)
                from_node, _ = self._pending_move
                reject_reason = str(
                    result.get("errorCode")
                    or result.get("reason")
                    or result.get("message")
                    or ""
                )
                if "PROCESS_REQUIRED" in reject_reason:
                    self._process_started_nodes.discard(from_node)
            break
        self._pending_move = None

    def _sync_clear_feedback(self, data: dict[str, Any], player_id: int) -> None:
        if self._pending_clear is None:
            return
        for result in data.get("actionResults") or []:
            if result.get("playerId") != player_id:
                continue
            if result.get("action") != "CLEAR":
                continue
            if not result.get("accepted"):
                self._failed_clears.add(self._pending_clear)
            break
        self._pending_clear = None

    def _sync_break_feedback(self, data: dict[str, Any], player_id: int) -> None:
        for result in data.get("actionResults") or []:
            if result.get("playerId") != player_id:
                continue
            if result.get("action") not in ("BREAK_GUARD", "FORCED_PASS"):
                continue
            target = result.get("targetNodeId")
            current = self._last_node_id
            if target and current:
                key = (current, target)
                if result.get("accepted"):
                    self._failed_breaks.discard(key)
                    if self._pending_forced_pass == key:
                        self._pending_forced_pass = None
                else:
                    self._failed_breaks.add(key)
                    if self._pending_forced_pass == key:
                        self._pending_forced_pass = None
            break

        for event in self._round_events(data):
            if event.get("type") != "ACTION_REJECTED":
                continue
            payload = event.get("payload") or {}
            if payload.get("playerId") != player_id:
                continue
            rejected_action = payload.get("action")
            if rejected_action in ("BREAK_GUARD", "FORCED_PASS"):
                target = payload.get("targetNodeId")
                current = self._last_node_id
                if target and current:
                    self._failed_breaks.add((current, target))
                if self._pending_forced_pass is not None:
                    self._failed_breaks.add(self._pending_forced_pass)
                    self._pending_forced_pass = None
                continue
            if self._pending_forced_pass is None:
                continue
            error_code = str(payload.get("errorCode") or "")
            if error_code in ("MOVING_ACTION_FORBIDDEN", "MOVE_BLOCKED_BY_GUARD"):
                self._failed_breaks.add(self._pending_forced_pass)
                self._pending_forced_pass = None

    def _sync_process_feedback(self, data: dict[str, Any], player_id: int) -> None:
        for event in self._round_events(data):
            if event.get("type") != "PROCESS_COMPLETE":
                continue
            payload = event.get("payload") or {}
            completed_player = payload.get("playerId")
            node_id = payload.get("targetNodeId")
            if completed_player == player_id and node_id:
                self.process_attempted.add(node_id)
                self._process_started_nodes.discard(node_id)
                self._window_draw_counts.pop(node_id, None)
                if self._pending_process == node_id:
                    self._pending_process = None
            elif completed_player and completed_player != player_id and node_id:
                self._opponent_completed_process.add(node_id)

        for event in self._round_events(data):
            if event.get("type") != "ACTION_REJECTED":
                continue
            payload = event.get("payload") or {}
            if payload.get("playerId") != player_id:
                continue
            if payload.get("errorCode") != "WINDOW_DRAW_RETRY_LIMIT":
                continue
            for result in data.get("actionResults") or []:
                if result.get("playerId") != player_id:
                    continue
                if result.get("action") == "PROCESS":
                    target = result.get("targetNodeId")
                    if target:
                        self._process_started_nodes.add(target)
                        self.process_attempted.add(target)
                    break
            break

        if self._pending_process is None:
            return
        for result in data.get("actionResults") or []:
            if result.get("playerId") != player_id:
                continue
            if result.get("action") != "PROCESS":
                continue
            if not result.get("accepted"):
                self.process_attempted.discard(self._pending_process)
                if self._pending_process:
                    self._process_started_nodes.discard(self._pending_process)
            elif self._pending_process:
                self._process_started_nodes.add(self._pending_process)
            if result.get("errorCode") == "WINDOW_DRAW_RETRY_LIMIT":
                target = result.get("targetNodeId")
                if target:
                    self._process_started_nodes.add(target)
                    self.process_attempted.add(target)
            self._pending_process = None
            break

    def _sync_squad_feedback(self, data: dict[str, Any], player_id: int) -> None:
        squad_actions = {
            "SQUAD_SCOUT",
            "SQUAD_CLEAR",
            "SQUAD_REINFORCE",
            "SQUAD_WEAKEN",
        }
        for event in self._round_events(data):
            event_type = event.get("type")
            payload = event.get("payload") or {}
            if payload.get("playerId") != player_id:
                continue
            if event_type == "SQUAD_FAILED":
                action = payload.get("action")
                target = payload.get("targetNodeId")
                if action and target:
                    self._squad_inflight.discard((action, target))
                continue
            if event_type in squad_actions:
                target = payload.get("targetNodeId")
                if target:
                    self._squad_inflight.discard((event_type, target))

        for result in data.get("actionResults") or []:
            if result.get("playerId") != player_id:
                continue
            action = result.get("action")
            if action not in squad_actions:
                continue
            target = result.get("targetNodeId")
            if not target:
                continue
            if not result.get("accepted"):
                self._squad_inflight.discard((action, target))

    def _squad_action(self, data: dict[str, Any], player_id: int) -> Optional[dict[str, Any]]:
        me = self._find_player(data, player_id)
        if me is None:
            return None
        if me.get("delivered") or me.get("retired"):
            return None
        if me.get("state") in ("RESTING", "CONTESTING"):
            return None
        if data.get("phase", "NORMAL") == "RUSH":
            return None

        squad_available = int(me.get("squadAvailable", 0))
        if squad_available <= 0:
            return None

        current_node = me.get("currentNodeId")
        if not current_node:
            return None

        action: Optional[dict[str, Any]] = None
        if squad_available >= 2:
            weaken_target = self._squad_weaken_target(data, me, current_node)
            if weaken_target is not None:
                action = {"action": "SQUAD_WEAKEN", "targetNodeId": weaken_target}

        if action is None and squad_available >= 1:
            scout_target = self._squad_scout_target(data, me, current_node)
            if scout_target is not None:
                action = {"action": "SQUAD_SCOUT", "targetNodeId": scout_target}

        if action is None and squad_available >= 2:
            clear_target = self._squad_clear_target(data, me, current_node)
            if clear_target is not None:
                action = {"action": "SQUAD_CLEAR", "targetNodeId": clear_target}

        if action is None:
            return None

        self._squad_inflight.add((action["action"], action["targetNodeId"]))
        return action

    def _forward_route_nodes(self, current_node: str) -> list[str]:
        current_idx = self._route_index(current_node)
        if current_idx < 0:
            return list(MAIN_ROUTE)
        return list(MAIN_ROUTE[current_idx + 1 :])

    def _squad_weaken_target(
        self,
        data: dict[str, Any],
        me: dict[str, Any],
        current_node: str,
    ) -> Optional[str]:
        if self._route_index(current_node) < self._route_index("S09"):
            return None
        team_id = me.get("teamId", "")
        candidates: list[tuple[int, str]] = []
        next_node = me.get("nextNodeId")
        route_nodes = list(self._forward_route_nodes(current_node))
        if next_node and next_node not in route_nodes:
            route_nodes.insert(0, next_node)
        for node_id in route_nodes:
            if ("SQUAD_WEAKEN", node_id) in self._squad_inflight:
                continue
            if not self._enemy_guard_blocks(data, node_id, team_id):
                continue
            defense = self._guard_defense(data, node_id, team_id)
            if defense <= 1:
                continue
            candidates.append((defense, node_id))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (-item[0], item[1]))
        return candidates[0][1]

    def _squad_scout_target(
        self,
        data: dict[str, Any],
        me: dict[str, Any],
        current_node: str,
    ) -> Optional[str]:
        team_id = me.get("teamId", "")
        if self._route_index(current_node) < self._route_index("S02"):
            return None
        node_id = self._next_main_route_hop(current_node)
        if node_id is None:
            return None
        if ("SQUAD_SCOUT", node_id) in self._squad_inflight:
            return None
        if self._has_own_scout_mark(data, node_id, team_id):
            return None
        if not self._node_benefits_from_scout(data, node_id, current_node):
            return None
        if self._scout_mark_will_expire_before_use(
            data, me, current_node, node_id, data.get("round")
        ):
            return None
        return node_id

    def _squad_clear_target(
        self,
        data: dict[str, Any],
        me: dict[str, Any],
        current_node: str,
    ) -> Optional[str]:
        node_id = self._next_main_route_hop(current_node)
        if node_id is None:
            return None
        if ("SQUAD_CLEAR", node_id) in self._squad_inflight:
            return None
        node = self._find_node(data, node_id)
        if not node.get("hasObstacle"):
            return None
        if self._has_t04_for_obstacle(data, node_id):
            return None
        if not self._can_clear_node_soon(me, current_node, node_id):
            return None
        return node_id

    def _has_own_scout_mark(
        self,
        data: dict[str, Any],
        node_id: str,
        team_id: str,
    ) -> bool:
        node = self._find_node(data, node_id)
        for mark in node.get("scouted") or []:
            if mark.get("teamId") != team_id:
                continue
            if mark.get("remainingTriggers", 0) > 0 and mark.get("remainRound", 0) > 0:
                return True
        return False

    def _node_benefits_from_scout(
        self,
        data: dict[str, Any],
        node_id: str,
        current_node: str,
    ) -> bool:
        if node_id in self.process_attempted:
            return False
        if node_id == self.gate_node_id:
            s12_idx = self._route_index("S12")
            current_idx = self._route_index(current_node)
            return current_idx >= s12_idx >= 0
        if node_id in ROUTE_TASK_NODES and self._task_base_total < TASK_TARGET_BASE:
            return True
        node = self._find_node(data, node_id)
        process_type = node.get("processType")
        if not process_type or process_type == "VERIFY":
            return False
        process_round = int(node.get("processRound", 0) or 0)
        return process_round > 2

    def _squad_delay_rounds(self, data: dict[str, Any], current_node: str, target_node: str) -> int:
        current = self._find_node(data, current_node)
        target = self._find_node(data, target_node)
        dx = abs(float(current.get("x", 0)) - float(target.get("x", 0)))
        dy = abs(float(current.get("y", 0)) - float(target.get("y", 0)))
        distance = max(dx, dy)
        return min(15, max(3, math.ceil(distance / 3)))

    def _estimate_main_fleet_rounds_to_node(
        self,
        me: dict[str, Any],
        current_node: str,
        target_node: str,
    ) -> int:
        origin = current_node
        if me.get("state") == "MOVING":
            moving_from = me.get("currentNodeId")
            if moving_from:
                origin = moving_from
        path = shortest_weighted_path(self.weighted_adjacency, origin, target_node)
        if len(path) < 2:
            return 0
        total_weight = 0
        for idx in range(len(path) - 1):
            hop_from = path[idx]
            hop_to = path[idx + 1]
            for neighbor, weight in self.weighted_adjacency.get(hop_from, []):
                if neighbor == hop_to:
                    total_weight += weight
                    break
        return max(1, (total_weight + MOVE_WEIGHT_PER_ROUND - 1) // MOVE_WEIGHT_PER_ROUND)

    def _can_clear_node_soon(
        self,
        me: dict[str, Any],
        current_node: str,
        target_node: str,
    ) -> bool:
        arrival_rounds = self._estimate_main_fleet_rounds_to_node(me, current_node, target_node)
        return arrival_rounds <= CLEAR_NEAR_MAX_ROUNDS

    def _scout_mark_will_expire_before_use(
        self,
        data: dict[str, Any],
        me: dict[str, Any],
        current_node: str,
        target_node: str,
        current_round: Any,
    ) -> bool:
        if not isinstance(current_round, int):
            return True
        squad_delay = self._squad_delay_rounds(data, current_node, target_node)
        travel_rounds = self._estimate_main_fleet_rounds_to_node(me, current_node, target_node)
        mark_ready_round = current_round + squad_delay
        mark_last_usable_round = mark_ready_round + SCOUT_MARK_TTL
        arrival_round = current_round + travel_rounds
        return arrival_round > mark_last_usable_round

    @staticmethod
    def _find_opponent(data: dict[str, Any], player_id: int) -> Optional[dict[str, Any]]:
        for player in data.get("players") or []:
            if player.get("playerId") != player_id:
                return player
        return None

    @staticmethod
    def _progress_rank(player: dict[str, Any]) -> tuple[bool, bool, int, int]:
        node_id = player.get("currentNodeId") or ""
        try:
            idx = MAIN_ROUTE.index(node_id)
        except ValueError:
            idx = -1
        return (
            bool(player.get("delivered")),
            bool(player.get("verified")),
            idx,
            int(player.get("totalScore", 0) or 0),
        )

    def _route_position(self, player: dict[str, Any]) -> float:
        node_id = player.get("currentNodeId") or ""
        idx = self._route_index(node_id)
        if idx < 0:
            return -1.0
        state = player.get("state")
        next_node = player.get("nextNodeId") or ""
        progress = int(player.get("edgeProgressPermille") or 0)
        next_idx = self._route_index(next_node)
        if state in ("MOVING", "WAITING", "FORCED_PASSING") and next_idx == idx + 1:
            return idx + progress / 1000.0
        if state in ("MOVING", "WAITING", "FORCED_PASSING") and next_idx == idx - 1:
            return idx - progress / 1000.0
        return float(idx)

    def _hop_rounds(self, from_node: str, to_node: str) -> int:
        for neighbor, weight in self.weighted_adjacency.get(from_node, []):
            if neighbor == to_node:
                return max(1, (weight + MOVE_WEIGHT_PER_ROUND - 1) // MOVE_WEIGHT_PER_ROUND)
        return 9999

    def _estimate_hop_rounds(self, player: dict[str, Any]) -> int:
        edge_ms = int(player.get("edgeTotalMs") or 0)
        if edge_ms > 0 and player.get("state") in ("MOVING", "WAITING", "FORCED_PASSING"):
            return max(1, edge_ms // MOVE_WEIGHT_PER_ROUND)
        node_id = player.get("currentNodeId") or ""
        next_node = player.get("nextNodeId") or ""
        if next_node:
            hop = self._hop_rounds(node_id, next_node)
            if hop < 9999:
                return hop
        next_hop = self._next_main_route_hop(node_id)
        if next_hop:
            return self._hop_rounds(node_id, next_hop)
        return 9999

    def _route_lead_frames(
        self, data: dict[str, Any], player_id: int, guard_node_id: str
    ) -> int:
        me = self._find_player(data, player_id)
        opponent = self._find_opponent(data, player_id)
        if me is None or opponent is None:
            return 0
        my_pos = self._route_position(me)
        opp_pos = self._route_position(opponent)
        if my_pos < 0 or opp_pos < 0 or my_pos <= opp_pos + 1e-6:
            return 0
        hop_frames = self._estimate_hop_rounds(opponent)
        if hop_frames >= 9999:
            opp_node = opponent.get("currentNodeId") or ""
            hop_frames = self._hop_rounds(opp_node, guard_node_id)
            if hop_frames >= 9999:
                next_hop = self._next_main_route_hop(opp_node)
                hop_frames = self._hop_rounds(opp_node, next_hop) if next_hop else 1
        hop_frames = max(1, min(hop_frames, 9998))
        return max(0, int((my_pos - opp_pos) * hop_frames))

    def _travel_rounds_for_edge_weight(self, weight_ms: int) -> int:
        return max(1, math.ceil(weight_ms / EDGE_MS_PER_ROUND))

    def _sync_opponent_edge_tracking(
        self, data: dict[str, Any], player_id: int
    ) -> None:
        opponent = self._find_opponent(data, player_id)
        if opponent is None:
            return
        round_num = data.get("round")
        if not isinstance(round_num, int):
            return
        opp_id = int(opponent.get("playerId") or 0)
        from_node = opponent.get("currentNodeId") or ""
        to_node = opponent.get("nextNodeId") or ""
        state = opponent.get("state")
        if state in ("MOVING", "WAITING", "FORCED_PASSING") and to_node:
            progress = int(opponent.get("edgeProgressPermille") or 0)
            key = (opp_id, from_node, to_node)
            last_key = self._opp_active_edge_key.get(opp_id)
            if key != last_key:
                self._opp_edge_start_round[key] = round_num
                self._opp_active_edge_key[opp_id] = key
            elif progress < self._opp_edge_last_progress.get(key, progress):
                self._opp_edge_start_round[key] = round_num
            self._opp_edge_last_progress[key] = progress
        elif opp_id in self._opp_active_edge_key:
            del self._opp_active_edge_key[opp_id]

    def _opponent_edge_remaining_rounds(
        self, data: dict[str, Any], opponent: dict[str, Any]
    ) -> int:
        round_num = data.get("round")
        if not isinstance(round_num, int):
            return 1
        opp_id = int(opponent.get("playerId") or 0)
        from_node = opponent.get("currentNodeId") or ""
        to_node = opponent.get("nextNodeId") or ""
        progress = int(opponent.get("edgeProgressPermille") or 0)
        if progress >= 1000:
            return 0
        key = (opp_id, from_node, to_node)
        start = self._opp_edge_start_round.get(key)
        if start is not None and progress > 0:
            elapsed = max(1, round_num - start)
            return max(1, math.ceil(elapsed * (1000 - progress) / progress))
        edge_ms = int(opponent.get("edgeTotalMs") or 0)
        if edge_ms > 0:
            total = self._travel_rounds_for_edge_weight(edge_ms)
            return max(1, math.ceil(total * (1000 - progress) / 1000.0))
        hop = self._hop_rounds(from_node, to_node)
        if hop < 9999:
            return hop
        return 1

    def _opponent_final_approach_lead_frames(
        self,
        data: dict[str, Any],
        opponent: dict[str, Any],
        guard_node_id: str,
    ) -> int:
        if opponent.get("nextNodeId") != guard_node_id:
            return 0
        if opponent.get("state") not in ("MOVING", "WAITING", "FORCED_PASSING"):
            return 0
        return self._opponent_edge_remaining_rounds(data, opponent)

    def _guard_lead_frames(
        self, data: dict[str, Any], player_id: int, guard_node_id: str
    ) -> int:
        me = self._find_player(data, player_id)
        opponent = self._find_opponent(data, player_id)
        if me is None or opponent is None:
            return 0
        if not self._ahead_of_opponent(data, player_id):
            return 0
        route_lead = self._route_lead_frames(data, player_id, guard_node_id)
        my_node = me.get("currentNodeId") or ""
        if my_node != guard_node_id:
            return route_lead
        approach = self._opponent_final_approach_lead_frames(
            data, opponent, guard_node_id
        )
        if approach > 0:
            return max(route_lead, approach)
        return route_lead

    def _should_prioritize_guard_over_side_objectives(
        self,
        data: dict[str, Any],
        player_id: int,
        current_node: str,
    ) -> bool:
        if current_node not in GUARD_BEFORE_SIDE_NODES:
            return False
        me = self._find_player(data, player_id)
        team_id = me.get("teamId", "") if me is not None else ""
        if self._own_guard_active_at_node(data, team_id, current_node):
            return False
        if current_node in self._guard_set_nodes:
            return False
        if self._pending_set_guard == current_node:
            return True
        if data.get("phase") == "RUSH":
            return False
        return self._guard_will_affect_opponent(data, player_id, current_node)

    def _own_guard_active_at_node(
        self, data: dict[str, Any], team_id: str, node_id: str
    ) -> bool:
        node = self._find_node(data, node_id)
        guard = node.get("guard") or {}
        if not guard.get("active"):
            return False
        if guard.get("ownerTeamId") != team_id:
            return False
        return int(guard.get("defense", 0)) > 0

    def _hold_move_for_guard(
        self,
        data: dict[str, Any],
        me: dict[str, Any],
        player_id: int,
        current_node: str,
    ) -> bool:
        if me.get("state") not in ("IDLE", "WAITING"):
            return False
        if current_node not in GUARD_BEFORE_SIDE_NODES:
            return False
        team_id = me.get("teamId", "")
        if self._own_guard_active_at_node(data, team_id, current_node):
            return False
        if current_node in self._guard_set_nodes:
            return False
        if self._pending_set_guard == current_node:
            return True
        if data.get("phase") == "RUSH":
            return False
        return self._guard_will_affect_opponent(data, player_id, current_node)

    def _movement_speed_rank(self, player: dict[str, Any]) -> tuple[int, int, int]:
        resources = player.get("resources") or {}
        has_horse = (
            resources.get("FAST_HORSE", 0) > 0 or resources.get("SHORT_HORSE", 0) > 0
        )
        edge_ms = int(player.get("edgeTotalMs") or 0)
        edge_rounds = 9999
        if edge_ms > 0 and player.get("state") in ("MOVING", "WAITING", "FORCED_PASSING"):
            edge_rounds = max(1, edge_ms // MOVE_WEIGHT_PER_ROUND)
        else:
            node_id = player.get("currentNodeId") or ""
            next_node = player.get("nextNodeId") or self._next_main_route_hop(node_id)
            if node_id and next_node:
                edge_rounds = self._hop_rounds(node_id, next_node)
        return (int(self._has_move_buff(player)), int(has_horse), -edge_rounds)

    def _compare_route_progress(self, leader: dict[str, Any], trailer: dict[str, Any]) -> int:
        lead_pos = self._route_position(leader)
        trail_pos = self._route_position(trailer)
        if lead_pos > trail_pos + 1e-6:
            return 1
        if trail_pos > lead_pos + 1e-6:
            return -1
        if leader.get("currentNodeId") != trailer.get("currentNodeId"):
            lead_rank = self._progress_rank(leader)
            trail_rank = self._progress_rank(trailer)
            if lead_rank > trail_rank:
                return 1
            if trail_rank > lead_rank:
                return -1
            return 0

        lead_state = leader.get("state")
        if lead_state == "MOVING":
            return 1
        if lead_state == "WAITING":
            lead_progress = int(leader.get("edgeProgressPermille") or 0)
            trail_progress = int(trailer.get("edgeProgressPermille") or 0)
            if lead_progress > trail_progress:
                return 1
            if lead_progress < trail_progress:
                return -1
            lead_speed = self._movement_speed_rank(leader)
            trail_speed = self._movement_speed_rank(trailer)
            if lead_speed > trail_speed:
                return 1
            if trail_speed > lead_speed:
                return -1
            return 0
        return 0

    def _ahead_of_opponent(self, data: dict[str, Any], player_id: int) -> bool:
        me = self._find_player(data, player_id)
        opponent = self._find_opponent(data, player_id)
        if me is None or opponent is None:
            return False
        return self._compare_route_progress(me, opponent) > 0

    def _in_first_half(self, current_node: str, phase: str) -> bool:
        if phase == "RUSH":
            return False
        idx = self._route_index(current_node)
        half_idx = self._route_index(FIRST_HALF_PROGRESS_NODE)
        if idx < 0 or half_idx < 0:
            return False
        return idx <= half_idx

    def _defer_side_objectives_for_progress(
        self,
        data: dict[str, Any],
        player_id: int,
        phase: str,
        current_node: str,
    ) -> bool:
        if not self._in_first_half(current_node, phase):
            return False
        if not self._ahead_of_opponent(data, player_id):
            return True
        return self._guard_lead_frames(data, player_id, current_node) < MIN_GUARD_LEAD_FRAMES

    def _needs_urgent_ice_claim(self, me: dict[str, Any], phase: str) -> bool:
        threshold = (
            ICE_USE_LATE_FRESHNESS if phase == "RUSH" else ICE_USE_FRESHNESS
        )
        return float(me.get("freshness", 100)) < threshold

    def _opponent_within_guard_range(
        self,
        data: dict[str, Any],
        player_id: int,
        current_node: str,
    ) -> bool:
        opponent = self._find_opponent(data, player_id)
        if opponent is None:
            return False
        my_idx = self._route_index(current_node)
        opp_idx = self._route_index(opponent.get("currentNodeId") or "")
        if my_idx < 0 or opp_idx < 0:
            return False
        return opp_idx >= my_idx - 2

    def _own_active_guard_count(self, data: dict[str, Any], team_id: str) -> int:
        count = 0
        for node in data.get("nodes") or []:
            guard = node.get("guard") or {}
            if not guard.get("active"):
                continue
            if guard.get("ownerTeamId") != team_id:
                continue
            if int(guard.get("defense", 0)) <= 0:
                continue
            count += 1
        return count

    def _node_guard_blocks_set(
        self,
        data: dict[str, Any],
        node_id: str,
        team_id: str,
    ) -> bool:
        node = self._find_node(data, node_id)
        guard = node.get("guard") or {}
        if not guard.get("active"):
            return False
        if int(guard.get("defense", 0)) <= 0:
            return False
        owner = guard.get("ownerTeamId")
        return bool(owner)

    def _can_set_guard_at_node(self, node_id: str) -> bool:
        if node_id in GUARD_FORBIDDEN_NODES or node_id == self.terminal_node_id:
            return False
        return True

    def _opponent_on_same_main_route(
        self, data: dict[str, Any], player_id: int
    ) -> bool:
        opponent = self._find_opponent(data, player_id)
        if opponent is None:
            return False
        node_id = opponent.get("currentNodeId") or ""
        state = opponent.get("state")
        next_node = opponent.get("nextNodeId") or ""
        route_type = opponent.get("routeType") or ""

        if state in ("MOVING", "WAITING", "FORCED_PASSING") and next_node:
            if route_type in ("BRANCH", "WATER", "MOUNTAIN"):
                return False
            return (
                self._route_index(node_id) >= 0 or self._route_index(next_node) >= 0
            )
        return self._route_index(node_id) >= 0

    def _guard_will_affect_opponent(
        self, data: dict[str, Any], player_id: int, node_id: str
    ) -> bool:
        opponent = self._find_opponent(data, player_id)
        if opponent is None:
            return False
        if self._opponent_passed_route_node(opponent, node_id):
            return False
        if not self._ahead_of_opponent(data, player_id):
            return False
        if self._guard_lead_frames(data, player_id, node_id) < MIN_GUARD_LEAD_FRAMES:
            return False
        target_idx = self._route_index(node_id)
        if target_idx < 0:
            return False
        opp_pos = self._route_position(opponent)
        if opp_pos > target_idx + 1e-3:
            return False
        if self._opponent_within_guard_range(data, player_id, node_id):
            return True
        return opp_pos <= target_idx + 1e-3

    def _is_guard_checkpoint_node(self, data: dict[str, Any], node_id: str) -> bool:
        if node_id in GUARD_SET_ROUTE_NODES or node_id == self.gate_node_id:
            return True
        node = self._find_node(data, node_id)
        return node.get("nodeType") in ("KEY_PASS", "PASS")

    def _attempt_forced_pass(
        self, current_node: str, target: str
    ) -> Optional[dict[str, Any]]:
        break_key = (current_node, target)
        if break_key in self._failed_breaks:
            return None
        if self._pending_forced_pass == break_key:
            return None
        self._pending_forced_pass = break_key
        return {"action": "FORCED_PASS", "targetNodeId": target}

    def _guard_breakthrough_for_target(
        self,
        data: dict[str, Any],
        me: dict[str, Any],
        current_node: str,
        target_node: str,
        *,
        allow_forced_pass: bool = True,
    ) -> Optional[dict[str, Any]]:
        team_id = me.get("teamId", "")
        if not self._enemy_guard_blocks(data, target_node, team_id):
            return None

        defense = self._guard_defense(data, target_node, team_id)
        if defense <= 1:
            return None

        break_key = (current_node, target_node)
        if break_key not in self._failed_breaks:
            good_fruit, bad_fruit = self._plan_break_investment(me, defense)
            if good_fruit > 0 or bad_fruit > 0:
                action: dict[str, Any] = {
                    "action": "BREAK_GUARD",
                    "targetNodeId": target_node,
                }
                if good_fruit > 0:
                    action["goodFruit"] = good_fruit
                if bad_fruit > 0:
                    action["badFruit"] = bad_fruit
                return action

        if not allow_forced_pass:
            return None

        if break_key in self._failed_breaks:
            return {"action": "FORCED_PASS", "targetNodeId": target_node}

        return self._attempt_forced_pass(current_node, target_node)

    @staticmethod
    def _guard_set_base_cost(node: dict[str, Any], gate_node_id: str) -> int:
        node_id = node.get("nodeId", "")
        if node_id == gate_node_id:
            return 1
        if node.get("nodeType") == "KEY_PASS":
            return 1
        return 0

    def _plan_guard_extra_fruit(self, me: dict[str, Any], node: dict[str, Any]) -> int:
        available = int(me.get("goodFruit", 0))
        base_cost = self._guard_set_base_cost(node, self.gate_node_id)
        reserve = 20
        spendable = max(0, available - base_cost - reserve)
        if node.get("nodeType") == "KEY_PASS" and spendable >= 1:
            return 1
        if spendable >= 2:
            return 2
        if spendable >= 1:
            return 1
        return 0

    def _set_guard_action(
        self,
        data: dict[str, Any],
        me: dict[str, Any],
        player_id: int,
        current_node: str,
        node: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        if not self._can_set_guard_at_node(current_node):
            return None
        if data.get("phase") == "RUSH":
            return None
        if me.get("state") not in ("IDLE", "WAITING"):
            return None
        if not self._opponent_on_same_main_route(data, player_id):
            return None
        if not self._guard_will_affect_opponent(data, player_id, current_node):
            return None
        team_id = me.get("teamId", "")
        if current_node in self._guard_set_nodes or self._pending_set_guard == current_node:
            return None
        if self._node_guard_blocks_set(data, current_node, team_id):
            return None
        if self._own_active_guard_count(data, team_id) >= MAX_OWN_GUARDS:
            return None
        base_cost = self._guard_set_base_cost(node, self.gate_node_id)
        extra_good_fruit = self._plan_guard_extra_fruit(me, node)
        if int(me.get("goodFruit", 0)) < base_cost + extra_good_fruit:
            return None
        self._pending_set_guard = current_node
        action: dict[str, Any] = {
            "action": "SET_GUARD",
            "targetNodeId": current_node,
        }
        if extra_good_fruit > 0:
            action["extraGoodFruit"] = extra_good_fruit
        return action

    def _sync_guard_set_feedback(self, data: dict[str, Any], player_id: int) -> None:
        for event in self._round_events(data):
            if event.get("type") != "GUARD_SET":
                continue
            payload = event.get("payload") or {}
            if payload.get("playerId") != player_id:
                continue
            node_id = payload.get("targetNodeId") or payload.get("nodeId")
            if node_id:
                self._guard_set_nodes.add(node_id)
                if self._pending_set_guard == node_id:
                    self._pending_set_guard = None

        if self._pending_set_guard is None:
            return
        for result in data.get("actionResults") or []:
            if result.get("playerId") != player_id:
                continue
            if result.get("action") != "SET_GUARD":
                continue
            if not result.get("accepted"):
                self._pending_set_guard = None
            break

    def _block_task_claim(self, task_id: Optional[str]) -> None:
        if task_id:
            self._blocked_task_ids.add(task_id)

    def _sync_task_feedback(self, data: dict[str, Any], player_id: int) -> None:
        for event in self._round_events(data):
            event_type = event.get("type")
            payload = event.get("payload") or {}
            if event_type == "TASK_COMPLETE":
                task_id = payload.get("taskId")
                if task_id:
                    self._completed_task_ids.add(task_id)
                    self._blocked_task_ids.discard(task_id)
                if payload.get("playerId") == player_id:
                    score = payload.get("score", 0)
                    if isinstance(score, (int, float)):
                        self._task_base_total += int(score)
                continue
            if event_type != "ACTION_REJECTED":
                continue
            if payload.get("playerId") != player_id:
                continue
            if payload.get("action") == "CLAIM_TASK":
                self._block_task_claim(payload.get("taskId") or self._pending_task_claim)

        for result in data.get("actionResults") or []:
            if result.get("playerId") != player_id:
                continue
            if result.get("action") != "CLAIM_TASK":
                continue
            task_id = result.get("taskId") or self._pending_task_claim
            if result.get("accepted"):
                if task_id:
                    self._blocked_task_ids.discard(task_id)
            else:
                self._block_task_claim(task_id)
            self._pending_task_claim = None
            break

    def _task_action(
        self,
        data: dict[str, Any],
        current_node: str,
        node: dict[str, Any],
        player_id: int,
    ) -> Optional[dict[str, Any]]:
        round_num = data.get("round", 0)
        if round_num > TASK_CLAIM_DEADLINE:
            return None
        task_cap = TASK_TARGET_STRETCH
        if round_num > 450 and self._task_base_total >= TASK_TARGET_BASE:
            task_cap = TASK_TARGET_BASE
        if self._task_base_total >= task_cap:
            return None
        if current_node not in ROUTE_TASK_NODES:
            return None
        if self._needs_process(node, current_node):
            return None
        me = self._find_player(data, player_id)
        if me is None:
            return None
        task_action = self._best_claimable_task(data, me, current_node, player_id)
        if task_action is not None:
            self._pending_task_claim = task_action.get("taskId")
        return task_action

    def _best_claimable_task(
        self,
        data: dict[str, Any],
        me: dict[str, Any],
        current_node: str,
        player_id: int,
    ) -> Optional[dict[str, Any]]:
        best: Optional[dict[str, Any]] = None
        best_score = -1
        for task in data.get("tasks") or []:
            if not self._is_task_claimable(data, me, current_node, player_id, task):
                continue
            task_id = task.get("taskId")
            task_node = task.get("nodeId")
            score = int(task.get("score", 0))
            if task_node == current_node:
                score += 1000
            if score > best_score:
                best_score = score
                best = {"action": "CLAIM_TASK", "taskId": task_id}
        return best

    def _is_task_claimable(
        self,
        data: dict[str, Any],
        me: dict[str, Any],
        current_node: str,
        player_id: int,
        task: dict[str, Any],
    ) -> bool:
        task_id = task.get("taskId")
        if not task_id or task_id in self._completed_task_ids or task_id in self._blocked_task_ids:
            return False
        if not task.get("active") or task.get("completed") or task.get("failed"):
            return False

        round_num = data.get("round", 0)
        expire_round = int(task.get("expireRound") or 0)
        if expire_round > 0 and isinstance(round_num, int) and round_num > expire_round:
            return False

        owner_id = int(task.get("ownerPlayerId") or 0)
        if owner_id not in (0, player_id):
            return False

        protection_id = int(task.get("protectionPlayerId") or 0)
        if protection_id not in (0, player_id):
            return False

        if self._task_under_contest(data, task_id):
            return False

        task_node = task.get("nodeId")
        if not task_node or not self._can_claim_task(data, current_node, task):
            return False
        if self._window_process_suppressed(data, task_node):
            return False
        if task_node != current_node and self._opponent_at_task_node(
            data, player_id, task_node
        ):
            return False
        if self._is_remote_t04_task(task, current_node) and self._opponent_at_same_node(
            data, player_id, current_node
        ):
            return False
        if task_node == current_node and self._opponent_processing_task_at_node(
            data, player_id, current_node, task_id
        ):
            return False
        if self._is_t06_task(task) and not self._has_mount_for_t06(me):
            return False
        return True

    @staticmethod
    def _is_t06_task(task: dict[str, Any]) -> bool:
        template = str(task.get("taskTemplateId") or task.get("templateId") or "")
        return template.startswith("T06")

    @staticmethod
    def _has_mount_for_t06(me: dict[str, Any]) -> bool:
        resources = me.get("resources") or {}
        return resources.get("FAST_HORSE", 0) > 0 or resources.get("SHORT_HORSE", 0) > 0

    def _task_under_contest(self, data: dict[str, Any], task_id: str) -> bool:
        for contest in data.get("contests") or []:
            if contest.get("contestType") != "TASK":
                continue
            if contest.get("taskId") != task_id:
                continue
            if contest.get("resolved") or contest.get("status") == "SUPPRESSED":
                continue
            return True
        return False

    def _opponent_processing_task_at_node(
        self,
        data: dict[str, Any],
        player_id: int,
        node_id: str,
        task_id: str,
    ) -> bool:
        for player in data.get("players") or []:
            if player.get("playerId") == player_id:
                continue
            if player.get("currentNodeId") != node_id:
                continue
            if player.get("state") != "PROCESSING":
                continue
            current_process = player.get("currentProcess") or {}
            if current_process.get("action") != "CLAIM_TASK":
                continue
            processing_task = current_process.get("taskId")
            if processing_task in (None, "", task_id):
                return True
        return False

    @staticmethod
    def _is_remote_t04_task(task: dict[str, Any], current_node: str) -> bool:
        task_node = task.get("nodeId")
        if not task_node or task_node == current_node:
            return False
        template = str(task.get("taskTemplateId") or task.get("templateId") or "")
        return template.startswith("T04")

    def _opponent_at_same_node(
        self, data: dict[str, Any], player_id: int, node_id: str
    ) -> bool:
        for player in data.get("players") or []:
            if player.get("playerId") == player_id:
                continue
            if player.get("currentNodeId") != node_id:
                continue
            if player.get("state") in (
                "IDLE",
                "WAITING",
                "PROCESSING",
                "CONTESTING",
                "RESTING",
            ):
                return True
        return False

    def _opponent_at_task_node(
        self, data: dict[str, Any], player_id: int, task_node: str
    ) -> bool:
        for player in data.get("players") or []:
            if player.get("playerId") == player_id:
                continue
            if player.get("currentNodeId") != task_node:
                continue
            if player.get("state") in (
                "IDLE",
                "WAITING",
                "PROCESSING",
                "CONTESTING",
            ):
                return True
        return False

    def _can_claim_task(
        self,
        data: dict[str, Any],
        current_node: str,
        task: dict[str, Any],
    ) -> bool:
        task_node = task.get("nodeId")
        if task_node == current_node:
            return True
        template = str(task.get("taskTemplateId") or task.get("templateId") or "")
        if not template.startswith("T04"):
            return False
        if task_node not in self.adjacency.get(current_node, []):
            return False
        obstacle_node = self._find_node(data, task_node)
        return bool(obstacle_node.get("hasObstacle"))

    def _has_t04_for_obstacle(self, data: dict[str, Any], obstacle_node_id: str) -> bool:
        for task in data.get("tasks") or []:
            task_id = task.get("taskId")
            if not task_id or task_id in self._completed_task_ids:
                continue
            if task.get("nodeId") != obstacle_node_id:
                continue
            if not task.get("active") or task.get("completed") or task.get("failed"):
                continue
            template = str(task.get("taskTemplateId") or task.get("templateId") or "")
            if template.startswith("T04"):
                return True
        return False

    def _claim_resource_action(self, node: dict[str, Any], current_node: str) -> Optional[dict[str, Any]]:
        if current_node in self._resource_claimed_nodes:
            return None
        stock = node.get("resourceStock") or {}

        if current_node in ICE_CLAIM_NODES and stock.get("ICE_BOX", 0) > 0:
            self._resource_claimed_nodes.add(current_node)
            return {
                "action": "CLAIM_RESOURCE",
                "targetNodeId": current_node,
                "resourceType": "ICE_BOX",
            }

        if current_node in HORSE_CLAIM_NODES and stock.get("FAST_HORSE", 0) > 0:
            self._resource_claimed_nodes.add(current_node)
            return {
                "action": "CLAIM_RESOURCE",
                "targetNodeId": current_node,
                "resourceType": "FAST_HORSE",
            }

        if current_node in HORSE_CLAIM_NODES and stock.get("SHORT_HORSE", 0) > 0:
            self._resource_claimed_nodes.add(current_node)
            return {
                "action": "CLAIM_RESOURCE",
                "targetNodeId": current_node,
                "resourceType": "SHORT_HORSE",
            }
        return None

    def _use_resource_action(
        self,
        me: dict[str, Any],
        current_node: str,
        phase: str,
    ) -> Optional[dict[str, Any]]:
        resources = me.get("resources") or {}
        freshness = me.get("freshness", 100)

        if resources.get("ICE_BOX", 0) > 0 and self._should_use_ice(me, current_node, phase, freshness):
            return {"action": "USE_RESOURCE", "resourceType": "ICE_BOX"}

        if self._has_move_buff(me):
            return None

        if phase == "RUSH":
            return None

        if current_node in HORSE_USE_NODES:
            if resources.get("FAST_HORSE", 0) > 0:
                return {"action": "USE_RESOURCE", "resourceType": "FAST_HORSE"}
            if resources.get("SHORT_HORSE", 0) > 0:
                return {"action": "USE_RESOURCE", "resourceType": "SHORT_HORSE"}
        return None

    def _should_use_ice(
        self,
        me: dict[str, Any],
        current_node: str,
        phase: str,
        freshness: float,
    ) -> bool:
        if freshness <= 0:
            return False
        if freshness >= ICE_USE_LATE_FRESHNESS:
            return False
        current_idx = self._route_index(current_node)
        s07_idx = self._route_index("S07")
        if current_idx >= s07_idx >= 0 or phase == "RUSH":
            return freshness < ICE_USE_LATE_FRESHNESS
        return freshness < ICE_USE_FRESHNESS

    def _rush_protect_action(
        self,
        me: dict[str, Any],
        phase: str,
        current_node: str,
    ) -> Optional[dict[str, Any]]:
        if phase != "RUSH":
            return None
        if me.get("rushTacticUsedCount", 0) > 0:
            return None
        if not me.get("verified") and current_node == "S13":
            return None
        if current_node == self.gate_node_id:
            return None
        if current_node not in RUSH_PROTECT_NODES:
            return None
        return {"action": "RUSH_PROTECT"}

    def _edge_guard_response(
        self,
        data: dict[str, Any],
        me: dict[str, Any],
        phase: str,
        current_node: str,
    ) -> Optional[dict[str, Any]]:
        next_node = me.get("nextNodeId")
        if not next_node:
            return None
        team_id = me.get("teamId", "")
        if not self._enemy_guard_blocks(data, next_node, team_id):
            self._edge_guard_waits.pop((current_node, next_node), None)
            return None

        edge_key = (current_node, next_node)
        waits = self._edge_guard_waits.get(edge_key, 0) + 1
        self._edge_guard_waits[edge_key] = waits

        defense = self._guard_defense(data, next_node, team_id)
        if defense <= 1:
            return None

        if ("SQUAD_WEAKEN", next_node) in self._squad_inflight and waits <= 2:
            return {"action": "WAIT"}

        breakthrough = self._guard_breakthrough_for_target(
            data,
            me,
            current_node,
            next_node,
            allow_forced_pass=False,
        )
        if breakthrough is not None:
            return breakthrough

        return {"action": "WAIT"}

    def _opponent_passed_route_node(self, opponent: dict[str, Any], node_id: str) -> bool:
        target_idx = self._route_index(node_id)
        opp_idx = self._route_index(opponent.get("currentNodeId") or "")
        if target_idx < 0 or opp_idx < 0:
            return False
        return opp_idx > target_idx

    def _guard_hold_action(
        self,
        data: dict[str, Any],
        me: dict[str, Any],
        player_id: int,
        current_node: str,
    ) -> Optional[dict[str, Any]]:
        if current_node not in GUARD_HOLD_NODES:
            self._guard_hold_rounds.pop(current_node, None)
            return None

        next_hop = self._next_main_route_hop(current_node)
        if not next_hop:
            self._guard_hold_rounds.pop(current_node, None)
            return None

        team_id = me.get("teamId", "")
        if self._enemy_guard_blocks(data, next_hop, team_id):
            self._guard_hold_rounds.pop(current_node, None)
            return None

        if self._ahead_of_opponent(data, player_id):
            self._guard_hold_rounds.pop(current_node, None)
            return None

        opponent = self._find_opponent(data, player_id)
        if opponent is None:
            self._guard_hold_rounds.pop(current_node, None)
            return None

        if self._opponent_passed_route_node(opponent, next_hop):
            self._guard_hold_rounds.pop(current_node, None)
            return None

        if not self._opponent_ahead_on_route(data, player_id):
            self._guard_hold_rounds.pop(current_node, None)
            return None

        hold_rounds = self._guard_hold_rounds.get(current_node, 0) + 1
        self._guard_hold_rounds[current_node] = hold_rounds
        if hold_rounds > GUARD_HOLD_MAX_ROUNDS:
            self._guard_hold_rounds.pop(current_node, None)
            return None
        return {"action": "WAIT"}

    def _opponent_ahead_on_route(self, data: dict[str, Any], player_id: int) -> bool:
        me = self._find_player(data, player_id)
        opponent = self._find_opponent(data, player_id)
        if me is None or opponent is None:
            return False
        return self._compare_route_progress(opponent, me) > 0

    def _next_main_route_hop(self, current_node: str) -> Optional[str]:
        idx = self._route_index(current_node)
        if idx < 0 or idx + 1 >= len(MAIN_ROUTE):
            return None
        return MAIN_ROUTE[idx + 1]

    def _guard_breakthrough_action(
        self,
        data: dict[str, Any],
        me: dict[str, Any],
        current_node: str,
        goal: str,
    ) -> Optional[dict[str, Any]]:
        team_id = me.get("teamId", "")
        targets: list[tuple[int, str]] = []

        path = shortest_weighted_path(self.weighted_adjacency, current_node, goal)
        if len(path) >= 2:
            hop = path[1]
            if hop in self.adjacency.get(current_node, []):
                if self._enemy_guard_blocks(data, hop, team_id):
                    targets.append((self._guard_defense(data, hop, team_id), hop))

        for neighbor in self.adjacency.get(current_node, []):
            if not self._is_forward_progress(current_node, neighbor, goal):
                continue
            if not self._enemy_guard_blocks(data, neighbor, team_id):
                continue
            entry = (self._guard_defense(data, neighbor, team_id), neighbor)
            if entry not in targets:
                targets.append(entry)

        if not targets:
            return None

        targets.sort(key=lambda item: (item[0], item[1]))
        _, target = targets[0]
        return self._guard_breakthrough_for_target(data, me, current_node, target)

    @staticmethod
    def _plan_break_investment(me: dict[str, Any], defense: int) -> tuple[int, int]:
        available_good = min(3, int(me.get("goodFruit", 0)))
        available_bad = min(3, int(me.get("badFruit", 0)))
        best: Optional[tuple[int, int]] = None
        best_rank: Optional[tuple[int, int]] = None

        for good_fruit in range(available_good + 1):
            for bad_fruit in range(available_bad + 1):
                if good_fruit == 0 and bad_fruit == 0:
                    continue
                if good_fruit * 2 + bad_fruit * 3 < defense:
                    continue
                rank = (good_fruit, bad_fruit)
                if best_rank is None or rank < best_rank:
                    best = (good_fruit, bad_fruit)
                    best_rank = rank

        if best is not None:
            return best
        if available_good > 0:
            return available_good, min(available_bad, 3)
        if available_bad > 0:
            return 0, available_bad
        return 0, 0

    def _guard_defense(self, data: dict[str, Any], node_id: str, team_id: str) -> int:
        node = self._find_node(data, node_id)
        guard = node.get("guard") or {}
        if not guard.get("active"):
            return 0
        owner = guard.get("ownerTeamId")
        if owner and owner != team_id:
            return int(guard.get("defense", 0))
        return 0

    def _enemy_guard_blocks(self, data: dict[str, Any], node_id: str, team_id: str) -> bool:
        return self._guard_defense(data, node_id, team_id) > 0

    def _clear_action(
        self,
        data: dict[str, Any],
        me: dict[str, Any],
        current_node: str,
        goal: str,
    ) -> Optional[dict[str, Any]]:
        if me.get("goodFruit", 0) < 1:
            return None
        path = shortest_weighted_path(self.weighted_adjacency, current_node, goal)
        if len(path) < 2:
            return None
        target = path[1]
        if self._is_backtrack(current_node, target):
            target = self._best_forward_neighbor(data, me, current_node, goal)
            if target is None:
                return None
        node = self._find_node(data, target)
        if not node.get("hasObstacle"):
            return None
        if self._has_t04_for_obstacle(data, target):
            return None
        if not self._can_clear_node_soon(me, current_node, target):
            return None
        clear_key = (current_node, target)
        if clear_key in self._failed_clears:
            return None
        self._pending_clear = clear_key
        return {"action": "CLEAR", "targetNodeId": target}

    def _escape_process_node_action(
        self,
        data: dict[str, Any],
        me: dict[str, Any],
        player_id: int,
        phase: str,
        current_node: str,
        node: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        if not node.get("processRound", 0):
            return None
        should_escape = self._window_process_suppressed(data, current_node)
        if not should_escape:
            return None
        goal = self._goal(me, phase, data, current_node)
        if not goal or current_node == goal:
            return None
        target = self._pick_move_target(
            data, me, current_node, goal, ignore_failed=True
        )
        if target is None:
            target = self._next_route_neighbor(current_node, ignore_failed=True)
        if target is None:
            return None
        self._pending_move = (current_node, target)
        return {"action": "MOVE", "targetNodeId": target}

    def _next_route_neighbor(
        self, current_node: str, *, ignore_failed: bool = False
    ) -> Optional[str]:
        idx = self._route_index(current_node)
        if idx < 0:
            return None
        for next_node in MAIN_ROUTE[idx + 1 :]:
            if next_node not in self.adjacency.get(current_node, []):
                continue
            move_key = (current_node, next_node)
            if ignore_failed or move_key not in self._failed_moves:
                return next_node
        return None

    def _pick_move_target(
        self,
        data: dict[str, Any],
        me: dict[str, Any],
        current_node: str,
        goal: str,
        *,
        ignore_failed: bool = False,
    ) -> Optional[str]:
        team_id = me.get("teamId", "")
        main_hop = self._next_main_route_hop(current_node)
        if main_hop and main_hop in self.adjacency.get(current_node, []):
            move_key = (current_node, main_hop)
            if (
                ignore_failed or move_key not in self._failed_moves
            ) and not self._is_move_blocked(data, main_hop, team_id):
                return main_hop

        path = shortest_weighted_path(self.weighted_adjacency, current_node, goal)
        if len(path) >= 2:
            target = path[1]
            if self._is_forward_progress(current_node, target, goal):
                move_key = (current_node, target)
                team_id = me.get("teamId", "")
                if (
                    ignore_failed or move_key not in self._failed_moves
                ) and not self._is_move_blocked(data, target, team_id):
                    return target

        forward = self._best_forward_neighbor(
            data, me, current_node, goal, ignore_failed=ignore_failed
        )
        if forward is not None:
            return forward

        neighbors = self.adjacency.get(current_node, [])
        if not neighbors:
            return None

        team_id = me.get("teamId", "")
        ranked: list[tuple[int, str]] = []
        for neighbor in neighbors:
            if not self._is_forward_progress(current_node, neighbor, goal):
                continue
            move_key = (current_node, neighbor)
            if not ignore_failed and move_key in self._failed_moves:
                continue
            if self._is_move_blocked(data, neighbor, team_id):
                continue
            sub_path = shortest_weighted_path(self.weighted_adjacency, neighbor, goal)
            if not sub_path:
                continue
            ranked.append((len(sub_path), neighbor))

        if not ranked:
            return None

        ranked.sort(key=lambda item: (item[0], item[1]))
        return ranked[0][1]

    def _best_forward_neighbor(
        self,
        data: dict[str, Any],
        me: dict[str, Any],
        current_node: str,
        goal: str,
        *,
        ignore_failed: bool = False,
    ) -> Optional[str]:
        team_id = me.get("teamId", "")
        ranked: list[tuple[int, str]] = []
        for neighbor in self.adjacency.get(current_node, []):
            if not self._is_forward_progress(current_node, neighbor, goal):
                continue
            move_key = (current_node, neighbor)
            if not ignore_failed and move_key in self._failed_moves:
                continue
            if self._is_move_blocked(data, neighbor, team_id):
                continue
            sub_path = shortest_weighted_path(self.weighted_adjacency, neighbor, goal)
            if not sub_path:
                continue
            ranked.append((len(sub_path), neighbor))
        if not ranked:
            return None
        ranked.sort(key=lambda item: (item[0], item[1]))
        return ranked[0][1]

    def _is_forward_progress(self, current_node: str, target_node: str, goal: str) -> bool:
        if self._is_backtrack(current_node, target_node):
            return False
        current_idx = self._route_index(current_node)
        target_idx = self._route_index(target_node)
        if current_idx >= 0 and target_idx < 0:
            return False
        if current_idx >= 0 and target_idx >= 0:
            return target_idx > current_idx
        current_path = shortest_weighted_path(self.weighted_adjacency, current_node, goal)
        target_path = shortest_weighted_path(self.weighted_adjacency, target_node, goal)
        if not current_path or not target_path:
            return False
        return len(target_path) < len(current_path)

    def _route_index(self, node_id: str) -> int:
        try:
            return MAIN_ROUTE.index(node_id)
        except ValueError:
            return -1

    def _is_backtrack(self, current_node: str, target_node: str) -> bool:
        current_idx = self._route_index(current_node)
        target_idx = self._route_index(target_node)
        if current_idx < 0 or target_idx < 0:
            return False
        return target_idx < current_idx

    def _is_move_blocked(self, data: dict[str, Any], target_node: str, team_id: str) -> bool:
        node = self._find_node(data, target_node)
        if node.get("hasObstacle"):
            return True
        guard = node.get("guard") or {}
        if not guard.get("active"):
            return False
        owner = guard.get("ownerTeamId")
        defense = guard.get("defense", 0)
        return bool(owner and owner != team_id and defense > 0)

    def _goal(
        self,
        me: dict[str, Any],
        phase: str,
        data: dict[str, Any],
        current_node: str,
    ) -> Optional[str]:
        if me.get("verified"):
            return self.terminal_node_id
        return self.gate_node_id

    def _next_ice_stop(self, data: dict[str, Any], current_node: str) -> Optional[str]:
        current_idx = self._route_index(current_node)
        for node_id in ICE_STOPS:
            if node_id in self._ice_depleted_nodes:
                continue
            stop_idx = self._route_index(node_id)
            if stop_idx < 0:
                continue
            if current_idx > stop_idx:
                continue
            node = self._find_node(data, node_id)
            stock = node.get("resourceStock") or {}
            if stock.get("ICE_BOX", 0) > 0:
                return node_id
            self._ice_depleted_nodes.add(node_id)
        return None

    def _opponent_competing_for_process(
        self, data: dict[str, Any], player_id: int, current_node: str
    ) -> bool:
        for player in data.get("players") or []:
            if player.get("playerId") == player_id:
                continue
            if player.get("currentNodeId") != current_node:
                continue
            if player.get("state") in ("PROCESSING", "CONTESTING"):
                return True
        return False

    def _opponent_at_process_node(
        self, data: dict[str, Any], player_id: int, current_node: str
    ) -> bool:
        for player in data.get("players") or []:
            if player.get("playerId") == player_id:
                continue
            if player.get("currentNodeId") != current_node:
                continue
            if player.get("state") in (
                "IDLE",
                "WAITING",
                "CONTESTING",
                "RESTING",
                "PROCESSING",
            ):
                return True
        return False

    def _opponent_processing_blocks_process(
        self,
        data: dict[str, Any],
        player_id: int,
        current_node: str,
    ) -> bool:
        """Task book §5.4.1: processing already started blocks later PROCESS at same node."""
        for player in data.get("players") or []:
            if player.get("playerId") == player_id:
                continue
            if player.get("currentNodeId") != current_node:
                continue
            if player.get("state") == "PROCESSING":
                return True
        return False

    def _window_process_suppressed(self, data: dict[str, Any], node_id: str) -> bool:
        current_round = data.get("round")
        suppress_until = self._window_suppressed_nodes.get(node_id)
        if isinstance(current_round, int) and isinstance(suppress_until, int):
            if current_round <= suppress_until:
                return True

        for contest in data.get("contests") or []:
            if contest.get("status") != "SUPPRESSED":
                continue
            if contest.get("targetNodeId") != node_id:
                continue
            until = contest.get("suppressUntilRound")
            if isinstance(current_round, int) and isinstance(until, int):
                if current_round <= until:
                    return True
        return False

    def _needs_process(self, node: dict[str, Any], current_node: str) -> bool:
        if current_node in SKIP_PROCESS_NODES:
            return False
        if current_node in self.process_attempted:
            return False
        if current_node in self._process_started_nodes:
            return False
        process_type = node.get("processType")
        if not process_type:
            return False
        if process_type == "VERIFY":
            return False
        return bool(node.get("processRound", 0))

    def _can_deliver(self, me: dict[str, Any]) -> bool:
        return me.get("goodFruit", 0) > 0 and me.get("freshness", 0) > 0

    @staticmethod
    def _has_move_buff(me: dict[str, Any]) -> bool:
        for buff in me.get("buffs") or []:
            if buff.get("type") in ("FAST_HORSE", "SHORT_HORSE", "RUSH_SPEED"):
                if buff.get("remainingRound", 0) > 0:
                    return True
        return False

    @staticmethod
    def _find_player(data: dict[str, Any], player_id: int) -> Optional[dict[str, Any]]:
        for player in data.get("players") or []:
            if player.get("playerId") == player_id:
                return player
        return None

    def _find_node(self, data: dict[str, Any], node_id: str) -> dict[str, Any]:
        merged = dict(self._node_catalog.get(node_id, {}))
        for node in data.get("nodes") or []:
            if node.get("nodeId") == node_id:
                merged.update(node)
                self._node_catalog[node_id] = merged
                return merged
        if not merged.get("processType") and node_id in ROUTE_PROCESS_NODES:
            merged.update(ROUTE_PROCESS_NODES[node_id])
        return merged
