# Changelog

## 0.1.5 — 2026-09-17

- Added mouse/touch interaction to the debug UI: click-and-drag (or touch)
  on the live screen now injects real taps/swipes via a new `sendMouse`-backed
  `POST /api/v1/emulator/mouse` (`{x, y, buttons}`, one call per down/move/up).
  Coordinates are translated from the displayed image's CSS size to the
  stream's native device pixel size in `web/index.html`. Verified end-to-end
  by tapping the Chrome icon in a live session and confirming it launched.
  Reported by a user who could see the screen (0.1.4) but had no way to
  interact with it.
- Added a static check for the new route/frontend wiring and an E2E check
  that a mouse-down/mouse-up pair is accepted.
- Fixed an E2E test race: the worker Control API health check ran once
  immediately after the emulator's own boot check, which could fail if the
  emulator was already booted from a prior run (leaving the worker container
  no time to start). It now retries like the other readiness checks.

## 0.1.4 — 2026-09-17

- Replaced the debug UI's video path entirely. Direct gRPC probing of the
  official emulator's legacy `android.emulation.control.Rtc` service (used by
  the vendored WebRTC frontend) showed it never returns an SDP answer or ICE
  candidates for a real browser offer — confirmed both via `sendJsepMessage`/
  `receiveJsepMessage(s)` polling and by replaying an actual captured browser
  offer. This made the 0.1.2/0.1.3 debug page fundamentally unable to show
  video, independent of the routing bug 0.1.3 fixed.
- `scripts/gateway_server.py` is now a small, fully self-owned aiohttp app
  (no vendored/sed-patched third-party gateway code) that talks directly to
  the emulator's `EmulatorController` gRPC service: `getStatus`, `setGps`
  (`/api/v1/emulator/gps`, unchanged contract), a new `sendKey`-backed
  `POST /api/v1/emulator/key` (`GoHome`/`GoBack`/`AppSwitch`/`Power`/
  `AudioVolumeUp`/`AudioVolumeDown`), and a new `streamScreenshot`-backed
  `GET /api/v1/emulator/screen.mjpeg` (a `multipart/x-mixed-replace` PNG
  stream — a real, if lower-frame-rate, live view).
- `web/index.html` is a new small self-owned static page (no build step)
  showing that live stream plus hardware/GPS controls, replacing the vendored
  `android-emulator-container-scripts` React frontend entirely.
- `Dockerfile.webrtc-gateway`/`Dockerfile.webrtc-web` are drastically
  simplified: no more cloning `android-emulator-container-scripts`, no more
  `rtc_service.proto` vendoring/compilation, no more `npm ci`/webpack build.
  Removed `scripts/webrtc-gateway-entrypoint.sh` and `webrtc/rtc_service.proto`
  (dead code after the above). `nginx/webrtc.conf` no longer needs the 0.1.3
  path alias and now disables proxy buffering so `screen.mjpeg` frames are
  forwarded as they arrive instead of batched.
- Updated static and E2E tests for the new architecture: E2E now fetches a
  real frame from `screen.mjpeg` and posts a hardware key, instead of the old
  JSEP-handshake-only check that could never have caught the video being
  fundamentally broken.
- Verified end-to-end: a `screen.mjpeg` frame confirmed visually as the real
  emulator home screen; hardware key and GPS calls succeed; full
  `./tests/e2e_debug.sh` passes including a genuine `android-example` PASS.

## 0.1.3 — 2026-09-17

- Fixed the WebRTC debug UI showing a blank white page. The built frontend's
  `index.html` references its JS bundle by an absolute
  `/android-emulator-webrtc/assets/...` path, but nginx served the build
  output only at the root (`/assets/...`); the mismatch fell through to
  nginx's SPA `try_files ... /index.html` fallback, which returned `index.html`
  itself with `HTTP 200` for the JS request — so the page loaded but its
  script never ran, no error visible to a plain `curl` check. `nginx/webrtc.conf`
  now aliases `/android-emulator-webrtc/` back to the same document root.
  Found by actually opening `http://<host>:6082` in a browser (reported by a
  user) after the 0.1.2 release; the existing E2E test only checked for
  `<html` in the root response, which passed either way.
- Added a static check that `nginx/webrtc.conf` has the alias, and an E2E
  check that fetches the exact JS path `index.html` references and requires a
  real JavaScript content type, so this class of "200 but wrong content"
  regression cannot pass silently again.

## 0.1.2 — 2026-09-17

- Fixed one real cause of `open`/`new_tab` opening the wrong screen: on a fresh
  (`-no-snapshot`) official emulator instance, Chrome had never completed its
  first-run setup, so the very first `ACTION_VIEW` intent could open Chrome's
  `FirstRunActivity` wizard instead of the requested page.
  `scripts/entrypoint.sh` now disables Chrome's first-run experience (`chrome
  --disable-fre --no-default-browser-check --no-first-run` via
  `/data/local/tmp/chrome-command-line`) once the emulator is reachable and
  before the worker connects, matching `worker-android`'s working behavior.
  This fix is verified in isolation (manual adb repro before/after) but is
  **not sufficient on its own**: repeated full debug E2E runs on this
  resource-constrained host still fail `android-example` at the `press`/`BACK`
  action, because Chrome's cold start is separately unreliable here — see the
  new "Known issues" section in `README.md` and `AGENT.md` for the exact
  crash/ANR evidence from five full E2E attempts. Pre-warming Chrome before
  the worker starts (tried during this investigation) did not reliably avoid
  the problem and was reverted rather than kept as an unproven, latency-adding
  workaround.
- Added a static regression check that `scripts/entrypoint.sh` still disables
  Chrome's first-run experience.

- Completed browser debug mode with a built WebRTC UI, Nginx proxy and a gateway
  compatible with the legacy RTC service exposed by the pinned emulator image.
- Removed manual ADB-key exports by mounting the generated key as a read-only
  file understood by both the official emulator and the worker sidecar.
- Fixed Appium startup with an explicit Android SDK, build-tools and cold-install
  timeouts; Appium diagnostics are now visible in container logs.
- Matched worker-android defaults and added proxy, Telephony QA, mock SMS and
  JuicySMS example profiles/scenarios.
- Made emulator proxy materialization follow the same global/local/profile
  deep-merge precedence as the Python worker configuration.
- Added static configuration, Go proxy-contract and full debug E2E tests.

## 0.1.0 — 2026-09-17

- Added initial Google official Emulator Container POC with KVM, authenticated
  ADB, Appium sidecar and the shared Android worker runtime.
