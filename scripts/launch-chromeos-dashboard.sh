#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/launch-chromeos-dashboard.sh [--check]

Ensure the local VelaCare dashboard is ready, then open it in the host browser.
--check starts/reuses the server and checks readiness without opening a browser.

Environment:
  VELACARE_WORKSPACE          Workspace directory (default: <repo>/agentic-space)
  VELACARE_BIND_HOST          Server bind address (default: 0.0.0.0)
  VELACARE_PORT               Server port (default: 8050)
  VELACARE_BASE_PATH          URL prefix (default: /)
  VELACARE_URL                Browser URL (default: http://localhost:<port><base-path>)
  VELACARE_STARTUP_TIMEOUT    Readiness timeout in seconds (default: 90)
  VELACARE_STATE_DIR          PID/log directory override
USAGE
}

check_only=false
case "${1:-}" in
  "") ;;
  --check) check_only=true ;;
  --help|-h) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac
if [[ $# -gt 1 ]]; then
  usage >&2
  exit 2
fi

script_path="$(readlink -f -- "${BASH_SOURCE[0]}")"
repo_root="$(cd -- "$(dirname -- "$script_path")/.." && pwd -P)"
workspace="${VELACARE_WORKSPACE:-$repo_root/agentic-space}"
if [[ "$workspace" != /* ]]; then workspace="$repo_root/$workspace"; fi
bind_host="${VELACARE_BIND_HOST:-0.0.0.0}"
port="${VELACARE_PORT:-8050}"
base_path="${VELACARE_BASE_PATH:-/}"
startup_timeout="${VELACARE_STARTUP_TIMEOUT:-90}"
health_host="${VELACARE_HEALTH_HOST:-127.0.0.1}"
health_scheme="${VELACARE_HEALTH_SCHEME:-http}"
state_dir="${VELACARE_STATE_DIR:-${XDG_STATE_HOME:-${HOME:?HOME must be set}/.local/state}/velacare}"
pid_file="$state_dir/dashboard-$port.pid"
log_file="$state_dir/dashboard-$port.log"
lock_file="$state_dir/dashboard-$port.lock"

if [[ ! "$port" =~ ^[0-9]+$ ]] || (( port < 1 || port > 65535 )); then
  printf 'VelaCare launcher: VELACARE_PORT must be between 1 and 65535.\n' >&2
  exit 2
fi
if [[ ! "$startup_timeout" =~ ^[0-9]+$ ]] || (( startup_timeout < 1 )); then
  printf 'VelaCare launcher: VELACARE_STARTUP_TIMEOUT must be a positive number of seconds.\n' >&2
  exit 2
fi
if [[ "$base_path" != /* ]]; then base_path="/$base_path"; fi
if [[ "$base_path" != */ ]]; then base_path="$base_path/"; fi
if [[ "$base_path" == *".."* || "$base_path" == *"?"* || "$base_path" == *"#"* ]]; then
  printf 'VelaCare launcher: VELACARE_BASE_PATH must be a simple URL path prefix.\n' >&2
  exit 2
fi
base_prefix="${base_path%/}"
health_root="$health_scheme://$health_host:$port$base_prefix"
live_url="$health_root/health/live"
ready_url="$health_root/health/ready"
browser_url="${VELACARE_URL:-http://localhost:$port$base_path}"
started_pid=""

if [[ ! -x "$repo_root/run-dashboard" ]]; then
  printf 'VelaCare launcher: missing executable %s/run-dashboard\n' "$repo_root" >&2
  exit 1
fi
for command_name in python3 uv flock setsid; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'VelaCare launcher: required command not found: %s\n' "$command_name" >&2
    exit 1
  fi
done

mkdir -p -m 0700 "$state_dir"
chmod 0700 "$state_dir"
umask 077
exec 9>"$lock_file"
flock -x 9

notify_failure() {
  if [[ "$check_only" == false ]] && command -v notify-send >/dev/null 2>&1 && { [[ -n "${DISPLAY:-}" ]] || [[ -n "${WAYLAND_DISPLAY:-}" ]]; }; then
    notify-send --app-name="VelaCare Data Explorer" "VelaCare could not start" "$1" >/dev/null 2>&1 || true
  fi
}

stop_owned_server() {
  [[ -n "$started_pid" ]] || return 0
  if kill -0 "$started_pid" 2>/dev/null; then
    local process_group
    process_group="$(ps -o pgid= -p "$started_pid" 2>/dev/null | tr -d ' ' || true)"
    if [[ "$process_group" == "$started_pid" ]]; then
      kill -TERM -- "-$started_pid" 2>/dev/null || true
    else
      kill -TERM "$started_pid" 2>/dev/null || true
    fi
    for _ in 1 2 3 4 5; do
      kill -0 "$started_pid" 2>/dev/null || break
      sleep 1
    done
    if kill -0 "$started_pid" 2>/dev/null && [[ "$process_group" == "$started_pid" ]]; then
      kill -KILL -- "-$started_pid" 2>/dev/null || true
    fi
    wait "$started_pid" 2>/dev/null || true
  fi
  if [[ -f "$pid_file" ]] && [[ "$(cat "$pid_file" 2>/dev/null || true)" == "$started_pid" ]]; then
    rm -f -- "$pid_file"
  fi
  started_pid=""
}

fail() {
  printf 'VelaCare launcher: %s\n' "$1" >&2
  if [[ -n "$started_pid" ]]; then
    printf 'Startup log: %s\n' "$log_file" >&2
    if [[ -f "$log_file" ]]; then tail -n 20 "$log_file" >&2 || true; fi
    stop_owned_server
  fi
  notify_failure "$1"
  exit 1
}

probe() {
  python3 - "$1" <<'PY'
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    with urlopen(Request(sys.argv[1], headers={"Accept": "application/json"}), timeout=1.5) as response:
        code, body = response.status, response.read(65536)
except HTTPError as error:
    code, body = error.code, error.read(65536)
except (URLError, TimeoutError, OSError):
    raise SystemExit(2)
try:
    payload = json.loads(body.decode("utf-8"))
except (UnicodeDecodeError, json.JSONDecodeError):
    payload = {}
dashboard = payload.get("dashboard") if isinstance(payload, dict) else {}
if not isinstance(dashboard, dict):
    dashboard = {}
print("|".join((str(payload.get("service", "")), str(payload.get("status", "")), str(code), str(dashboard.get("status", "")))))
PY
}

port_is_open() {
  python3 - "$health_host" "$port" <<'PY'
import socket
import sys
try:
    with socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=0.3):
        raise SystemExit(0)
except OSError:
    raise SystemExit(1)
PY
}

read_probe_fields() {
  IFS='|' read -r probe_service probe_status probe_code probe_dashboard <<< "$1"
}

server_pid_alive() {
  [[ -f "$pid_file" ]] || return 1
  local candidate
  candidate="$(cat "$pid_file" 2>/dev/null || true)"
  [[ "$candidate" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$candidate" 2>/dev/null
}

if [[ -f "$pid_file" ]] && ! server_pid_alive; then
  rm -f -- "$pid_file"
fi

existing_server=false
if live_result="$(probe "$live_url")"; then
  read_probe_fields "$live_result"
  if [[ "$probe_service" != "velacare-dashboard" || "$probe_status" != "live" ]]; then
    fail "Port $port is already serving an unrelated application; no process was started or stopped."
  fi
  existing_server=true
elif port_is_open; then
  fail "Port $port is occupied by a service that does not identify itself as VelaCare; no process was stopped."
fi

if [[ "$existing_server" == false ]]; then
  printf 'Starting VelaCare Data Explorer on %s:%s (workspace %s)\n' "$bind_host" "$port" "$workspace" >> "$log_file"
  cd "$repo_root"
  setsid "$repo_root/run-dashboard" --workspace "$workspace" --host "$bind_host" --port "$port" --base-path "$base_path" 9>&- >> "$log_file" 2>&1 </dev/null &
  started_pid=$!
  pid_tmp="$pid_file.tmp.$$"
  printf '%s\n' "$started_pid" > "$pid_tmp"
  mv -f -- "$pid_tmp" "$pid_file"
else
  printf 'Reusing existing VelaCare dashboard on %s\n' "$browser_url"
fi

ready=false
deadline=$((SECONDS + startup_timeout))
while (( SECONDS < deadline )); do
  if ready_result="$(probe "$ready_url")"; then
    read_probe_fields "$ready_result"
    if [[ "$probe_service" == "velacare-dashboard" && "$probe_code" == "200" && "$probe_status" == "ready" && "$probe_dashboard" == "ready" ]]; then
      ready=true
      break
    fi
    if [[ "$probe_service" == "velacare-dashboard" && "$probe_status" == "unavailable" ]]; then
      fail "The VelaCare process is running but cannot access its configured workspace. Check VELACARE_WORKSPACE."
    fi
    if [[ "$probe_service" != "velacare-dashboard" && "$existing_server" == true ]]; then
      fail "The existing service on port $port is not a ready VelaCare dashboard."
    fi
  elif [[ "$existing_server" == true ]] && port_is_open; then
    fail "The existing service on port $port stopped identifying itself as VelaCare."
  fi

  if [[ -n "$started_pid" ]] && ! kill -0 "$started_pid" 2>/dev/null; then
    fail "The dashboard process exited before readiness."
  fi
  sleep 1
done

if [[ "$ready" == false ]]; then
  fail "Dashboard readiness timed out after ${startup_timeout}s."
fi
started_pid=""

printf 'VelaCare Data Explorer is ready at %s\n' "$browser_url"
if [[ "$check_only" == true ]]; then
  printf 'Check complete; no browser was opened.\n'
  exit 0
fi
if ! command -v xdg-open >/dev/null 2>&1; then
  fail "Dashboard is ready at $browser_url, but xdg-open is unavailable. Install the desktop URL opener or use --check."
fi

open_marker="$state_dir/last-browser-open-$port"
now="$(date +%s)"
last_open="$(cat "$open_marker" 2>/dev/null || printf '0')"
if [[ "$last_open" =~ ^[0-9]+$ ]] && (( now - last_open < 5 )); then
  printf 'A browser launch was just requested; skipped opening a duplicate tab.\n'
else
  printf '%s\n' "$now" > "$open_marker"
  nohup xdg-open "$browser_url" >> "$log_file" 2>&1 </dev/null &
fi
