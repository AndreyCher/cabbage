#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root_dir"

./scripts/debug-up.sh

deadline=$((SECONDS + 360))
until curl -fsS http://127.0.0.1:6082/api/v1/emulator/status | python3 -c 'import json,sys; assert json.load(sys.stdin)["booted"] is True'; do
  (( SECONDS < deadline )) || { echo "WebRTC status did not become ready" >&2; exit 1; }
  sleep 2
done

curl -fsS http://127.0.0.1:6082/ | grep -qi '<html'
curl -fsS http://127.0.0.1:8092/api/v1/health | python3 -c 'import json,sys; assert json.load(sys.stdin)["status"] == "ok"'

docker exec worker-google-android-google-android-webrtc-gateway-1 python -c \
  "import asyncio,aiohttp,json; exec('async def t():\n    async with aiohttp.ClientSession() as s:\n        async with s.ws_connect(\"http://google-android-web:8080/api/v1/emulator/ws-jsep\") as w:\n            m=await asyncio.wait_for(w.receive(),10)\n            data=json.loads(m.data)\n            assert \"start\" in data and data[\"start\"].get(\"iceServers\")\nasyncio.run(t())')"

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
