#!/usr/bin/env bash
set -euo pipefail

HOST="${1:-127.0.0.1}"
PORT="${2:-7860}"
BASE_URL="http://${HOST}:${PORT}"

REQ1="/runs/{run_id}/invocations"
REQ2="/runs/{run_id}/io_graph"

say() {
  printf '%s\n' "$*"
}

fail() {
  local reason="$1"
  say "[dashboard-contract] ERROR: ${reason}"
  say "[dashboard-contract] endpoint: ${BASE_URL}"
  say "[dashboard-contract] required routes: ${REQ1}, ${REQ2}"
  say ""

  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids="$(lsof -tiTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null | tr '\n' ' ' | xargs)"
    if [[ -n "${pids}" ]]; then
      say "[dashboard-contract] listeners on :${PORT}: ${pids}"
      ps -fp ${pids} 2>/dev/null || true
      if ps -fp ${pids} 2>/dev/null | grep -q '/Documents/operad'; then
        say ""
        say "[dashboard-contract] hint: found a dashboard process from /Documents/operad; this often causes API mismatch with this workspace."
      fi
    else
      say "[dashboard-contract] no listener detected on :${PORT}."
    fi
  else
    say "[dashboard-contract] lsof not available; cannot list listener PID."
  fi

  say ""
  say "[dashboard-contract] fix commands:"
  say "  1) stop conflicting process (example): kill <pid>"
  say "  2) start dashboard from this workspace: make dashboard"
  say "  3) re-run your command (example-observed/demo)"
  exit 1
}

if ! curl -fsS "${BASE_URL}/api/manifest" >/dev/null; then
  fail "cannot reach ${BASE_URL}/api/manifest"
fi

openapi_json="$(curl -fsS "${BASE_URL}/openapi.json" 2>/dev/null || true)"
if [[ -z "${openapi_json}" ]]; then
  fail "cannot fetch ${BASE_URL}/openapi.json"
fi

if ! python3 - <<'PY' "${openapi_json}" "${REQ1}" "${REQ2}"; then
import json
import sys

raw = sys.argv[1]
req = {sys.argv[2], sys.argv[3]}
try:
    doc = json.loads(raw)
except Exception:
    sys.exit(2)
paths = set((doc.get("paths") or {}).keys())
missing = sorted(req - paths)
if missing:
    print("missing:" + ",".join(missing))
    sys.exit(1)
sys.exit(0)
PY
  reason="incompatible dashboard API contract"
  missing_msg="$(python3 - <<'PY' "${openapi_json}" "${REQ1}" "${REQ2}" 2>/dev/null || true
import json
import sys
raw = sys.argv[1]
req = {sys.argv[2], sys.argv[3]}
try:
    doc = json.loads(raw)
except Exception:
    print("unable to parse /openapi.json")
    sys.exit(0)
paths = set((doc.get("paths") or {}).keys())
missing = sorted(req - paths)
if missing:
    print("missing routes: " + ", ".join(missing))
PY
)"
  if [[ -n "${missing_msg}" ]]; then
    reason="${reason} (${missing_msg})"
  fi
  fail "${reason}"
fi

say "[dashboard-contract] ok: ${BASE_URL} exposes required agent-view routes."
