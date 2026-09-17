# Changelog

## 0.1.7 — 2026-09-17

- Added configurable Appium session capabilities `android.adb_exec_timeout_ms`
  and `android.uiautomator2_server_install_timeout_ms` (both default 120000)
  to `AndroidDevice.connect()`, so a slower cold Appium/UiAutomator2 install on
  a given emulator/host does not need a code change. This closes out a shared
  runtime change that was already required by `worker-google-android` 0.1.1's
  cold-start fix but had not yet been released for `worker-android` itself.
- No behavior change for existing profiles: both new keys keep their previous
  hard-coded defaults unless a profile explicitly overrides them.

## 0.1.6 — 2026-09-16

- Made the Compose debug service explicitly enable safe JuicySMS diagnostics,
  including when the selected profile does not set `debug.keep_alive`.

## 0.1.5 — 2026-09-16

- Added safe JuicySMS lifecycle tracing in debug mode and descriptive stable
  provider error codes in normal startup warnings.

## 0.1.4 — 2026-09-16

- Corrected JuicySMS country handling to its current v2 contract: one-time
  orders accept only `USA`, `UK`, `NL` and `PH`; reject unsupported countries
  locally instead of creating a known-invalid order request.
- Corrected the shipped JuicySMS example from unsupported `DE` to `NL`.

## 0.1.3 — 2026-09-16

- Simplified standalone JuicySMS setup: a private local profile may now set
  `phone_number_provider.token` directly, while retaining token-file support
  for future Controller materialization.
- Ignored Android `config/profiles/*.local.json` files to prevent local provider
  credentials from being committed accidentally.

## 0.1.2 — 2026-09-16

- Added a direct JuicySMS v2 one-time-order adapter with secret-file bearer
  credentials, bounded polling, E.164/order validation and graceful cancel.
- Added non-secret JuicySMS profile configuration and provider contract tests.
- Made cloud phone allocation run-scoped and optional by default: a worker can
  start without a connected number, logs a clear warning and exposes `null` as
  the QA app's line number. `required: true` retains fail-fast behavior.

## 0.1.1 — 2026-09-16

- Added opt-in application-scoped telephony QA via pinned Frida runtime: IMEI,
  IMSI, phone number, operator, MCC/MNC and country Android Java API fixtures.
- Added deterministic generated identity values, explicit fixed values and
  validation; new domains read Identity config before launch-profile overrides.
- Added replaceable phone provider interface, mock fixture and normalized HTTP
  bridge with idempotency keys, bounded polling and secret-file credentials.
- Added polling/webhook delivery through existing run-scoped runtime inputs,
  allocation correlation, SMS code normalization and graceful release lifecycle.
- Fixed fatal errors and shutdown propagation through debug continue-on-error.
- Prepare adb-root before Appium port forwards, then start telephony instrumentation
  after the Appium session is ready; bound Android-service readiness retries.
- Added unit, HTTP/API contract tests and a real Android QA APK smoke test.
- Added TELEPHONY.md and runnable profile/scenario examples; excluded caches,
  archives and runtime artifacts from Docker build context.
- Controller/Web Console integration and whole-OS telephony changes remain deferred.

## 0.1.0 — 2026-09-14

- Added autonomous `worker-android` sibling component.
- Preserved worker config, scenario, artifact, runtime-input and Control API contracts used by `worker-firefox`.
- Added Android Emulator + Appium UiAutomator2 execution backend.
- Added standalone and noVNC debug Compose services.
- Added Android device profile selection via worker config or `EMULATOR_DEVICE`.
- Added emulator startup proxy translation from the shared top-level `proxy` configuration.
- Added Android `screenrecord` run recording.
- Added portable action types and Android-specific `launch_app`, `tap`, and `swipe` actions.
- Controller and Web Console integration intentionally deferred.
