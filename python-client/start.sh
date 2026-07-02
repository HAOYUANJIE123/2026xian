#!/bin/bash
set -e

if [ "$#" -ne 3 ]; then
  echo "Usage: $0 <playerId> <host> <port>"
  exit 1
fi

PLAYER_ID="$1"
HOST="$2"
PORT="$3"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

exec python3 basic_client.py \
  --player-id="${PLAYER_ID}" \
  --host="${HOST}" \
  --port="${PORT}" \
  --player-name="python-bot" \
  --version="1.0"
