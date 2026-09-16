#!/usr/bin/env bash
set -euo pipefail
BASE_PID=""; APP_PID=""
cleanup(){
  if [[ -n "$APP_PID" ]] && kill -0 "$APP_PID" 2>/dev/null; then kill -TERM "$APP_PID" 2>/dev/null || true; wait "$APP_PID" 2>/dev/null || true; fi
  if [[ -n "$BASE_PID" ]] && kill -0 "$BASE_PID" 2>/dev/null; then kill -TERM "$BASE_PID" 2>/dev/null || true; wait "$BASE_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM

# Keep Docker-Android responsible for emulator, VNC and Appium lifecycle.
export APPIUM="${APPIUM:-true}"
export WEB_VNC="${WEB_VNC:-false}"

# Resolve device profile and emulator-level proxy from the same worker profile
# used by app.main. Explicit environment variables still win, which is handy
# for one-off autonomous CLI runs.
if [[ -n "${WORKER_SYSTEM_CONFIG:-}" && -n "${WORKER_PROFILE:-}" ]]; then
  mapfile -t STARTUP_VALUES < <(python3 - <<'PYCFG'
import os
from urllib.parse import quote, urlsplit, urlunsplit
from app.config_loader import load_runtime_config

cfg, _ = load_runtime_config(os.environ["WORKER_PROFILE"], os.environ["WORKER_SYSTEM_CONFIG"])
android = cfg.get("android", {}) or {}
print(str(android.get("emulator_device", "Samsung Galaxy S10")))
proxy = cfg.get("proxy", {}) or {}
proxy_url = ""
if proxy.get("enabled") and proxy.get("server"):
    raw = str(proxy["server"])
    if "://" not in raw:
        raw = "http://" + raw
    u = urlsplit(raw)
    host = u.hostname or ""
    port = f":{u.port}" if u.port else ""
    user = proxy.get("username")
    password = proxy.get("password")
    auth = ""
    if user:
        auth = quote(str(user), safe="")
        if password is not None:
            auth += ":" + quote(str(password), safe="")
        auth += "@"
    proxy_url = urlunsplit((u.scheme or "http", auth + host + port, "", "", ""))
print(proxy_url)
PYCFG
  )
  : "${EMULATOR_DEVICE:=${STARTUP_VALUES[0]:-Samsung Galaxy S10}}"
  if [[ -n "${STARTUP_VALUES[1]:-}" && "${EMULATOR_ADDITIONAL_ARGS:-}" != *"-http-proxy"* ]]; then
    export EMULATOR_ADDITIONAL_ARGS="${EMULATOR_ADDITIONAL_ARGS:-} -http-proxy ${STARTUP_VALUES[1]}"
  fi
fi
export EMULATOR_DEVICE="${EMULATOR_DEVICE:-Samsung Galaxy S10}"

echo "[worker-android] emulator device: ${EMULATOR_DEVICE}"
if [[ "${EMULATOR_ADDITIONAL_ARGS:-}" == *"-http-proxy"* ]]; then echo "[worker-android] emulator proxy: configured"; fi

/home/androidusr/docker-android/mixins/scripts/run.sh &
BASE_PID=$!

# Do not start the worker API before adb exists; the Python worker itself waits
# for Android boot_completed and then creates the UiAutomator2 session.
for _ in $(seq 1 120); do
  if adb devices 2>/dev/null | grep -q 'emulator-'; then break; fi
  if ! kill -0 "$BASE_PID" 2>/dev/null; then echo "[entrypoint] docker-android runtime exited early" >&2; wait "$BASE_PID"; exit $?; fi
  sleep 1
done

"$@" & APP_PID=$!
set +e
wait "$APP_PID"; status=$?
set -e
exit "$status"
