#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
mkdir -p runtime

if [[ ! -f runtime/adbkey ]]; then
  docker run --rm --user "$(id -u):$(id -g)" \
    --entrypoint /android/sdk/platform-tools/adb \
    -v "$ROOT_DIR/runtime:/out" \
    us-docker.pkg.dev/android-emulator-268719/images/30-google-x64-no-metrics:30.1.2 \
    keygen /out/adbkey
fi

docker compose --profile debug up -d --build \
  google-emulator google-android-webrtc-gateway google-android-web worker-google-android-debug

echo "WebRTC debug UI: http://$(hostname -I | awk '{print $1}'):6082"
