#!/bin/sh
set -eu

action="${1:-session}"

# agy SessionStart hook contract expects `{}` on stdout. Always ensure `{}` is output.
cleanup() {
  printf "{}\n"
}
trap cleanup EXIT

[ "${HERDR_ENV:-}" = "1" ] || exit 0
[ -n "${HERDR_SOCKET_PATH:-}" ] || exit 0
[ -n "${HERDR_PANE_ID:-}" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

HERDR_ACTION="$action" python3 - <<'PY'
import json
import os
import random
import socket
import sys
import time

pane_id = os.environ.get("HERDR_PANE_ID")
socket_path = os.environ.get("HERDR_SOCKET_PATH")
if not pane_id or not socket_path:
    raise SystemExit(0)

hook_input = {}
try:
    if not sys.stdin.isatty():
        raw = sys.stdin.read()
        if raw.strip():
            hook_input = json.loads(raw)
except Exception:
    hook_input = {}

session_id = hook_input.get("conversationId") or hook_input.get("session_id")
transcript_path = hook_input.get("transcriptPath") or hook_input.get("transcript_path")

if not session_id:
    session_id = f"agy-session-{int(time.time())}"

source = "herdr:agy"
request_id = f"{source}:{int(time.time() * 1000)}:{random.randrange(1_000_000):06d}"
report_seq = time.time_ns()

params = {
    "pane_id": pane_id,
    "source": source,
    "agent": "agy",
    "seq": report_seq,
    "agent_session_id": str(session_id),
}
if transcript_path:
    params["agent_session_path"] = str(transcript_path)

request = {
    "id": request_id,
    "method": "pane.report_agent_session",
    "params": params,
}

try:
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(0.5)
    client.connect(socket_path)
    client.sendall((json.dumps(request) + "\n").encode())
    try:
        client.recv(4096)
    except Exception:
        pass
    client.close()
except Exception:
    pass
PY
