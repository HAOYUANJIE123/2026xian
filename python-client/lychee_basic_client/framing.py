import json
import re
import socket
from typing import Any

MAX_BODY = 99999

# V4 server may emit Java-style maps with unquoted numeric keys: {1001:"CLAIM_TASK"}
_SERVER_JSON_KEY_RE = re.compile(r"(?<=[\{,])(\d+)(?=:)")


def loads_server_json(body: bytes | str) -> Any:
    text = body.decode("utf-8") if isinstance(body, bytes) else body
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(_SERVER_JSON_KEY_RE.sub(r'"\1"', text))


def read_exact(sock: socket.socket, length: int) -> bytes:
    chunks = []
    remaining = length
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise EOFError("connection closed")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_frame(sock: socket.socket) -> dict:
    prefix = read_exact(sock, 5)
    try:
        length = int(prefix.decode("ascii"))
    except ValueError as exc:
        raise ValueError(f"invalid frame prefix: {prefix!r}") from exc
    if length < 0 or length > MAX_BODY:
        raise ValueError(f"invalid frame length: {length}")
    body = read_exact(sock, length)
    return loads_server_json(body)


def write_frame(sock: socket.socket, message: dict[str, Any]) -> None:
    body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(body) > MAX_BODY:
        raise ValueError(f"message too large: {len(body)}")
    sock.sendall(f"{len(body):05d}".encode("ascii") + body)
