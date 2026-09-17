#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="$root_dir/docker-compose.yml"
python3 -m json.tool "$root_dir/config/config.json" >/dev/null
python3 -m json.tool "$root_dir/config/default.json" >/dev/null
while IFS= read -r file; do python3 -m json.tool "$file" >/dev/null; done < <(find "$root_dir/config/profiles" "$root_dir/config/scenarios" -type f -name '*.json' | sort)
bash -n "$root_dir/scripts/debug-up.sh"
sh -n "$root_dir/scripts/entrypoint.sh"
python3 -m py_compile "$root_dir/scripts/gateway_server.py"
docker compose -f "$compose_file" --profile debug config -q
grep -q '^  google-android-webrtc-gateway:' "$compose_file"
grep -q '^  google-android-web:' "$compose_file"
grep -q '6082:8080' "$compose_file"
grep -q '/run/secrets/adbkey:ro' "$compose_file"
grep -q 'ANDROID_SDK_ROOT=/usr/lib/android-sdk' "$root_dir/Dockerfile"
grep -q 'emulator_controller.proto' "$root_dir/Dockerfile.webrtc-gateway"
grep -q 'gateway_server.py' "$root_dir/Dockerfile.webrtc-gateway"
grep -q 'chrome-command-line' "$root_dir/scripts/entrypoint.sh"
grep -q 'screen.mjpeg' "$root_dir/web/index.html"
grep -q 'proxy_buffering off' "$root_dir/nginx/webrtc.conf"
echo "Static configuration tests passed"
