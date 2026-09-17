#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

./scripts/debug-up.sh

deadline=$((SECONDS + 360))
until curl -fsS http://127.0.0.1:6082/api/v1/emulator/status | python3 -c 'import json,sys; assert json.load(sys.stdin)["booted"] is True'; do
  (( SECONDS < deadline )) || { echo "Emulator status did not become ready" >&2; exit 1; }
  sleep 2
done

curl -fsS http://127.0.0.1:6082/ | grep -qi '<html'

deadline=$((SECONDS + 120))
until curl -fsS http://127.0.0.1:8092/api/v1/health | python3 -c 'import json,sys; assert json.load(sys.stdin)["status"] == "ok"'; do
  (( SECONDS < deadline )) || { echo "Worker Control API did not become ready" >&2; exit 1; }
  sleep 2
done

# The debug page's live view is a multipart/x-mixed-replace PNG stream
# (screen.mjpeg), not the official image's legacy WebRTC video service (that
# service never returns an SDP answer or ICE candidates for a real browser
# peer connection - verified by direct gRPC probing; see README.md "Known
# issues"). Read the first frame and require real PNG bytes, so a routing or
# gateway regression that would otherwise render as a silent blank page fails
# this test loudly instead.
frame_file="$(mktemp)"
trap 'rm -f "$frame_file"' EXIT
# --max-time bounds this: screen.mjpeg is an infinite stream, so curl is
# expected to exit 28 (timeout) here, not 0; only fail on other exit codes.
set +e
curl -fsS --max-time 3 -o "$frame_file" http://127.0.0.1:6082/api/v1/emulator/screen.mjpeg
curl_rc=$?
set -e
if [ "$curl_rc" -ne 0 ] && [ "$curl_rc" -ne 28 ]; then
  echo "screen.mjpeg request failed (curl exit $curl_rc)" >&2
  exit 1
fi
grep -qa 'Content-Type: image/png' "$frame_file" || { echo "screen.mjpeg did not return a PNG frame" >&2; exit 1; }

# Hardware key injection (HOME) should be accepted by the gateway.
key_status="$(curl -fsS -X POST -H 'Content-Type: application/json' -d '{"key":"GoHome"}' http://127.0.0.1:6082/api/v1/emulator/key | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')"
[ "$key_status" = "sent" ] || { echo "Hardware key injection did not report 'sent'" >&2; exit 1; }

# Mouse/tap injection (a down+up pair, as the frontend sends for a click).
mouse_status="$(curl -fsS -X POST -H 'Content-Type: application/json' -d '{"x":50,"y":50,"buttons":1}' http://127.0.0.1:6082/api/v1/emulator/mouse | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')"
[ "$mouse_status" = "sent" ] || { echo "Mouse-down injection did not report 'sent'" >&2; exit 1; }
mouse_status="$(curl -fsS -X POST -H 'Content-Type: application/json' -d '{"x":50,"y":50,"buttons":0}' http://127.0.0.1:6082/api/v1/emulator/mouse | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')"
[ "$mouse_status" = "sent" ] || { echo "Mouse-up injection did not report 'sent'" >&2; exit 1; }

deadline=$((SECONDS + 360))
while :; do
  summary="$(find artifacts/google-android-test-001/android-example -name summary.json -type f -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -1 | cut -d' ' -f2-)"
  if [[ -n "$summary" ]] && python3 -c 'import json,sys; data=json.load(open(sys.argv[1])); raise SystemExit(0 if data.get("status") == "PASS" else 1)' "$summary"; then
    python3 -c 'import json,sys; data=json.load(open(sys.argv[1])); assert data["status"] == "PASS"; assert data.get("device", {}).get("serial") == "google-emulator:5555"' "$summary"
    break
  fi
  (( SECONDS < deadline )) || { docker compose --profile debug logs --tail=200 worker-google-android-debug; echo "Debug scenario did not pass" >&2; exit 1; }
  sleep 2
done

echo "Debug E2E passed: $summary"
