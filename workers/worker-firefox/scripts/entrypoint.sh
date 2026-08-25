#!/usr/bin/env bash
set -euo pipefail

HELPER_PIDS=()
APP_PID=""
STOP_REQUESTED="false"

cleanup_helpers() {
  if ((${#HELPER_PIDS[@]})); then
    for pid in "${HELPER_PIDS[@]}"; do
      kill -TERM "$pid" >/dev/null 2>&1 || true
    done
    for pid in "${HELPER_PIDS[@]}"; do
      wait "$pid" >/dev/null 2>&1 || true
    done
  fi
}

handle_signal() {
  local sig="$1"
  trap '' INT TERM
  if [[ -n "$APP_PID" ]] && kill -0 "$APP_PID" >/dev/null 2>&1; then
    kill -s "$sig" "$APP_PID" >/dev/null 2>&1 || true
    set +e
    wait "$APP_PID"
    local app_status=$?
    set -e
    cleanup_helpers
    trap - EXIT
    if [[ "$app_status" -ne 0 ]]; then
      echo "[entrypoint] application exit code during requested shutdown: $app_status" >&2
    fi
    exit 0
  fi
  cleanup_helpers
  trap - EXIT
  exit 0
}

trap 'handle_signal INT' INT
trap 'handle_signal TERM' TERM
trap 'cleanup_helpers' EXIT

resolve_debug_display() {
  python - <<'PY'
import os
from pathlib import Path

from app.config_loader import load_runtime_config

system_config = os.environ.get("WORKER_SYSTEM_CONFIG")
profile = os.environ.get("WORKER_PROFILE")
cfg = {}
layout = {}

if system_config and profile:
    try:
        cfg, layout = load_runtime_config(profile, system_config)
    except Exception as exc:
        print(f"[debug-config-warning] {exc}", file=__import__("sys").stderr)

dd = cfg.get("browser", {}).get("debug_display", {}) or {}
fallback = dd.get("fallback", {}) or {}
width = int(fallback.get("width", 1920))
height = int(fallback.get("height", 1080))
depth = int(dd.get("depth", 24))
size_mode = str(dd.get("size", "identity")).lower()

if size_mode == "identity":
    identity = cfg.get("identity")
    identities_dir = layout.get("identities_dir")
    if identity and identities_dir:
        profile_cfg = Path(identities_dir) / str(identity) / "config.json"
        if profile_cfg.exists():
            try:
                import json
                pcfg = json.loads(profile_cfg.read_text())
                window = pcfg.get("fingerprint", {}).get("window")
                if isinstance(window, dict):
                    width = int(window.get("width", width))
                    height = int(window.get("height", height))
            except Exception:
                pass
elif size_mode == "custom":
    width = int(dd.get("width", width))
    height = int(dd.get("height", height))

position = dd.get("position", {}) or {}
x = int(position.get("x", 0))
y = int(position.get("y", 0))
window_mode = str(dd.get("window", "maximized")).lower()
novnc_scaling = str(dd.get("novnc_scaling", "local")).lower()

print(width)
print(height)
print(depth)
print(window_mode)
print(x)
print(y)
print(novnc_scaling)
PY
}

resolve_x11_recording() {
  python - <<'PY'
import os

from app.browser import uses_x11_recording
from app.config_loader import load_runtime_config

system_config = os.environ.get("WORKER_SYSTEM_CONFIG")
profile = os.environ.get("WORKER_PROFILE")
enabled = False
if system_config and profile:
    try:
        cfg, _ = load_runtime_config(profile, system_config)
        enabled = uses_x11_recording(cfg)
    except Exception as exc:
        print(f"[recording-config-warning] {exc}", file=__import__("sys").stderr)
print("true" if enabled else "false")
PY
}

write_openbox_config() {
  local window_mode="$1"
  local x="$2"
  local y="$3"
  mkdir -p /root/.config/openbox

  local maximize_xml=""
  if [[ "$window_mode" == "maximized" ]]; then
    maximize_xml='      <maximized>yes</maximized>'
  fi

  cat >/root/.config/openbox/rc.xml <<EOF2
<?xml version="1.0" encoding="UTF-8"?>
<openbox_config xmlns="http://openbox.org/3.4/rc">
  <placement>
    <policy>Smart</policy>
    <center>no</center>
    <monitor>Primary</monitor>
  </placement>
  <applications>
    <application class="*">
      <position force="yes">
        <x>${x}</x>
        <y>${y}</y>
        <monitor>1</monitor>
      </position>
${maximize_xml}
    </application>
  </applications>
</openbox_config>
EOF2
}

X11_RECORDING_ENABLED="$(resolve_x11_recording)"
if [[ "${ENABLE_NOVNC:-false}" == "true" || "$X11_RECORDING_ENABLED" == "true" ]]; then
  export DISPLAY="${DISPLAY:-:99}"

  mapfile -t DEBUG_VALUES < <(resolve_debug_display "$@")
  DEBUG_WIDTH="${DEBUG_VALUES[0]:-1920}"
  DEBUG_HEIGHT="${DEBUG_VALUES[1]:-1080}"
  DEBUG_DEPTH="${DEBUG_VALUES[2]:-24}"
  DEBUG_WINDOW_MODE="${DEBUG_VALUES[3]:-maximized}"
  DEBUG_POS_X="${DEBUG_VALUES[4]:-0}"
  DEBUG_POS_Y="${DEBUG_VALUES[5]:-0}"
  DEBUG_NOVNC_SCALING="${DEBUG_VALUES[6]:-local}"
  DEBUG_DISPLAY_SIZE="${DEBUG_WIDTH}x${DEBUG_HEIGHT}x${DEBUG_DEPTH}"
  export WORKER_DEBUG_DISPLAY_SIZE="${DEBUG_WIDTH}x${DEBUG_HEIGHT}"

  write_openbox_config "$DEBUG_WINDOW_MODE" "$DEBUG_POS_X" "$DEBUG_POS_Y"

  Xvfb "$DISPLAY" -screen 0 "$DEBUG_DISPLAY_SIZE" -nolisten tcp -ac >/tmp/xvfb.log 2>&1 &
  XVFB_PID=$!
  HELPER_PIDS+=("$XVFB_PID")
  echo "[debug] Waiting for Xvfb on $DISPLAY..."

  xvfb_ready=false
  for _ in $(seq 1 100); do
    if xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then
      xvfb_ready=true
      break
    fi
    if ! kill -0 "$XVFB_PID" >/dev/null 2>&1; then
      break
    fi
    sleep 0.1
  done

  if [[ "$xvfb_ready" != "true" ]]; then
    echo "[debug] ERROR: Xvfb failed to become ready on $DISPLAY" >&2
    cat /tmp/xvfb.log >&2 || true
    exit 1
  fi
  echo "[debug] Xvfb is ready on $DISPLAY ($DEBUG_DISPLAY_SIZE)"
  echo "[debug] Window placement: mode=$DEBUG_WINDOW_MODE position=${DEBUG_POS_X},${DEBUG_POS_Y}"

  openbox --config-file /root/.config/openbox/rc.xml >/tmp/openbox.log 2>&1 &
  HELPER_PIDS+=("$!")
  if [[ "${ENABLE_NOVNC:-false}" == "true" ]]; then
    VNC_ACCESS_ARGS=()
    if [[ "${NOVNC_VIEW_ONLY:-false}" == "true" ]]; then
      VNC_ACCESS_ARGS+=("-viewonly")
    fi
    x11vnc -display "$DISPLAY" -forever -shared -nopw "${VNC_ACCESS_ARGS[@]}" -rfbport "${VNC_PORT:-5900}" >/tmp/x11vnc.log 2>&1 &
    HELPER_PIDS+=("$!")
    websockify --web=/usr/share/novnc/ "${NOVNC_PORT:-6080}" localhost:"${VNC_PORT:-5900}" >/tmp/novnc.log 2>&1 &
    HELPER_PIDS+=("$!")

    novnc_ready=false
    for _ in $(seq 1 100); do
      if curl -fsS "http://127.0.0.1:${NOVNC_PORT:-6080}/vnc.html" >/dev/null 2>&1; then
        novnc_ready=true
        break
      fi
      sleep 0.1
    done

    if [[ "$novnc_ready" != "true" ]]; then
      echo "[debug] ERROR: noVNC failed to become ready on port ${NOVNC_PORT:-6080}" >&2
      cat /tmp/novnc.log >&2 || true
      exit 1
    fi

    if [[ "$DEBUG_NOVNC_SCALING" == "local" ]]; then
      NOVNC_URL="http://<docker-host>:${NOVNC_PORT:-6080}/vnc.html?autoconnect=true&resize=scale"
    else
      NOVNC_URL="http://<docker-host>:${NOVNC_PORT:-6080}/vnc.html?autoconnect=true&resize=off"
    fi
    echo "[debug] noVNC ready: $NOVNC_URL"
  fi
fi

"$@" &
APP_PID=$!

set +e
wait "$APP_PID"
status=$?
set -e

exit "$status"
