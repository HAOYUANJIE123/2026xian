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
MAIN_ROUTE = ("S01", "S02", "S04", "S05", "S09", "S10", "S11", "S12", "S13", "S14", "S15")
ROUTE_TASK_NODES = frozenset({"S04", "S05", "S09", "S10"})
HORSE_USE_NODES = frozenset({"S04", "S05", "S09", "S10", "S11", "S12", "S13"})
RUSH_SPEED_NODES = frozenset({"S09", "S10", "S11", "S12", "S13", "S14"})
ICE_USE_FRESHNESS = 90.0


class RouteStrategy:
    def __init__(self) -> None:
        self.gate_node_id = "S14"
        self.terminal_node_id = "S15"
        self.adjacency: dict[str, list[str]] = {}
        self.weighted_adjacency: dict[str, list[tuple[str, int]]] = {}
        self.process_attempted: set[str] = set()
        self._failed_moves: set[tuple[str, str]] = set()
        self._failed_clears: set[tuple[str, str]] = set()
        self._pending_move: Optional[tuple[str, str]] = None
        self._pending_clear: Optional[tuple[str, str]] = None
        self._pending_process: Optional[str] = None
        self._last_node_id: Optional[str] = None
        self._resource_claimed_nodes: set[str] = set()
        self._completed_task_ids: set[str] = set()
        self._task_nodes_done: set[str] = set()
        self._task_base_total = 0

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
        self._pending_move = None
        self._pending_clear = None
        self._pending_process = None
        self._last_node_id = None
        self._resource_claimed_nodes.clear()
        self._completed_task_ids.clear()
        self._task_nodes_done.clear()
        self._task_base_total = 0

    def decide(self, data: dict[str, Any], player_id: int) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []

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
        self._sync_process_feedback(data, player_id)
        self._sync_task_feedback(data, player_id)

        state = me.get("state", "IDLE")
        if state in WAIT_STATES:
            return None
        if me.get("delivered") or me.get("retired"):
            return None

        current_node = me.get("currentNodeId")
        if not current_node:
            return None

        if self._last_node_id and self._last_node_id != current_node:
            self.process_attempted.discard(self._last_node_id)
        self._last_node_id = current_node

        phase = data.get("phase", "NORMAL")
        node = self._find_node(data, current_node)

        if current_node == self.terminal_node_id:
            if me.get("verified") and self._can_deliver(me):
                return {"action": "DELIVER"}

        if phase == "RUSH" and not me.get("verified") and current_node == self.gate_node_id:
            return {"action": "VERIFY_GATE", "targetNodeId": self.gate_node_id}

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

        rush_action = self._rush_speed_action(me, phase, current_node)
        if rush_action is not None:
            return rush_action

        goal = self._goal(me, phase)
        if goal is None or current_node == goal:
            return None

        clear_action = self._clear_action(data, me, current_node, goal)
        if clear_action is not None:
            return clear_action

        target = self._pick_move_target(data, me, current_node, goal)
        if target is None:
            return None
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
            else:
                self._failed_moves.add(self._pending_move)
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
            node_id = payload.get("nodeId")
            if node_id:
                self._task_nodes_done.add(node_id)

    def _task_action(
        self,
        data: dict[str, Any],
        current_node: str,
        node: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        if self._task_base_total >= TASK_TARGET_BASE:
            return None
        if current_node not in ROUTE_TASK_NODES:
            return None
        if current_node in self._task_nodes_done:
            return None
        if self._needs_process(node, current_node):
            return None

        best: Optional[dict[str, Any]] = None
        best_score = -1
        for task in data.get("tasks") or []:
            task_id = task.get("taskId")
            if not task_id or task_id in self._completed_task_ids:
                continue
            if task.get("nodeId") != current_node:
                continue
            if not task.get("active") or task.get("completed") or task.get("failed"):
                continue
            score = task.get("score", 0)
            if score > best_score:
                best_score = score
                best = {"action": "CLAIM_TASK", "taskId": task_id}
        return best

    def _claim_resource_action(self, node: dict[str, Any], current_node: str) -> Optional[dict[str, Any]]:
        if current_node in self._resource_claimed_nodes:
            return None
        preferred = "SHORT_HORSE" if current_node == "S04" else "FAST_HORSE"
        if current_node not in ("S04", "S09"):
            return None
        stock = node.get("resourceStock") or {}
        if stock.get(preferred, 0) <= 0:
            return None
        self._resource_claimed_nodes.add(current_node)
        return {
            "action": "CLAIM_RESOURCE",
            "targetNodeId": current_node,
            "resourceType": preferred,
        }

    def _use_resource_action(
        self,
        me: dict[str, Any],
        current_node: str,
        phase: str,
    ) -> Optional[dict[str, Any]]:
        resources = me.get("resources") or {}
        if self._has_move_buff(me):
            if resources.get("ICE_BOX", 0) > 0 and me.get("freshness", 100) < ICE_USE_FRESHNESS:
                return {"action": "USE_RESOURCE", "resourceType": "ICE_BOX"}
            return None

        if phase == "RUSH":
            return None

        if current_node in HORSE_USE_NODES:
            if resources.get("FAST_HORSE", 0) > 0:
                return {"action": "USE_RESOURCE", "resourceType": "FAST_HORSE"}
            if resources.get("SHORT_HORSE", 0) > 0:
                return {"action": "USE_RESOURCE", "resourceType": "SHORT_HORSE"}

        if resources.get("ICE_BOX", 0) > 0 and me.get("freshness", 100) < ICE_USE_FRESHNESS:
            return {"action": "USE_RESOURCE", "resourceType": "ICE_BOX"}
        return None

    def _rush_speed_action(
        self,
        me: dict[str, Any],
        phase: str,
        current_node: str,
    ) -> Optional[dict[str, Any]]:
        if phase != "RUSH":
            return None
        if me.get("rushTacticUsedCount", 0) > 0:
            return None
        if self._has_move_buff(me):
            return None
        if current_node not in RUSH_SPEED_NODES and not me.get("verified"):
            return None
        return {"action": "RUSH_SPEED"}

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
        path = shortest_weighted_path(self.weighted_adjacency, current_node, goal)
        if len(path) >= 2:
            target = path[1]
            if not self._is_backtrack(current_node, target):
                move_key = (current_node, target)
                team_id = me.get("teamId", "")
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
            if self._is_backtrack(current_node, neighbor):
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

    def _goal(self, me: dict[str, Any], phase: str) -> Optional[str]:
        if me.get("verified"):
            return self.terminal_node_id
        if phase == "RUSH":
            return self.gate_node_id
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
