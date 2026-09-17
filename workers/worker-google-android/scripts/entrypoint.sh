#!/bin/sh
set -eu
serial="${WORKER_GOOGLE_ANDROID_ADB_SERIAL:-google-emulator:5555}"
deadline=$(( $(date +%s) + 180 ))
until adb connect "$serial" >/dev/null 2>&1 && [ "$(adb -s "$serial" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; do
  [ "$(date +%s)" -lt "$deadline" ] || { echo "Google Android emulator ADB boot timeout" >&2; exit 1; }
  sleep 2
done
# Disable Chrome's first-run experience so a later ACTION_VIEW intent opens
# the requested page directly instead of Chrome's FirstRunActivity wizard.
# This is a verified, unconditional fix; it does not address the separate,
# environment-sensitive Chrome cold-start reliability issue documented in
# CHANGELOG.md/README.md (occasional SIGTRAP crash or ANR on this emulator
# image's first real launch, independent of this flag).
adb -s "$serial" shell "echo chrome --disable-fre --no-default-browser-check --no-first-run > /data/local/tmp/chrome-command-line" >/dev/null 2>&1 || true
appium --address 127.0.0.1 --port 4723 --base-path / --log-timestamp &
appium_pid=$!
trap 'kill "$appium_pid" 2>/dev/null || true' EXIT INT TERM
exec "$@"
