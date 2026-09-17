# Changelog

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
