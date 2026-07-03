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

TASK_TARGET_MIN = 90
TASK_TARGET_STRETCH = 120
TASK_CLAIM_DEADLINE = 520
MAIN_ROUTE = ("S01", "S02", "S03", "S07", "S09", "S10", "S11", "S12", "S13", "S14", "S15")
ROUTE_TASK_NODES = frozenset({"S03", "S07", "S09", "S10", "S11", "S13"})
ICE_CLAIM_NODES = frozenset({"S03", "S07"})
HORSE_CLAIM_NODES = frozenset({"S09"})
HORSE_USE_NODES = frozenset({"S07", "S09", "S10", "S11", "S12", "S13"})
RUSH_PROTECT_NODES = frozenset({"S13"})
GUARD_CHOKE_NODES = frozenset({"S10", "S11"})
SCOUT_OPENING_NODE = "S10"
SCOUT_LATE_NODES = ("S13", "S14")
SQUAD_CLEAR_NODES = frozenset({"S11"})
SQUAD_CLEAR_MIN_ROUND = 240
SQUAD_TACTICS_MAX_ROUND = 385
EDGE_GUARD_WAIT_MAX = 8
NON_BLACKLIST_MOVE_ERRORS = frozenset(
    {
        "PROCESS_REQUIRED",
        "MOVE_BLOCKED_BY_GUARD",
        "OBJECT_BUSY",
        "MOVING_ACTION_FORBIDDEN",
    }
)
ICE_USE_FRESHNESS = 92.0
ICE_USE_LATE_FRESHNESS = 95.0


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
        self._task_base_total = 0
        self._edge_guard_waits: dict[tuple[str, str], int] = {}
        self._scouted_targets: set[str] = set()
        self._squad_clear_targets: set[str] = set()

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
        self._task_base_total = 0
        self._edge_guard_waits.clear()
        self._scouted_targets.clear()
        self._squad_clear_targets.clear()

    def decide(self, data: dict[str, Any], player_id: int) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        me = self._find_player(data, player_id)
        phase = data.get("phase", "NORMAL")

        if me is not None:
            self._sync_squad_feedback(data, player_id)
            squad_action = self._squad_action(data, me, phase)
            if squad_action is not None:
                actions.append(squad_action)

        window_action = self._window_action(data, player_id)
        if window_action is not None:
            actions.append(window_action)

        main_action = self._main_action(data, player_id)
        if main_action is not None:
            actions.append(main_action)

        return actions

    def _window_action(self, data: dict[str, Any], player_id: int) -> Optional[dict[str, Any]]:
        for contest in data.get("contests") or []:
            if contest.get("resolved"):
                continue
            if contest.get("status") == "SUPPRESSED":
                continue
            participants = {contest.get("redPlayerId"), contest.get("bluePlayerId")}
            if player_id not in participants:
                continue
            contest_id = contest.get("contestId")
            if not contest_id:
                continue
            return {
                "action": "WINDOW_CARD",
                "contestId": contest_id,
                "card": "ABSTAIN",
            }
        return None

    def _main_action(self, data: dict[str, Any], player_id: int) -> Optional[dict[str, Any]]:
        me = self._find_player(data, player_id)
        if me is None:
            return None

        self._sync_move_feedback(data, player_id)
        self._sync_clear_feedback(data, player_id)
        self._sync_break_feedback(data, player_id)
        self._sync_process_feedback(data, player_id)
        self._sync_task_feedback(data, player_id)

        state = me.get("state", "IDLE")
        if state in WAIT_STATES and state not in ("MOVING", "WAITING"):
            return {"action": "WAIT"}
        if me.get("delivered") or me.get("retired"):
            return None

        current_node = me.get("currentNodeId")
        if not current_node:
            return None

        if self._last_node_id and self._last_node_id != current_node:
            self.process_attempted.discard(self._last_node_id)
        self._last_node_id = current_node

        phase = data.get("phase", "NORMAL")

        if state == "MOVING":
            edge_action = self._edge_guard_response(data, me, phase, current_node)
            if edge_action is not None:
                return edge_action
            next_node = me.get("nextNodeId")
            if next_node:
                return {"action": "MOVE", "targetNodeId": next_node}
            return None

        if state == "WAITING":
            edge_action = self._edge_guard_response(data, me, phase, current_node)
            if edge_action is not None:
                return edge_action
            next_node = me.get("nextNodeId")
            if next_node:
                return {"action": "MOVE", "targetNodeId": next_node}
            node = self._find_node(data, current_node)
            if self._needs_process(node, current_node):
                self._pending_process = current_node
                return {"action": "PROCESS", "targetNodeId": current_node}
            if (
                phase == "RUSH"
                and not me.get("verified")
                and current_node == self.gate_node_id
            ):
                return {"action": "VERIFY_GATE", "targetNodeId": self.gate_node_id}
            if me.get("verified") and current_node == self.gate_node_id:
                return {"action": "MOVE", "targetNodeId": self.terminal_node_id}

        node = self._find_node(data, current_node)

        if current_node == self.terminal_node_id:
            if me.get("verified") and self._can_deliver(me):
                return {"action": "DELIVER"}

        if phase == "RUSH" and not me.get("verified") and current_node == self.gate_node_id:
            return {"action": "VERIFY_GATE", "targetNodeId": self.gate_node_id}

        rush_action = self._rush_protect_action(me, phase, current_node)
        if rush_action is not None:
            return rush_action

        if self._needs_process(node, current_node):
            self._pending_process = current_node
            return {"action": "PROCESS", "targetNodeId": current_node}

        task_action = self._task_action(data, current_node, node)
        if task_action is not None:
            return task_action

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

        set_guard_action = self._set_guard_action(data, me, current_node, node, phase)
        if set_guard_action is not None:
            return set_guard_action

        target = self._pick_move_target(data, me, current_node, goal)
        if target is None:
            return None
        self._pending_move = (current_node, target)
        return {"action": "MOVE", "targetNodeId": target}

    def _sync_move_feedback(self, data: dict[str, Any], player_id: int) -> None:
        if self._pending_move is None:
            return
        move_key = self._pending_move
        for result in data.get("actionResults") or []:
            if result.get("playerId") != player_id:
                continue
            if result.get("action") != "MOVE":
                continue
            if result.get("accepted"):
                self._failed_moves.discard(move_key)
            elif result.get("errorCode") not in NON_BLACKLIST_MOVE_ERRORS:
                self._failed_moves.add(move_key)
            break
        else:
            rejected_code: Optional[str] = None
            for event in data.get("events") or []:
                if event.get("type") != "ACTION_REJECTED":
                    continue
                payload = event.get("payload") or {}
                if payload.get("playerId") != player_id:
                    continue
                rejected_code = payload.get("errorCode")
                break
            if rejected_code is None:
                for message in data.get("messages") or []:
                    if message.get("type") != "ACTION_REJECTED":
                        continue
                    payload = message.get("payload") or {}
                    if payload.get("playerId") != player_id:
                        continue
                    rejected_code = payload.get("errorCode")
                    break
            if rejected_code and rejected_code not in NON_BLACKLIST_MOVE_ERRORS:
                self._failed_moves.add(move_key)
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
                else:
                    self._failed_breaks.add(key)
            break

    def _sync_process_feedback(self, data: dict[str, Any], player_id: int) -> None:
        for event in data.get("events") or []:
            if event.get("type") != "PROCESS_COMPLETE":
                continue
            payload = event.get("payload") or {}
            if payload.get("playerId") != player_id:
                continue
            node_id = payload.get("targetNodeId")
            if node_id:
                self.process_attempted.add(node_id)
                if self._pending_process == node_id:
                    self._pending_process = None

        if self._pending_process is None:
            return
        for result in data.get("actionResults") or []:
            if result.get("playerId") != player_id:
                continue
            if result.get("action") != "PROCESS":
                continue
            if not result.get("accepted"):
                self.process_attempted.discard(self._pending_process)
            self._pending_process = None
            break

    def _sync_task_feedback(self, data: dict[str, Any], player_id: int) -> None:
        for event in data.get("events") or []:
            if event.get("type") != "TASK_COMPLETE":
                continue
            payload = event.get("payload") or {}
            if payload.get("playerId") != player_id:
                continue
            task_id = payload.get("taskId")
            if task_id:
                self._completed_task_ids.add(task_id)
            score = payload.get("score", 0)
            if isinstance(score, (int, float)):
                self._task_base_total += int(score)

    def _sync_squad_feedback(self, data: dict[str, Any], player_id: int) -> None:
        for message in data.get("messages") or []:
            msg_type = message.get("type")
            payload = message.get("payload") or {}
            if payload.get("playerId") != player_id:
                continue
            if msg_type == "SCOUT_MARKER_ADD":
                target = payload.get("targetNodeId")
                if target:
                    self._scouted_targets.add(target)
            elif msg_type == "SQUAD_SCOUT":
                target = payload.get("targetNodeId")
                if target:
                    self._scouted_targets.add(target)
            elif msg_type == "SQUAD_CLEAR":
                target = payload.get("targetNodeId")
                if target:
                    self._squad_clear_targets.add(target)

    def _squad_action(
        self,
        data: dict[str, Any],
        me: dict[str, Any],
        phase: str,
    ) -> Optional[dict[str, Any]]:
        if phase == "RUSH" or me.get("delivered") or me.get("retired"):
            return None

        round_num = data.get("round", 0)
        if round_num > SQUAD_TACTICS_MAX_ROUND:
            return None

        available = int(me.get("squadAvailable", 0))
        if available < 1:
            return None

        weaken_action = self._squad_weaken_action(data, me, available)
        if weaken_action is not None:
            return weaken_action

        clear_action = self._squad_clear_action(data, me, round_num, available)
        if clear_action is not None:
            return clear_action

        scout_action = self._squad_scout_action(me, round_num, available)
        if scout_action is not None:
            return scout_action
        return None

    def _squad_scout_action(
        self,
        me: dict[str, Any],
        round_num: int,
        available: int,
    ) -> Optional[dict[str, Any]]:
        if (
            round_num <= 20
            and SCOUT_OPENING_NODE not in self._scouted_targets
            and available >= 1
        ):
            self._scouted_targets.add(SCOUT_OPENING_NODE)
            return {"action": "SQUAD_SCOUT", "targetNodeId": SCOUT_OPENING_NODE}

        current_node = me.get("currentNodeId") or ""
        current_idx = self._route_index(current_node)
        for scout_node in SCOUT_LATE_NODES:
            if scout_node in self._scouted_targets:
                continue
            scout_idx = self._route_index(scout_node)
            if scout_idx < 0 or current_idx < scout_idx - 1:
                continue
            self._scouted_targets.add(scout_node)
            return {"action": "SQUAD_SCOUT", "targetNodeId": scout_node}
        return None

    def _squad_weaken_action(
        self,
        data: dict[str, Any],
        me: dict[str, Any],
        available: int,
    ) -> Optional[dict[str, Any]]:
        if available < 2 or me.get("state") != "IDLE":
            return None

        current_node = me.get("currentNodeId")
        if not current_node:
            return None

        team_id = me.get("teamId", "")
        candidates: list[tuple[int, str]] = []
        for neighbor in self.adjacency.get(current_node, []):
            defense = self._guard_defense(data, neighbor, team_id)
            if defense >= 4:
                candidates.append((defense, neighbor))

        next_hop = self._next_main_route_hop(current_node)
        if next_hop:
            defense = self._guard_defense(data, next_hop, team_id)
            entry = (defense, next_hop)
            if defense >= 4 and entry not in candidates:
                candidates.append(entry)

        if not candidates:
            return None

        candidates.sort(key=lambda item: (-item[0], item[1]))
        _, target = candidates[0]
        return {"action": "SQUAD_WEAKEN", "targetNodeId": target}

    def _squad_clear_action(
        self,
        data: dict[str, Any],
        me: dict[str, Any],
        round_num: int,
        available: int,
    ) -> Optional[dict[str, Any]]:
        if round_num < SQUAD_CLEAR_MIN_ROUND or available < 2:
            return None

        current_idx = self._route_index(me.get("currentNodeId") or "")
        for node_id in SQUAD_CLEAR_NODES:
            if node_id in self._squad_clear_targets:
                continue
            node_idx = self._route_index(node_id)
            if node_idx >= 0 and current_idx >= 0 and current_idx + 2 < node_idx:
                continue
            node = self._find_node(data, node_id)
            if not node.get("hasObstacle"):
                continue
            self._squad_clear_targets.add(node_id)
            return {"action": "SQUAD_CLEAR", "targetNodeId": node_id}
        return None

    def _set_guard_action(
        self,
        data: dict[str, Any],
        me: dict[str, Any],
        current_node: str,
        node: dict[str, Any],
        phase: str,
    ) -> Optional[dict[str, Any]]:
        if phase == "RUSH" or me.get("state") != "IDLE":
            return None
        if current_node not in GUARD_CHOKE_NODES:
            return None
        if self._own_guard_count(data, me) >= 2:
            return None

        guard = node.get("guard") or {}
        if guard.get("active") and guard.get("ownerTeamId") == me.get("teamId"):
            return None

        round_num = data.get("round", 0)
        if round_num < 200 and self._task_base_total < TASK_TARGET_MIN:
            return None

        if not self._should_hold_choke(data, me, current_node):
            return None

        spare_good = max(0, int(me.get("goodFruit", 0)) - 1)
        extra_good = min(2, spare_good)
        return {
            "action": "SET_GUARD",
            "targetNodeId": current_node,
            "extraGoodFruit": extra_good,
        }

    def _should_hold_choke(
        self,
        data: dict[str, Any],
        me: dict[str, Any],
        current_node: str,
    ) -> bool:
        enemy = self._find_enemy_player(data, me.get("playerId"))
        if enemy is None or enemy.get("delivered"):
            return False

        prev_hop = self._prev_main_route_hop(current_node)
        if prev_hop and self._enemy_near_node(enemy, prev_hop, current_node):
            return True

        if current_node == "S11" and self._enemy_near_node(enemy, "S10", "S11"):
            return True
        return False

    @staticmethod
    def _enemy_near_node(
        enemy: dict[str, Any],
        node_id: str,
        next_node_id: Optional[str] = None,
    ) -> bool:
        current = enemy.get("currentNodeId")
        nxt = enemy.get("nextNodeId")
        state = enemy.get("state")
        if current == node_id:
            return True
        if next_node_id and state in ("MOVING", "WAITING"):
            if current == node_id and nxt == next_node_id:
                return True
            if nxt == next_node_id:
                return True
        return False

    def _prev_main_route_hop(self, current_node: str) -> Optional[str]:
        idx = self._route_index(current_node)
        if idx <= 0:
            return None
        return MAIN_ROUTE[idx - 1]

    def _own_guard_count(self, data: dict[str, Any], me: dict[str, Any]) -> int:
        team_id = me.get("teamId", "")
        count = 0
        for node in data.get("nodes") or []:
            guard = node.get("guard") or {}
            if guard.get("active") and guard.get("ownerTeamId") == team_id:
                if int(guard.get("defense", 0)) > 0:
                    count += 1
        return count

    @staticmethod
    def _find_enemy_player(data: dict[str, Any], player_id: int) -> Optional[dict[str, Any]]:
        for player in data.get("players") or []:
            if player.get("playerId") != player_id:
                return player
        return None

    def _task_action(
        self,
        data: dict[str, Any],
        current_node: str,
        node: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        round_num = data.get("round", 0)
        if round_num > TASK_CLAIM_DEADLINE:
            return None
        task_cap = TASK_TARGET_STRETCH
        if round_num > 450 and self._task_base_total >= TASK_TARGET_MIN:
            task_cap = TASK_TARGET_MIN
        if self._task_base_total >= task_cap:
            return None
        if current_node not in ROUTE_TASK_NODES:
            return None
        if self._needs_process(node, current_node):
            return None
        return self._best_claimable_task(data, current_node)

    def _best_claimable_task(
        self,
        data: dict[str, Any],
        current_node: str,
    ) -> Optional[dict[str, Any]]:
        best: Optional[dict[str, Any]] = None
        best_score = -1
        for task in data.get("tasks") or []:
            task_id = task.get("taskId")
            if not task_id or task_id in self._completed_task_ids:
                continue
            if not task.get("active") or task.get("completed") or task.get("failed"):
                continue
            task_node = task.get("nodeId")
            if not task_node or not self._can_claim_task(data, current_node, task):
                continue
            score = task.get("score", 0)
            if score > best_score:
                best_score = score
                best = {"action": "CLAIM_TASK", "taskId": task_id}
        return best

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

        defense = self._guard_defense(data, next_node, team_id)
        if defense <= 1:
            self._edge_guard_waits.pop((current_node, next_node), None)
            return None

        edge_key = (current_node, next_node)
        waits = self._edge_guard_waits.get(edge_key, 0) + 1
        self._edge_guard_waits[edge_key] = waits
        if waits >= EDGE_GUARD_WAIT_MAX:
            self._edge_guard_waits.pop(edge_key, None)
            return None
        return {"action": "WAIT"}

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

        main_hop = self._next_main_route_hop(current_node)
        if main_hop and main_hop in self.adjacency.get(current_node, []):
            if self._enemy_guard_blocks(data, main_hop, team_id):
                targets.append((self._guard_defense(data, main_hop, team_id), main_hop))

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
        break_key = (current_node, target)
        if break_key in self._failed_breaks:
            return None

        good_fruit, bad_fruit = self._plan_break_investment(me, targets[0][0])
        if good_fruit == 0 and bad_fruit == 0:
            return None

        return {
            "action": "BREAK_GUARD",
            "targetNodeId": target,
            "goodFruit": good_fruit,
            "badFruit": bad_fruit,
        }

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

    @staticmethod
    def _guard_defense(data: dict[str, Any], node_id: str, team_id: str) -> int:
        node = RouteStrategy._find_node(data, node_id)
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
        clear_key = (current_node, target)
        if clear_key in self._failed_clears:
            return None
        self._pending_clear = clear_key
        return {"action": "CLEAR", "targetNodeId": target}

    def _pick_move_target(
        self,
        data: dict[str, Any],
        me: dict[str, Any],
        current_node: str,
        goal: str,
    ) -> Optional[str]:
        team_id = me.get("teamId", "")
        main_hop = self._next_main_route_hop(current_node)
        if main_hop and main_hop in self.adjacency.get(current_node, []):
            move_key = (current_node, main_hop)
            if move_key not in self._failed_moves and not self._is_move_blocked(
                data, main_hop, team_id
            ):
                return main_hop

        path = shortest_weighted_path(self.weighted_adjacency, current_node, goal)
        if len(path) >= 2:
            target = path[1]
            if self._is_forward_progress(current_node, target, goal):
                move_key = (current_node, target)
                if move_key not in self._failed_moves and not self._is_move_blocked(
                    data, target, team_id
                ):
                    return target

        forward = self._best_forward_neighbor(data, me, current_node, goal)
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
            if move_key in self._failed_moves:
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
    ) -> Optional[str]:
        team_id = me.get("teamId", "")
        ranked: list[tuple[int, str]] = []
        for neighbor in self.adjacency.get(current_node, []):
            if not self._is_forward_progress(current_node, neighbor, goal):
                continue
            move_key = (current_node, neighbor)
            if move_key in self._failed_moves:
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
        del data, current_node
        if me.get("verified"):
            return self.terminal_node_id
        return self.gate_node_id

    def _needs_process(self, node: dict[str, Any], current_node: str) -> bool:
        if current_node in self.process_attempted:
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

    @staticmethod
    def _find_node(data: dict[str, Any], node_id: str) -> dict[str, Any]:
        for node in data.get("nodes") or []:
            if node.get("nodeId") == node_id:
                return node
        return {}
