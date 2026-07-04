"""Official local debug package paths (V4)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
DEBUG_PKG_ROOT = (
    PROJECT_ROOT / "official_latest" / "最新地图和调测包" / "调测包及赛题相关文档_V4"
)
DEBUG_ROOT = DEBUG_PKG_ROOT / "调测"
SERVER_DIR = DEBUG_ROOT / "server"
DEMO_DIR = DEBUG_ROOT / "demo"
MAP_CONFIG = DEBUG_PKG_ROOT / "map_config.json"
