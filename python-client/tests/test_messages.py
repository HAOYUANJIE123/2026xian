import unittest

from lychee_basic_client.graph import build_adjacency, shortest_path
from lychee_basic_client.messages import action_message, heartbeat_action
from lychee_basic_client.strategy import EDGE_GUARD_WAIT_MAX, GUARD_STUCK_BREAK_RETRY, RouteStrategy


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

    def test_waiting_at_s02_processes_after_move_rejected(self) -> None:
        strategy = RouteStrategy()
        strategy.load_start(
            {
                "matchId": "m1",
                "edges": [{"fromNodeId": "S02", "toNodeId": "S03", "bidirectional": True}],
                "map": {"gameplay": {"roles": {"gateNodeId": "S14", "terminalNodeIds": ["S15"]}}},
            }
        )
        strategy._pending_move = ("S02", "S03")
        strategy._last_node_id = "S02"
        actions = strategy.decide(
            {
                "round": 44,
                "phase": "NORMAL",
                "messages": [
                    {
                        "type": "ACTION_REJECTED",
                        "payload": {"playerId": 1001, "errorCode": "PROCESS_REQUIRED"},
                    }
                ],
                "players": [
                    {
                        "playerId": 1001,
                        "teamId": "RED",
                        "state": "WAITING",
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
        self.assertEqual([{"action": "PROCESS", "targetNodeId": "S02"}], actions)
        self.assertNotIn(("S02", "S03"), strategy._failed_moves)

    def test_process_required_does_not_blacklist_move(self) -> None:
        strategy = RouteStrategy()
        strategy.load_start(
            {
                "matchId": "m1",
                "edges": [{"fromNodeId": "S02", "toNodeId": "S03", "bidirectional": True}],
                "map": {"gameplay": {"roles": {"gateNodeId": "S14", "terminalNodeIds": ["S15"]}}},
            }
        )
        strategy._pending_move = ("S02", "S03")
        strategy._last_node_id = "S02"
        strategy._sync_move_feedback(
            {
                "actionResults": [
                    {
                        "playerId": 1001,
                        "action": "MOVE",
                        "accepted": False,
                        "errorCode": "PROCESS_REQUIRED",
                    }
                ]
            },
            1001,
        )
        self.assertNotIn(("S02", "S03"), strategy._failed_moves)

    def test_moves_from_s09_when_no_guard(self) -> None:
        strategy = RouteStrategy()
        strategy.load_start(
            {
                "matchId": "m1",
                "edges": [
                    {"fromNodeId": "S09", "toNodeId": "S10", "bidirectional": True},
                    {"fromNodeId": "S10", "toNodeId": "S11", "bidirectional": True},
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
        self.assertEqual([{"action": "MOVE", "targetNodeId": "S10"}], actions)

    def test_follows_main_route_from_s01(self) -> None:
        strategy = RouteStrategy()
        strategy.load_start(
            {
                "matchId": "m1",
                "edges": [
                    {"fromNodeId": "S01", "toNodeId": "S02", "bidirectional": True},
                    {"fromNodeId": "S01", "toNodeId": "S06", "bidirectional": True},
                    {"fromNodeId": "S02", "toNodeId": "S03", "bidirectional": True},
                    {"fromNodeId": "S06", "toNodeId": "S08", "bidirectional": True},
                ],
                "map": {"gameplay": {"roles": {"gateNodeId": "S14", "terminalNodeIds": ["S15"]}}},
            }
        )
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
                "nodes": [{"nodeId": "S01"}, {"nodeId": "S02"}, {"nodeId": "S06"}],
            },
            1001,
        )
        self.assertEqual([{"action": "MOVE", "targetNodeId": "S02"}], actions)

    def test_opening_squad_scout_s10(self) -> None:
        strategy = RouteStrategy()
        strategy.load_start(
            {
                "matchId": "m1",
                "edges": [{"fromNodeId": "S01", "toNodeId": "S02", "bidirectional": True}],
                "map": {"gameplay": {"roles": {"gateNodeId": "S14", "terminalNodeIds": ["S15"]}}},
            }
        )
        actions = strategy.decide(
            {
                "round": 1,
                "phase": "NORMAL",
                "players": [
                    {
                        "playerId": 1001,
                        "teamId": "RED",
                        "state": "MOVING",
                        "currentNodeId": "S01",
                        "nextNodeId": "S02",
                        "verified": False,
                        "delivered": False,
                        "squadAvailable": 8,
                    }
                ],
                "nodes": [{"nodeId": "S01"}],
            },
            1001,
        )
        self.assertIn(
            {"action": "SQUAD_SCOUT", "targetNodeId": "S10"},
            actions,
        )

    def test_set_guard_at_s10_when_enemy_approaches(self) -> None:
        strategy = RouteStrategy()
        strategy.load_start(
            {
                "matchId": "m1",
                "edges": [
                    {"fromNodeId": "S09", "toNodeId": "S10", "bidirectional": True},
                    {"fromNodeId": "S10", "toNodeId": "S11", "bidirectional": True},
                ],
                "map": {"gameplay": {"roles": {"gateNodeId": "S14", "terminalNodeIds": ["S15"]}}},
            }
        )
        strategy.process_attempted.add("S10")
        strategy._task_base_total = 90
        actions = strategy.decide(
            {
                "round": 280,
                "phase": "NORMAL",
                "players": [
                    {
                        "playerId": 1001,
                        "teamId": "RED",
                        "state": "IDLE",
                        "currentNodeId": "S10",
                        "verified": False,
                        "delivered": False,
                        "goodFruit": 95,
                        "squadAvailable": 6,
                    },
                    {
                        "playerId": 2002,
                        "teamId": "BLUE",
                        "state": "MOVING",
                        "currentNodeId": "S09",
                        "nextNodeId": "S10",
                        "delivered": False,
                    },
                ],
                "nodes": [
                    {"nodeId": "S10", "processRound": 0, "guard": {"active": False}},
                    {"nodeId": "S09"},
                ],
            },
            1001,
        )
        main_actions = [a for a in actions if a.get("action") != "SQUAD_SCOUT"]
        self.assertEqual("SET_GUARD", main_actions[0]["action"])
        self.assertEqual("S10", main_actions[0]["targetNodeId"])

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

    def test_skips_road_task_on_mountain_route(self) -> None:
        strategy = RouteStrategy()
        strategy.load_start(
            {
                "matchId": "m1",
                "edges": [
                    {"fromNodeId": "S09", "toNodeId": "S10", "bidirectional": True},
                ],
                "map": {"gameplay": {"roles": {"gateNodeId": "S14", "terminalNodeIds": ["S15"]}}},
            }
        )
        strategy.process_attempted.add("S09")
        actions = strategy.decide(
            {
                "round": 247,
                "phase": "NORMAL",
                "tasks": [
                    {
                        "taskId": "T_013",
                        "nodeId": "S09",
                        "active": True,
                        "completed": False,
                        "failed": False,
                        "routeBucket": "ROAD",
                        "taskTemplateId": "T06",
                        "score": 30,
                    }
                ],
                "players": [
                    {
                        "playerId": 1001,
                        "teamId": "RED",
                        "state": "IDLE",
                        "currentNodeId": "S09",
                        "mainRoute": "MOUNTAIN",
                        "routeTaskScore": "MOUNTAIN:60",
                        "verified": False,
                        "delivered": False,
                        "goodFruit": 99,
                    }
                ],
                "nodes": [{"nodeId": "S09", "processRound": 0}],
            },
            1001,
        )
        self.assertEqual([{"action": "MOVE", "targetNodeId": "S10"}], actions)

    def test_blacklists_failed_claim(self) -> None:
        strategy = RouteStrategy()
        strategy.load_start(
            {
                "matchId": "m1",
                "edges": [{"fromNodeId": "S09", "toNodeId": "S10", "bidirectional": True}],
                "map": {"gameplay": {"roles": {"gateNodeId": "S14", "terminalNodeIds": ["S15"]}}},
            }
        )
        strategy.process_attempted.add("S09")
        strategy._pending_claim = "T_013"
        strategy.decide(
            {
                "round": 248,
                "phase": "NORMAL",
                "messages": [
                    {
                        "type": "ACTION_REJECTED",
                        "payload": {"playerId": 1001, "errorCode": "RESOURCE_NOT_ENOUGH"},
                    }
                ],
                "tasks": [
                    {
                        "taskId": "T_013",
                        "nodeId": "S09",
                        "active": True,
                        "completed": False,
                        "failed": False,
                        "routeBucket": "ROAD",
                        "score": 30,
                    }
                ],
                "players": [
                    {
                        "playerId": 1001,
                        "teamId": "RED",
                        "state": "IDLE",
                        "currentNodeId": "S09",
                        "mainRoute": "ROAD",
                        "verified": False,
                        "delivered": False,
                        "goodFruit": 99,
                    }
                ],
                "nodes": [
                    {"nodeId": "S09", "processRound": 0},
                    {"nodeId": "S10", "guard": {"active": False}},
                ],
            },
            1001,
        )
        self.assertIn("T_013", strategy._failed_claims)
        actions = strategy.decide(
            {
                "round": 249,
                "phase": "NORMAL",
                "tasks": [
                    {
                        "taskId": "T_013",
                        "nodeId": "S09",
                        "active": True,
                        "completed": False,
                        "failed": False,
                        "routeBucket": "ROAD",
                        "score": 30,
                    }
                ],
                "players": [
                    {
                        "playerId": 1001,
                        "teamId": "RED",
                        "state": "IDLE",
                        "currentNodeId": "S09",
                        "mainRoute": "ROAD",
                        "verified": False,
                        "delivered": False,
                        "goodFruit": 99,
                    }
                ],
                "nodes": [
                    {"nodeId": "S09", "processRound": 0},
                    {"nodeId": "S10", "guard": {"active": False}},
                ],
            },
            1001,
        )
        self.assertEqual([{"action": "MOVE", "targetNodeId": "S10"}], actions)

    def test_edge_blocked_holds_instead_of_move(self) -> None:
        strategy = RouteStrategy()
        strategy.load_start(
            {
                "matchId": "m1",
                "edges": [{"fromNodeId": "S09", "toNodeId": "S10", "bidirectional": True}],
                "map": {"gameplay": {"roles": {"gateNodeId": "S14", "terminalNodeIds": ["S15"]}}},
            }
        )
        strategy._edge_guard_waits[("S09", "S10")] = EDGE_GUARD_WAIT_MAX
        actions = strategy.decide(
            {
                "round": 300,
                "phase": "NORMAL",
                "players": [
                    {
                        "playerId": 1001,
                        "teamId": "BLUE",
                        "state": "WAITING",
                        "currentNodeId": "S09",
                        "nextNodeId": "S10",
                        "verified": False,
                        "delivered": False,
                        "squadAvailable": 0,
                    }
                ],
                "nodes": [
                    {"nodeId": "S09"},
                    {
                        "nodeId": "S10",
                        "guard": {"active": True, "ownerTeamId": "RED", "defense": 6},
                    },
                ],
            },
            1001,
        )
        self.assertEqual([{"action": "WAIT"}], actions)

    def test_waits_at_s09_when_enemy_on_choke_edge(self) -> None:
        strategy = RouteStrategy()
        strategy.load_start(
            {
                "matchId": "m1",
                "edges": [{"fromNodeId": "S09", "toNodeId": "S10", "bidirectional": True}],
                "map": {"gameplay": {"roles": {"gateNodeId": "S14", "terminalNodeIds": ["S15"]}}},
            }
        )
        strategy.process_attempted.add("S09")
        strategy._task_base_total = 90
        actions = strategy.decide(
            {
                "round": 246,
                "phase": "NORMAL",
                "players": [
                    {
                        "playerId": 1001,
                        "teamId": "RED",
                        "state": "IDLE",
                        "currentNodeId": "S09",
                        "verified": False,
                        "delivered": False,
                        "goodFruit": 99,
                        "badFruit": 1,
                    },
                    {
                        "playerId": 2002,
                        "teamId": "BLUE",
                        "state": "MOVING",
                        "currentNodeId": "S09",
                        "nextNodeId": "S10",
                        "delivered": False,
                    },
                ],
                "nodes": [
                    {"nodeId": "S09", "processRound": 0},
                    {"nodeId": "S10", "guard": {"active": False}},
                ],
            },
            1001,
        )
        self.assertEqual([{"action": "WAIT"}], actions)

    def test_no_task_claim_at_s09_when_enemy_contests_even_below_task_target(self) -> None:
        strategy = RouteStrategy()
        strategy.load_start(
            {
                "matchId": "m1",
                "edges": [{"fromNodeId": "S09", "toNodeId": "S10", "bidirectional": True}],
                "map": {"gameplay": {"roles": {"gateNodeId": "S14", "terminalNodeIds": ["S15"]}}},
            }
        )
        strategy.process_attempted.add("S09")
        strategy._task_base_total = 60
        actions = strategy.decide(
            {
                "round": 244,
                "phase": "NORMAL",
                "tasks": [
                    {
                        "taskId": "T_012",
                        "routeType": "ROAD",
                        "baseScore": 30,
                        "status": "AVAILABLE",
                    }
                ],
                "players": [
                    {
                        "playerId": 1001,
                        "teamId": "RED",
                        "state": "IDLE",
                        "currentNodeId": "S09",
                        "verified": False,
                        "delivered": False,
                        "goodFruit": 99,
                        "badFruit": 1,
                    },
                    {
                        "playerId": 2002,
                        "teamId": "BLUE",
                        "state": "MOVING",
                        "currentNodeId": "S09",
                        "nextNodeId": "S10",
                        "delivered": False,
                    },
                ],
                "nodes": [
                    {"nodeId": "S09", "processRound": 0},
                    {"nodeId": "S10", "guard": {"active": False}},
                ],
            },
            1001,
        )
        self.assertEqual([{"action": "WAIT"}], actions)

    def test_claims_task_at_s10_when_s11_guarded_but_no_edge_contest(self) -> None:
        strategy = RouteStrategy()
        strategy.load_start(
            {
                "matchId": "m1",
                "edges": [
                    {"fromNodeId": "S10", "toNodeId": "S11", "bidirectional": True},
                    {"fromNodeId": "S11", "toNodeId": "S12", "bidirectional": True},
                ],
                "map": {"gameplay": {"roles": {"gateNodeId": "S14", "terminalNodeIds": ["S15"]}}},
            }
        )
        strategy.process_attempted.add("S10")
        strategy._task_base_total = 150
        actions = strategy.decide(
            {
                "round": 390,
                "phase": "NORMAL",
                "tasks": [
                    {
                        "taskId": "T_020",
                        "nodeId": "S10",
                        "active": True,
                        "completed": False,
                        "failed": False,
                        "routeBucket": "WATER",
                        "score": 30,
                    }
                ],
                "players": [
                    {
                        "playerId": 1001,
                        "teamId": "RED",
                        "state": "IDLE",
                        "currentNodeId": "S10",
                        "mainRoute": "WATER",
                        "verified": False,
                        "delivered": False,
                        "goodFruit": 99,
                    },
                    {
                        "playerId": 2002,
                        "teamId": "BLUE",
                        "state": "MOVING",
                        "currentNodeId": "S12",
                        "delivered": False,
                    },
                ],
                "nodes": [
                    {"nodeId": "S10", "processRound": 0},
                    {
                        "nodeId": "S11",
                        "guard": {
                            "active": True,
                            "ownerTeamId": "BLUE",
                            "defense": 6,
                        },
                    },
                ],
            },
            1001,
        )
        self.assertEqual("CLAIM_TASK", actions[0]["action"])

    def test_still_claims_tasks_at_s11_before_delivery_push(self) -> None:
        strategy = RouteStrategy()
        strategy.load_start(
            {
                "matchId": "m1",
                "edges": [{"fromNodeId": "S11", "toNodeId": "S12", "bidirectional": True}],
                "map": {"gameplay": {"roles": {"gateNodeId": "S14", "terminalNodeIds": ["S15"]}}},
            }
        )
        strategy.process_attempted.add("S11")
        strategy._task_base_total = 150
        actions = strategy.decide(
            {
                "round": 360,
                "phase": "NORMAL",
                "tasks": [
                    {
                        "taskId": "T_022",
                        "nodeId": "S11",
                        "active": True,
                        "completed": False,
                        "failed": False,
                        "routeBucket": "ROAD",
                        "score": 30,
                    }
                ],
                "players": [
                    {
                        "playerId": 1001,
                        "teamId": "RED",
                        "state": "IDLE",
                        "currentNodeId": "S11",
                        "mainRoute": "WATER",
                        "routeResourceCount": "ROAD:1",
                        "verified": False,
                        "delivered": False,
                        "goodFruit": 99,
                    }
                ],
                "nodes": [{"nodeId": "S11", "processRound": 0}],
            },
            1001,
        )
        self.assertEqual("CLAIM_TASK", actions[0]["action"])

    def test_waits_on_choke_edge_when_guard_blocks_instead_of_move_spam(self) -> None:
        strategy = RouteStrategy()
        strategy.load_start(
            {
                "matchId": "m1",
                "edges": [{"fromNodeId": "S09", "toNodeId": "S10", "bidirectional": True}],
                "map": {"gameplay": {"roles": {"gateNodeId": "S14", "terminalNodeIds": ["S15"]}}},
            }
        )
        actions = strategy.decide(
            {
                "round": 290,
                "phase": "NORMAL",
                "players": [
                    {
                        "playerId": 1001,
                        "teamId": "RED",
                        "state": "MOVING",
                        "currentNodeId": "S09",
                        "nextNodeId": "S10",
                        "verified": False,
                        "delivered": False,
                        "goodFruit": 99,
                        "badFruit": 1,
                    },
                    {
                        "playerId": 2002,
                        "teamId": "BLUE",
                        "state": "IDLE",
                        "currentNodeId": "S10",
                        "delivered": False,
                    },
                ],
                "nodes": [
                    {"nodeId": "S09"},
                    {
                        "nodeId": "S10",
                        "guard": {
                            "active": True,
                            "ownerTeamId": "BLUE",
                            "defense": 6,
                        },
                    },
                ],
            },
            1001,
        )
        self.assertEqual([{"action": "WAIT"}], actions)

    def test_waits_at_s09_when_enemy_occupies_s10_before_edge_entry(self) -> None:
        strategy = RouteStrategy()
        strategy.load_start(
            {
                "matchId": "m1",
                "edges": [{"fromNodeId": "S09", "toNodeId": "S10", "bidirectional": True}],
                "map": {"gameplay": {"roles": {"gateNodeId": "S14", "terminalNodeIds": ["S15"]}}},
            }
        )
        strategy.process_attempted.add("S09")
        actions = strategy.decide(
            {
                "round": 245,
                "phase": "NORMAL",
                "players": [
                    {
                        "playerId": 1001,
                        "teamId": "RED",
                        "state": "IDLE",
                        "currentNodeId": "S09",
                        "verified": False,
                        "delivered": False,
                        "goodFruit": 99,
                        "badFruit": 1,
                    },
                    {
                        "playerId": 2002,
                        "teamId": "BLUE",
                        "state": "IDLE",
                        "currentNodeId": "S10",
                        "delivered": False,
                    },
                ],
                "nodes": [
                    {"nodeId": "S09", "processRound": 0},
                    {"nodeId": "S10", "guard": {"active": False}},
                ],
            },
            1001,
        )
        self.assertIn(actions[0]["action"], ("WAIT", "BREAK_GUARD"))

    def test_retries_break_after_guard_stuck(self) -> None:
        strategy = RouteStrategy()
        strategy.load_start(
            {
                "matchId": "m1",
                "edges": [{"fromNodeId": "S09", "toNodeId": "S10", "bidirectional": True}],
                "map": {"gameplay": {"roles": {"gateNodeId": "S14", "terminalNodeIds": ["S15"]}}},
            }
        )
        strategy.process_attempted.add("S09")
        strategy._failed_breaks.add(("S09", "S10"))
        strategy._guard_stuck_streak[("S09", "S10")] = GUARD_STUCK_BREAK_RETRY
        actions = strategy.decide(
            {
                "round": 300,
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


if __name__ == "__main__":
    unittest.main()
