#!/usr/bin/env python3
"""Run a local Python-vs-Python match (our client vs teammate client)."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
TEAMMATE_ROOT = PROJECT_ROOT / "deng" / "extracted"
DEBUG_ROOT = PROJECT_ROOT / "比赛资料" / "比赛资料" / "调测包及赛题相关文档_V1" / "调测"
SERVER_DIR = DEBUG_ROOT / "server"
SERVER_EXE = SERVER_DIR / "lychee-arena-server.exe"
OUR_CLIENT = ROOT / "basic_client.py"
THEIR_CLIENT = TEAMMATE_ROOT / "basic_client.py"

DEFAULT_PORT = 30002
DEFAULT_SEED = "20260618"
OUR_PLAYER_ID = 1001
THEIR_PLAYER_ID = 2002


def _cleanup_outputs() -> None:
    for name in ("replay.txt", "debug_replay.txt", "client_debug.txt", "data.csv", "log.txt"):
        path = SERVER_DIR / name
        if path.exists():
            path.unlink()


def _wait_for_data_csv(timeout_sec: int) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if (SERVER_DIR / "data.csv").is_file():
            return True
        time.sleep(1)
    return False


def _terminate_process(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _load_replay_scores(replay_path: Path) -> dict[int, dict]:
    frames: list[dict] = []
    for line in replay_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            frames.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not frames:
        return {}
    last = frames[-1]
    result: dict[int, dict] = {}
    for player in last.get("players") or []:
        pid = player.get("playerId")
        if pid is None:
            continue
        result[int(pid)] = {
            "name": player.get("name", "?"),
            "totalScore": int(player.get("totalScore", 0) or 0),
            "delivered": bool(player.get("delivered")),
            "verified": bool(player.get("verified")),
            "currentNodeId": player.get("currentNodeId"),
        }
    return result


def run_pvp_match(
    *,
    port: int = DEFAULT_PORT,
    seed: str = DEFAULT_SEED,
    round_timeout_ms: int = 80,
    wait_timeout_sec: int = 300,
) -> Path:
    if not SERVER_EXE.is_file():
        raise SystemExit(f"pvp match skipped: missing server {SERVER_EXE}")
    if not OUR_CLIENT.is_file():
        raise SystemExit(f"pvp match skipped: missing our client {OUR_CLIENT}")
    if not THEIR_CLIENT.is_file():
        raise SystemExit(f"pvp match skipped: missing teammate client {THEIR_CLIENT}")

    _cleanup_outputs()
    match_id = "pvp-local"
    server_cmd = [
        str(SERVER_EXE),
        "--mode",
        "client-debug",
        "--debug-visibility",
        "full",
        "--seed",
        seed,
        "--match-id",
        match_id,
        "-p",
        str(port),
        "-r",
        ".",
        "-a",
        str(round_timeout_ms),
        "-c",
        "30000",
        "-d",
        "30000",
    ]
    our_cmd = [
        sys.executable,
        str(OUR_CLIENT),
        "--player-id",
        str(OUR_PLAYER_ID),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--player-name",
        "our-python",
        "--version",
        "1.0",
    ]
    their_cmd = [
        sys.executable,
        str(THEIR_CLIENT),
        "--player-id",
        str(THEIR_PLAYER_ID),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--player-name",
        "teammate-python",
        "--version",
        "1.0",
    ]

    server_proc: subprocess.Popen | None = None
    our_proc: subprocess.Popen | None = None
    their_proc: subprocess.Popen | None = None
    try:
        print(
            f"pvp match: seed={seed} port={port} our={OUR_PLAYER_ID} vs teammate={THEIR_PLAYER_ID}",
            flush=True,
        )
        server_proc = subprocess.Popen(
            server_cmd,
            cwd=str(SERVER_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(2)
        our_proc = subprocess.Popen(
            our_cmd,
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.5)
        their_proc = subprocess.Popen(
            their_cmd,
            cwd=str(TEAMMATE_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if not _wait_for_data_csv(wait_timeout_sec):
            raise SystemExit(
                f"pvp match timed out after {wait_timeout_sec}s; see {SERVER_DIR / 'log.txt'}"
            )
    finally:
        _terminate_process(their_proc)
        _terminate_process(our_proc)
        _terminate_process(server_proc)

    replay_path = SERVER_DIR / "replay.txt"
    if not replay_path.is_file():
        raise SystemExit(f"pvp match finished without replay: {replay_path}")
    return replay_path


def main() -> None:
    replay_path = run_pvp_match()
    scores = _load_replay_scores(replay_path)
    our = scores.get(OUR_PLAYER_ID, {})
    theirs = scores.get(THEIR_PLAYER_ID, {})
    our_score = our.get("totalScore", 0)
    their_score = theirs.get("totalScore", 0)

    print(f"\n=== pvp replay: {replay_path} ===")
    print(
        f"  our ({OUR_PLAYER_ID}): score={our_score} delivered={our.get('delivered')} node={our.get('currentNodeId')}"
    )
    print(
        f"  teammate ({THEIR_PLAYER_ID}): score={their_score} delivered={theirs.get('delivered')} node={theirs.get('currentNodeId')}"
    )

    if our_score > their_score:
        print("  result: OUR WIN")
    elif our_score < their_score:
        print("  result: TEAMMATE WIN")
    else:
        print("  result: TIE")


if __name__ == "__main__":
    main()
