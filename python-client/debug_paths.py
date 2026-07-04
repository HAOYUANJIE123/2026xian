"""Official local debug package paths (V5)."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
DEBUG_PKG_ROOT = PROJECT_ROOT / "official_latest" / "V5" / "调测包及赛题相关文档_V5"
DEBUG_ROOT = DEBUG_PKG_ROOT / "调测"
SERVER_DIR = DEBUG_ROOT / "server"
DEMO_DIR = DEBUG_ROOT / "demo"

# Relative to SERVER_DIR when passed to lychee-arena-server.exe -m (see start-server.bat).
DEFAULT_MAP_JSON = "map_config.json"
VARIANT_MAP_JSON = "map_config_variant_a.json"

MAP_CONFIG = SERVER_DIR / DEFAULT_MAP_JSON
MAP_CONFIG_VARIANT_A = SERVER_DIR / VARIANT_MAP_JSON

# Override via env, e.g. MAP_JSON=map_config_variant_a.json
ACTIVE_MAP_JSON = os.environ.get("MAP_JSON", DEFAULT_MAP_JSON)


def resolve_map_arg(map_json: str | None = None) -> str:
    """Return the -m argument for the server (relative filename by default)."""
    chosen = map_json or ACTIVE_MAP_JSON
    path = Path(chosen)
    if path.is_file():
        try:
            return path.relative_to(SERVER_DIR).as_posix()
        except ValueError:
            return str(path)
    return chosen.replace("\\", "/")


def map_file(map_json: str | None = None) -> Path:
    """Absolute path to the map JSON file."""
    arg = resolve_map_arg(map_json)
    path = Path(arg)
    if path.is_file():
        return path
    return SERVER_DIR / arg
