# worker-google-android 0.1.5

Adds real interaction to the 0.1.4 live view: click-and-drag (or touch) on the
screen now sends actual taps/swipes to the device via a new
`POST /api/v1/emulator/mouse` endpoint (`sendMouse` on `EmulatorController`).
Verified by tapping the Chrome icon in a live session and confirming it
launched. Also fixes a test-only race in the worker Control API health check.

# worker-google-android 0.1.4

Replaces the debug UI's video path. Direct gRPC probing showed the official
emulator image's legacy WebRTC video service never actually completes a real
browser peer connection (no SDP answer, no ICE candidates), so the 0.1.2/0.1.3
frontend could never show video regardless of the routing bug 0.1.3 fixed.
`http://<host>:6082` now shows a live view via a small self-owned gateway
(`scripts/gateway_server.py`) streaming real screenshots straight from the
emulator's `EmulatorController` gRPC service, plus working Home/Back/App
Switch/Power/Volume buttons and GPS controls. The vendored WebRTC frontend and
its legacy-proto adaptation are removed entirely — verified end-to-end,
including a real captured screen frame and a passing `android-example` run.
See `CHANGELOG.md` for the full technical detail.

# worker-google-android 0.1.3

Fixes the WebRTC debug UI at `http://<host>:6082` loading as a blank white
page. nginx served the built frontend's assets at the wrong path relative to
what `index.html` itself requests, so the browser's JS bundle request
silently got the HTML page back instead (`HTTP 200`, wrong content) and never
ran. `nginx/webrtc.conf` now serves both paths. See `CHANGELOG.md` for the
exact mechanism; this was reported by a user actually opening the page in a
browser, which no prior automated check exercised.

# worker-google-android 0.1.2

Fixes one real bug found by running the full debug E2E test against the
official emulator for the first time: on a fresh emulator instance, Chrome's
first-run setup wizard could intercept the first `open`/`new_tab`
`ACTION_VIEW` intent instead of showing the target page.
`scripts/entrypoint.sh` now disables Chrome's first-run experience before the
worker connects.

This release does **not** claim `android-example` reliably passes end-to-end.
Five full debug E2E runs on this development host also hit a second,
independent problem: Chrome's cold start on the official emulator image is
itself unreliable under host load, observed as either a native `SIGTRAP` crash
or an ANR while the browser window never gains focus — in both cases the
following `press`/`BACK` action then fails. See the "Known issues" section in
`README.md` and `AGENT.md` for the exact evidence and what was already tried.

# worker-google-android 0.1.1

Completes the autonomous Google Android worker POC. The worker now has a usable
browser WebRTC debug endpoint, file-mounted ADB authentication, working Appium
cold start, configuration/profile parity with `worker-android`, and automated
runtime E2E coverage. The same Python runtime provides scenario, API, artifact,
recording, Telephony QA and phone/SMS-provider behavior; emulator-specific
differences and startup commands are documented in `README.md`.

The WebRTC frontend is pinned to an upstream Google commit. Its build currently
reports upstream npm audit findings; no incompatible automatic dependency
upgrade is applied in this release.
