import unittest

from lychee_basic_client.graph import (
    build_weighted_adjacency,
    shortest_weighted_path,
)


class GraphTests(unittest.TestCase):
    def test_water_route_preferred_at_s02(self) -> None:
        edges = [
            {"fromNodeId": "S01", "toNodeId": "S02", "routeType": "ROAD", "distance": 30},
            {"fromNodeId": "S02", "toNodeId": "S03", "routeType": "ROAD", "distance": 25},
            {"fromNodeId": "S02", "toNodeId": "S04", "routeType": "ROAD", "distance": 20},
            {"fromNodeId": "S03", "toNodeId": "S07", "routeType": "ROAD", "distance": 54},
            {"fromNodeId": "S04", "toNodeId": "S05", "routeType": "WATER", "distance": 44},
            {"fromNodeId": "S05", "toNodeId": "S09", "routeType": "WATER", "distance": 48},
            {"fromNodeId": "S07", "toNodeId": "S09", "routeType": "ROAD", "distance": 46},
            {"fromNodeId": "S09", "toNodeId": "S14", "routeType": "ROAD", "distance": 40},
        ]
        weighted = build_weighted_adjacency(edges)
        path = shortest_weighted_path(weighted, "S02", "S14")
        self.assertEqual(path[1], "S04")


if __name__ == "__main__":
    unittest.main()
