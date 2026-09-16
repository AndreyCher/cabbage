# Changelog

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
