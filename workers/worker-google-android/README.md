# worker-google-android v0.1.4

Autonomous Android worker built around Google's official Android Emulator
Container (`30-google-x64-no-metrics:30.1.2`) and an Appium/ADB sidecar.

## Functional contract

The sidecar builds from the same Python application source as `worker-android`.
It therefore supports the same configuration merge, scenario actions, Control
API, runtime inputs, identity storage, artifacts, screenshots, Android screen
recording, app-scoped Telephony QA, mock/HTTP/JuicySMS phone providers, and safe
provider diagnostics. The example proxy configuration is translated into the
official emulator's `-http-proxy` launch argument.

The emulator implementation differs where the base images differ:

- browser debug at port `6082` shows a live view and hardware/GPS controls
  through a small self-owned gateway talking directly to the emulator's
  `EmulatorController` gRPC service (see "Debug mode and browser UI" below),
  not VNC/noVNC and not the image's own WebRTC video service;
- Android is Google APIs API 30/Android 11 rather than the Android 14 image used
  by `worker-android`;
- the device skin is the official image's Pixel 2;
- app-scoped Telephony QA requires this image to permit `adb root` and Frida;
  cloud-number/SMS inputs themselves do not require root.

The worker remains autonomous. Controller/Web Console integration is outside
this release.

## Requirements

- Linux x86_64 host with `/dev/kvm` available to Docker;
- Docker Compose v2;
- enough free Docker storage for the emulator's approximately 7.4 GB userdata.

## Debug mode and browser UI

The helper creates `runtime/adbkey` when missing, builds the four-container
stack, waits for the emulator healthcheck and starts the worker:

```bash
cd workers/worker-google-android
./scripts/debug-up.sh
```

Open `http://<docker-host>:6082`. The page shows a live emulator screen (a
`multipart/x-mixed-replace` PNG stream at `/api/v1/emulator/screen.mjpeg`,
refreshed as the device produces new frames), Home/Back/App Switch/Power/
Volume buttons, and GPS latitude/longitude controls — all served by
`scripts/gateway_server.py`, a small aiohttp app that talks directly to the
emulator's own `EmulatorController` gRPC service (`sendKey`, `streamScreenshot`,
`setPhysicalModel`). The Control API is available locally at
`http://127.0.0.1:8092`. No ADB-key `export` is required; all later commands
work directly:

```bash
docker compose --profile debug ps
docker compose --profile debug logs -f worker-google-android-debug
docker compose --profile debug down
```

The debug profile uses `debug.keep_alive=true`, so the container remains
available after the scenario.

This image's own legacy `android.emulation.control.Rtc` WebRTC video service
does not actually complete a real browser peer connection (verified by direct
gRPC probing: it never returns an SDP answer or ICE candidates after a client
offer). `screen.mjpeg` above is the replacement live view; see "Known issues"
for the (unrelated) Chrome-cold-start reliability issue this does not affect.

## Normal autonomous mode

Generate the ADB key once (the debug helper can do this), then run:

```bash
./scripts/debug-up.sh
docker compose --profile debug down
docker compose up --build google-emulator worker-google-android
```

The ordinary profile exits after the scenario and writes its result under
`artifacts/<identity>/<scenario>/<run-id>/`.

## Profiles

- `google-android-test-001` / `google-android-test-001-debug`: regular smoke run;
- `google-android-proxy-example`: emulator-level HTTP proxy example;
- `google-android-telephony-qa`: mock phone/SMS plus app-scoped telephony fixture;
- `google-android-juicysms-example`: private-local-profile template for JuicySMS.

Copy provider examples to a file ending in `.local.json` before adding a real
token. Such files, ADB keys, artifacts and identities are ignored by Git. The
full telephony/provider contract is shared with and documented in
`../worker-android/TELEPHONY.md`; scenario actions are documented in
`../worker-android/SCENARIO.md`.

## Tests

```bash
bash tests/test_debug_stack.sh
docker run --rm -v "$PWD/scripts:/src" -w /src golang:1.24-bookworm go test -v emulator-entrypoint.go emulator-entrypoint_test.go
PYTHONPATH=../worker-android python3 -m unittest discover -s ../worker-android/tests -p 'test_*.py'
./tests/e2e_debug.sh
```

The E2E test verifies the official emulator cold boot, Control API, browser
page, a real PNG frame from `screen.mjpeg`, hardware key injection, Appium
actions and final artifacts. `runtime/adbkey` is private local state and must
not be committed. See "Known issues" below: on a loaded host,
`./tests/e2e_debug.sh` can still fail `android-example` itself for a reason
unrelated to the debug UI or the test harness.

## Known issues

The 0.1.2/0.1.3 blank/black debug-UI screen is resolved as of 0.1.4: the live
view no longer depends on the image's non-functional legacy WebRTC video
service at all (see `CHANGELOG.md`). One issue remains open:

- **Chrome cold-start reliability on the official emulator image.** The
  default `android-example` scenario (`open` a URL, then `press` `BACK`) does
  not yet pass reliably end-to-end on a resource-constrained host. Five full
  `./tests/e2e_debug.sh` runs during the 0.1.2 investigation showed two
  distinct failure modes on Chrome's first real launch in a container:
  - a native crash (`ContextImpl: Failed to ensure
    .../Android/data/com.android.chrome/files/Download`, then `Fatal signal 5
    (SIGTRAP)`), or
  - an ANR (`ActivityRecord{...ChromeTabbedActivity} does not have a focused
    window`, `Input dispatching timed out`, resolving only after ~29s).

  In both cases the `press`/`BACK` action that follows `open` then fails with
  `InvalidElementStateException: Cannot generate key press event for key code
  4`, because Chrome never actually finished rendering the page. Disabling
  Chrome's first-run experience (0.1.2, see `CHANGELOG.md`) fixes a
  real but different problem and does not resolve this one. A pre-warm launch
  of Chrome before the worker connects (giving the flaky first launch a place
  to fail before the scenario runs) was tried and reverted: it did not
  reliably prevent the failure recurring on the scenario's own launch, and
  added 15-60s of startup latency for an unproven benefit. This looks like a
  genuine Chrome/emulator-image cold-start reliability issue that is sensitive
  to host CPU/memory pressure rather than a scenario-engine bug; a host with
  more headroom may see it less often. See `AGENT.md` for the exact evidence
  from each attempt. Do not reintroduce an unverified pre-warm/retry hack
  without first confirming it actually prevents the failure across multiple
  clean runs.
