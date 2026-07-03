import unittest

from lychee_basic_client.graph import build_adjacency, shortest_path
from lychee_basic_client.messages import action_message, heartbeat_action
from lychee_basic_client.strategy import RouteStrategy


class MessageTests(unittest.TestCase):
    def test_heartbeat_action_uses_empty_actions(self) -> None:
        self.assertEqual(
            {
                "msg_name": "action",
                "msg_data": {
                    "matchId": "match-1",
                    "round": 7,
                    "playerId": 1001,
                    "actions": [],
                },
            },
            heartbeat_action("match-1", 7, 1001),
        )

    def test_action_message_accepts_multiple_actions(self) -> None:
        actions = [{"action": "MOVE", "targetNodeId": "S02"}]
        self.assertEqual(
            action_message("match-1", 7, 1001, actions)["msg_data"]["actions"],
            actions,
        )


class GraphTests(unittest.TestCase):
    def test_shortest_path_on_sample_edges(self) -> None:
        edges = [
            {"fromNodeId": "S01", "toNodeId": "S02", "bidirectional": True},
            {"fromNodeId": "S02", "toNodeId": "S03", "bidirectional": True},
        ]
        adjacency = build_adjacency(edges)
        self.assertEqual(["S01", "S02", "S03"], shortest_path(adjacency, "S01", "S03"))


class StrategyTests(unittest.TestCase):
    def test_idle_at_process_node_submits_process(self) -> None:
        strategy = RouteStrategy()
        strategy.load_start(
            {
                "matchId": "m1",
                "edges": [{"fromNodeId": "S02", "toNodeId": "S03", "bidirectional": True}],
                "map": {"gameplay": {"roles": {"gateNodeId": "S14", "terminalNodeIds": ["S15"]}}},
            }
        )
        actions = strategy.decide(
            {
                "round": 3,
                "phase": "NORMAL",
                "players": [
                    {
                        "playerId": 1001,
                        "state": "IDLE",
                        "currentNodeId": "S03",
                        "verified": False,
                        "delivered": False,
                        "goodFruit": 100,
                        "freshness": 100,
                    }
                ],
                "nodes": [
                    {
                        "nodeId": "S03",
                        "processType": "TRANSFER",
                        "processRound": 4,
                    }
                ],
            },
            1001,
        )
        self.assertEqual([{"action": "PROCESS", "targetNodeId": "S03"}], actions)

    def test_picks_reachable_neighbor_when_shortest_hop_is_blocked(self) -> None:
        strategy = RouteStrategy()
        strategy.load_start(
            {
                "matchId": "m1",
                "edges": [
                    {"fromNodeId": "S01", "toNodeId": "S02", "bidirectional": True},
                    {"fromNodeId": "S01", "toNodeId": "S06", "bidirectional": True},
                    {"fromNodeId": "S02", "toNodeId": "S14", "bidirectional": True},
                    {"fromNodeId": "S06", "toNodeId": "S14", "bidirectional": True},
                ],
                "map": {"gameplay": {"roles": {"gateNodeId": "S14", "terminalNodeIds": ["S15"]}}},
            }
        )
        strategy._failed_moves.add(("S01", "S06"))
        actions = strategy.decide(
            {
                "round": 2,
                "phase": "NORMAL",
                "players": [
                    {
                        "playerId": 1001,
                        "teamId": "RED",
                        "state": "IDLE",
                        "currentNodeId": "S01",
                        "verified": False,
                        "delivered": False,
                    }
                ],
                "nodes": [
                    {"nodeId": "S01"},
                    {"nodeId": "S02"},
                    {"nodeId": "S06", "hasObstacle": True},
                ],
            },
            1001,
        )
        self.assertEqual([{"action": "MOVE", "targetNodeId": "S02"}], actions)

    def test_uses_horse_before_move_when_in_inventory(self) -> None:
        strategy = RouteStrategy()
        strategy.load_start(
            {
                "matchId": "m1",
                "edges": [
                    {"fromNodeId": "S04", "toNodeId": "S05", "bidirectional": True},
                    {"fromNodeId": "S05", "toNodeId": "S14", "bidirectional": True},
                ],
                "map": {"gameplay": {"roles": {"gateNodeId": "S14", "terminalNodeIds": ["S15"]}}},
            }
        )
        strategy.process_attempted.add("S04")
        actions = strategy.decide(
            {
                "round": 90,
                "phase": "NORMAL",
                "players": [
                    {
                        "playerId": 1001,
                        "teamId": "RED",
                        "state": "IDLE",
                        "currentNodeId": "S09",
                        "verified": False,
                        "delivered": False,
                        "resources": {"FAST_HORSE": 1},
                        "buffs": [],
                    }
                ],
                "nodes": [{"nodeId": "S09", "processRound": 0}],
            },
            1001,
        )
        self.assertEqual([{"action": "USE_RESOURCE", "resourceType": "FAST_HORSE"}], actions)

    def test_skips_process_at_s02(self) -> None:
        strategy = RouteStrategy()
        strategy.load_start(
            {
                "matchId": "m1",
                "edges": [{"fromNodeId": "S02", "toNodeId": "S03", "bidirectional": True}],
                "map": {"gameplay": {"roles": {"gateNodeId": "S14", "terminalNodeIds": ["S15"]}}},
            }
        )
        actions = strategy.decide(
            {
                "round": 50,
                "phase": "NORMAL",
                "players": [
                    {
                        "playerId": 1001,
                        "teamId": "BLUE",
                        "state": "IDLE",
                        "currentNodeId": "S02",
                        "verified": False,
                        "delivered": False,
                    }
                ],
                "nodes": [
                    {
                        "nodeId": "S02",
                        "processType": "TRANSFER",
                        "processRound": 4,
                    }
                ],
            },
            1001,
        )
        self.assertNotEqual("PROCESS", actions[0].get("action") if actions else None)

    def test_guard_hold_waits_at_s09_before_moving(self) -> None:
        strategy = RouteStrategy()
        strategy.load_start(
            {
                "matchId": "m1",
                "edges": [
                    {"fromNodeId": "S09", "toNodeId": "S10", "bidirectional": True},
                    {"fromNodeId": "S10", "toNodeId": "S14", "bidirectional": True},
                ],
                "map": {"gameplay": {"roles": {"gateNodeId": "S14", "terminalNodeIds": ["S15"]}}},
            }
        )
        strategy.process_attempted.add("S09")
        actions = strategy.decide(
            {
                "round": 260,
                "phase": "NORMAL",
                "players": [
                    {
                        "playerId": 1001,
                        "teamId": "BLUE",
                        "state": "IDLE",
                        "currentNodeId": "S09",
                        "verified": False,
                        "delivered": False,
                        "goodFruit": 99,
                        "badFruit": 1,
                    }
                ],
                "nodes": [
                    {"nodeId": "S09", "processRound": 0},
                    {"nodeId": "S10", "guard": {"active": False}},
                ],
            },
            1001,
        )
        self.assertEqual([{"action": "WAIT"}], actions)

    def test_break_guard_at_s09_when_s10_guarded(self) -> None:
        strategy = RouteStrategy()
        strategy.load_start(
            {
                "matchId": "m1",
                "edges": [
                    {"fromNodeId": "S09", "toNodeId": "S10", "bidirectional": True},
                    {"fromNodeId": "S10", "toNodeId": "S14", "bidirectional": True},
                ],
                "map": {"gameplay": {"roles": {"gateNodeId": "S14", "terminalNodeIds": ["S15"]}}},
            }
        )
        strategy.process_attempted.add("S09")
        actions = strategy.decide(
            {
                "round": 298,
                "phase": "NORMAL",
                "players": [
                    {
                        "playerId": 1001,
                        "teamId": "BLUE",
                        "state": "IDLE",
                        "currentNodeId": "S09",
                        "verified": False,
                        "delivered": False,
                        "goodFruit": 99,
                        "badFruit": 1,
                    }
                ],
                "nodes": [
                    {"nodeId": "S09", "processRound": 0},
                    {
                        "nodeId": "S10",
                        "guard": {
                            "active": True,
                            "ownerTeamId": "RED",
                            "defense": 6,
                        },
                    },
                ],
            },
            1001,
        )
        self.assertEqual("BREAK_GUARD", actions[0]["action"])
        self.assertEqual("S10", actions[0]["targetNodeId"])
        self.assertGreaterEqual(
            actions[0]["goodFruit"] * 2 + actions[0]["badFruit"] * 3,
            6,
        )


if __name__ == "__main__":
    unittest.main()
