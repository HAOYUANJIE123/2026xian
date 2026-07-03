#!/usr/bin/env python3
"""Run a headless local Demo match and validate the result."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from replay_gate import audit_outcome

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
DEBUG_ROOT = PROJECT_ROOT / "比赛资料" / "比赛资料" / "调测包及赛题相关文档_V1" / "调测"
SERVER_DIR = DEBUG_ROOT / "server"
DEMO_DIR = DEBUG_ROOT / "demo"
SERVER_EXE = SERVER_DIR / "lychee-arena-server.exe"
DEMO_EXE = DEMO_DIR / "l1-demo.exe"
CLIENT_SCRIPT = ROOT / "basic_client.py"

DEFAULT_PORT = 30001
DEFAULT_SEED = "20260618"
DEFAULT_PLAYER_ID = 1001
MIN_SCORE = 700


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


def run_local_match(
    *,
    port: int = DEFAULT_PORT,
    seed: str = DEFAULT_SEED,
    round_timeout_ms: int = 80,
    wait_timeout_sec: int = 240,
) -> Path:
    if not SERVER_EXE.is_file():
        raise SystemExit(f"local match skipped: missing server {SERVER_EXE}")
    if not DEMO_EXE.is_file():
        raise SystemExit(f"local match skipped: missing demo {DEMO_EXE}")
    if not CLIENT_SCRIPT.is_file():
        raise SystemExit(f"local match skipped: missing client {CLIENT_SCRIPT}")

    _cleanup_outputs()
    match_id = "validate-local"
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
    client_cmd = [
        sys.executable,
        str(CLIENT_SCRIPT),
        "--player-id",
        str(DEFAULT_PLAYER_ID),
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--player-name",
        "python-bot",
        "--version",
        "1.0",
    ]
    demo_cmd = [
        str(DEMO_EXE),
        f"--backend-host=127.0.0.1",
        f"--backend-port={port}",
        f"--player-id=2002",
        f"--player-name=demo-l1",
    ]

    server_proc: subprocess.Popen | None = None
    client_proc: subprocess.Popen | None = None
    demo_proc: subprocess.Popen | None = None
    try:
        print(
            f"local match: seed={seed} port={port} round_timeout_ms={round_timeout_ms}",
            flush=True,
        )
        server_proc = subprocess.Popen(
            server_cmd,
            cwd=str(SERVER_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(2)
        client_proc = subprocess.Popen(
            client_cmd,
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.5)
        demo_proc = subprocess.Popen(
            demo_cmd,
            cwd=str(DEMO_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if not _wait_for_data_csv(wait_timeout_sec):
            raise SystemExit(
                f"local match timed out after {wait_timeout_sec}s; see {SERVER_DIR / 'log.txt'}"
            )
    finally:
        _terminate_process(demo_proc)
        _terminate_process(client_proc)
        _terminate_process(server_proc)

    replay_path = SERVER_DIR / "replay.txt"
    if not replay_path.is_file():
        raise SystemExit(f"local match finished without replay: {replay_path}")
    return replay_path


def validate_local_match(**kwargs) -> None:
    replay_path = run_local_match(**kwargs)
    audit = audit_outcome(
        replay_path,
        DEFAULT_PLAYER_ID,
        require_delivery=True,
        min_score=MIN_SCORE,
    )
    print(f"\n=== local demo replay: {replay_path.name} ===")
    print(f"  score={audit.total_score} delivered={audit.delivered}")
    print(f"  rejects: {dict(audit.rejects)}")
    if audit.issues:
        for issue in audit.issues:
            print(f"  ISSUE: {issue}")
        raise SystemExit("local match validation failed")
    print("  ok")


def main() -> None:
    validate_local_match()


if __name__ == "__main__":
    main()
