# Changelog — worker-firefox

> Component root: `worker-firefox/`. Paths and commands in this document are relative to that directory unless stated otherwise.

## 0.5.22
- Added bounded Camoufox startup readiness retries for transient browser/context closure during addon initialization.
- Added `browser.startup_attempts` and `browser.startup_retry_delay_sec` configuration defaults.
- Replaced Playwright page recording in debug mode with full Xvfb display recording through FFmpeg.
- Added `recording.debug_backend="x11"` and `recording.debug_fps=15` defaults.
- Debug video is written live to `videos/debug-session.webm` and finalized on graceful SIGINT/SIGTERM shutdown.
- Preserved Playwright page recording for normal virtual/headless runs.
- Added `pytest.ini` to restrict test discovery to `tests/` and ignored local Python virtual-environment/cache files.
- Verified the Docker debug lifecycle, noVNC/API operation, runtime input, VP9 video playback, and all 59 unit tests.

## 0.5.21-1
- Documentation-only synchronization with `firefox-image-builder v0.2.0`.
- Clarified that the builder now clones Camoufox source and generates the browser package / SOURCE_COMMIT automatically.
- Removed obsolete wording implying operator-provided prebuilt browser ZIP/SOURCE_COMMIT inputs to the builder.
- Worker runtime behavior is unchanged.

## 0.5.21
- Removed `Dockerfile.base` and base-image build implementation from the worker release.
- Added `WORKER_FIREFOX_BASE_IMAGE` as the worker-owned Docker build argument for selecting a prepared browser runtime image.
- Worker now consumes immutable versioned images such as `worker-firefox-base:152.0.4-beta.28`.
- Browser ZIP and build-time `SOURCE_COMMIT` are no longer worker build inputs.
- Documented the separate `firefox-image-builder` tool boundary.
- Updated future Controller design to inspect/select prepared compatible base images instead of building browser images in the run path.
- Synchronized README, CONFIG, PLUGINS, FUTURE, FUTURE_BOT, MEMORY and release notes.

## 0.5.20
- Adopted neutral component naming: `worker-firefox`, future `worker-android`, and `controller`.
- Added configurable `project.name` (default internal codename `cabbage`) and `worker.type` (`firefox`) to `config/config.json`.
- Renamed project-owned environment variables to `WORKER_SYSTEM_CONFIG`, `WORKER_PROFILE`, and `WORKER_DEBUG_PROFILE`.
- Kept vendor/runtime variables such as `CAMOUFOX_EXECUTABLE_PATH` unchanged.
- Renamed Docker Compose services to `worker-firefox` and `worker-firefox-debug`.
- Removed fixed `container_name` from worker services to avoid coupling the worker to one container identity.
- Renamed the default base image tag to `worker-firefox-base:*` while preserving Camoufox-specific build arguments/runtime paths where they genuinely describe the vendor runtime.
- Made startup logs, `summary.json`, and worker health metadata expose configurable project/component/worker type.
- Renamed the HTTP server identity from `CamoufoxControlAPI` to `WorkerControlAPI`.
- Updated Controller roadmap and durable documentation to avoid POC/Camoufox/QA project-owned naming.

## 0.5.19
- Replaced the active monolithic `test.json` / `test-debug.json` configuration model with split configuration layers.
- Added `config/config.json` as the bootstrap runtime path map.
- Added canonical read-only `config/default.json`.
- Added `config/profiles/*.json` for profile/run overrides.
- Added `config/scenarios/*.json` with one reusable scenario per file.
- Added recursive default/profile merge and external scenario resolution/validation.
- Added `WORKER_SYSTEM_CONFIG` / `--system-config` and `WORKER_PROFILE` / positional profile selection.
- Removed project-specific application-storage paths from Python runtime code; identities, artifacts, default/profile/scenario locations and browser SOURCE_COMMIT path are injected through `config.json`.
- Persistent Identity storage root is now injected into identity lifecycle functions instead of using a module-level `/identities` constant.
- Worker remains read-only toward canonical default/scenario configuration.
- Updated Docker Compose sample to select launch profiles through environment variables.
- Added configuration resolver regression tests.
- Updated Controller roadmap so the future Central Console / Controller reuses this worker configuration domain model and launches ephemeral workers through DockerExecutor.

## 0.5.18-2
- Documentation-only review; no intentional runtime changes.
- Cleaned `../FUTURE.md` so it contains only genuinely unimplemented work.
- Clarified that the generic plugin framework is already implemented; retained only concrete plugin enhancements/new adapters in the roadmap.
- Audited the action registry against `SCENARIO.md`: all 19 implemented actions are documented.
- Audited Control API implementation against `API.md` and added the current endpoint inventory.
- Audited plugin modules against `PLUGINS.md`, including the internal `echo` test plugin.
- Updated documentation Definition of Done to keep completed work out of `../FUTURE.md`.

## 0.5.18-1
- Documentation-only revision of v0.5.18; no intentional runtime change.
- Documented the rare intermittent native `page.mouse.move()` stall observed across multiple releases.
- Added future design for phase-specific `click` timeouts and controlled reasons.
- Added future cleanup task for interrupted Playwright futures / trailing `TargetClosedError`.
- Synchronized `../FUTURE.md`, `../FUTURE_BOT.md`, `MEMORY.md`, README and release notes.

## 0.5.18
- Fixed `recording.show_cursor` to display the real cursor trajectory instead of only final action coordinates.
- Added live DOM `mousemove` tracking for the red recording marker.
- Registered the listener through `BrowserContext.add_init_script` so new documents and frames receive it automatically.
- Kept direct final-coordinate updates as a fallback.
- Added regression coverage for init-script registration and live mousemove tracking.
- Updated project documentation.

## 0.5.17
- Added `recording.show_cursor` for a simple red cursor marker in recorded/debug browser pages.
- Cursor marker updates for `mouse_move`, `mouse_move_random`, physical `click`, `mouse_press`, and `hover`.
- Cursor marker is visual-only (`pointer-events: none`) and is restored after navigation/new tabs/back navigation.
- Enabled `show_cursor` in sample debug config and left it disabled in normal sample config.
- Added regression tests for enabled/disabled cursor overlay behavior.
- Updated all relevant project documentation.

## 0.5.16-1
- Documentation/metadata-only revision of v0.5.16; no intentional runtime behavior change.
- Added project versioning policy for `-N` documentation revisions.
- Added future task to eliminate hidden/hardcoded operator-tunable behavioral defaults from Python code.
- Added detailed migration/audit plan to `../FUTURE_BOT.md`.
- Updated `MEMORY.md` so both policies survive future handoffs.

## 0.5.16
- Added modular `consent-handler` plugin for cookie/CMP banners.
- Added `handle` method with `accept_all` and `reject_optional` policies.
- Added provider-specific selector support for OneTrust, Cookiebot, Didomi, CookieYes, iubenda, Quantcast, and TrustArc.
- Added multilingual generic text fallback for common consent button labels.
- Added scanning of the main page and attached Playwright frames.
- Added `required=false` default behavior so missing banners can be treated as a normal no-op.
- Added `detect` diagnostics method and `consent-handler.json` / `consent-detect.json` artifacts.
- Added deterministic local `consent-test-page` Docker service and `consent-test` scenario.
- Updated sample plugin configuration and all relevant project documentation.

## 0.5.15
- Documentation/architecture synchronization release; no browser-worker runtime behavior changed from v0.5.14.
- Reviewed all root Markdown documentation against the current implementation and roadmap.
- Restored the approved future Controller/control-plane architecture to `../FUTURE.md`, `../FUTURE_BOT.md`, and `MEMORY.md`.
- Documented Docker SDK/Engine based `DockerExecutor`, Executor abstraction, one-run/one-ephemeral-worker lifecycle, internal worker networking, Controller-routed mid-run inputs, external persistence, and deferred Kubernetes direction.
- Added the future Controller/worker API boundary note to `API.md`.

## 0.5.14
- Added generic selector-based `hover` action for physical Camoufox mouse movement without clicking.
- `hover` accepts any valid Playwright/CSS selector; it is not tied to a specific HTML tag.
- Added precise center-relative `offset` positioning.
- Added optional `frame_selector` and nested `frames` support for iframe targets.
- Added regression tests for generic selectors, offsets, and iframe chains.
- Synchronized `../FUTURE.md` / `../FUTURE_BOT.md` with the deferred centralized Playwright frame/locator error-normalization task.
- Updated project documentation and `MEMORY.md`.

## 0.5.13
- Added generic `mouse_press` action for physical mouse down/hold/up interactions.
- `mouse_press` supports DOM selectors, absolute viewport coordinates, configurable button, offsets and hold duration.
- Added optional `frame_selector` and nested `frames` support for targets inside iframe chains, including cross-origin frames through Playwright frame locators.
- Hard action watchdog now includes intentional `hold_ms`, preventing valid long presses from being killed as stuck actions.
- Added regression tests for DOM hold, iframe-chain hold, coordinate hold and watchdog duration.
- Updated project documentation and `MEMORY.md`.

## 0.5.12
- Added generic outbound `webhook` scenario action with HTTP method, headers/params/body/JSON, timeout, retries, `on_error`, and `save_as`.
- Added webhook response runtime namespace: `{{webhook.<save_as>.<field>}}`.
- Added optional FastAPI `webhook-mock` Docker service backed by a mounted JSON profile configuration for end-to-end POC testing.
- Added root `MEMORY.md` project handoff and made it part of release documentation policy.
- Moved country-via-Control-API/Fluent dropdown automation to the unversioned roadmap.

## v0.5.11 — 2026-08-14

### Fixed
- Fixed a Playwright Sync API event-dispatch race in `switch_tab`.
- Replaced blocking Python polling sleep with Playwright-aware waiting while a requested tab is pending.
- Tabs opened by `target="_blank"`, `window.open()`, or popup flows can now be detected while `switch_tab` is actively waiting instead of only when a later Playwright call occurs.
- Added a regression test reproducing delayed site-created tab delivery.

### Documentation
- Updated README, CONFIG, SCENARIO, API, PLUGINS, FUTURE, FUTURE_BOT and RELEASE_NOTES for v0.5.11.

## v0.5.10 — 2026-08-14

### Added
- Automatic tracking of browser tabs/pages opened by the site via Playwright `BrowserContext` page events.
- Defensive synchronization with `browser_context.pages` before tab operations.
- `switch_tab.target` values: `first`, `oldest`, `last`, `newest`.
- `switch_tab.timeout_ms`; index-based switching now waits for a requested tab to appear.

### Changed
- Playwright locator timeouts in scenario actions are logged as controlled, concise errors instead of expected full tracebacks.
- Renamed `FUNCTIONS.md` to `CONFIG.md` and updated all project references.
- Corrected application/readme version metadata to `0.5.10`.

### Fixed
- Scenarios can now continue on a page opened by `target="_blank"`/`window.open()` instead of remaining bound to the original page registry.

## v0.5.9 — 2026-08-14

### Changed
- Froze the experimental `hcaptcha-challenger` solver direction after successful v0.5.8 live decision testing.
- Kept `hcaptcha-challenger` disabled by default; retained adapter code/tests for future research.
- Removed all bundled `hcaptcha-*` scenarios from `config/test.json` and `config/test-debug.json`.
- Added `../FUTURE_BOT.md` for detailed AI/developer continuation context while keeping `../FUTURE.md` concise for people.
- Synchronized README, scenario/functions/plugin/API documentation, roadmap, changelog, and release notes with the freeze decision.

### hCaptcha decision evidence
- Checkbox interaction confirmed: `clicked=True`, `challenge_opened=True`, `response_present=False`.
- Non-Gemini local solve test confirmed `models=0` and `reason=hcaptcha_local_solver_unavailable` on the tested 0.19.x runtime.
- Future work should first re-evaluate upstream and then prefer a generic pluggable vision backend instead of hard-coding Gemini.

## v0.5.8 — 2026-08-14

### Added
- Added configuration-only `hcaptcha-challenger.local_solve_test` as the final non-Gemini feasibility test before deciding whether to continue or freeze the local hCaptcha direction.
- The test reuses the current Camoufox page, opens the hCaptcha challenge, inspects non-Gemini public/runtime entry points and packaged local model assets, and writes `hcaptcha-local-solve-test.json`.
- Added bundled `hcaptcha-local-solve-test` scenario to normal and debug configs.

### Behavior
- `local_solve_test` never falls back to `AgentV`/Gemini.
- When no stable configuration-only local solver is discoverable in the installed upstream runtime, the plugin returns controlled reason `hcaptcha_local_solver_unavailable`.
- The action is marked `continue_on_error: true` in the bundled sample so diagnostics and screenshot artifacts are still produced.

### Research conclusion for live validation
- Upstream `hcaptcha-challenger` documents local model concepts, but its current high-level path is AgentV/Gemini; the maintainer has also stated that the old local flow is no longer a maintained/documented path. v0.5.8 converts that uncertainty into a reproducible runtime test rather than claiming unsupported local solving.


## v0.5.7 — 2026-08-14

### Added
- Added configuration-only `hcaptcha-challenger.checkbox_test`.
- Added `hcaptcha-checkbox-test` sample scenario to normal and debug configs.
- Added structured checkbox/challenge/response diagnostics without Gemini.

### Changed
- `capabilities` now advertises `checkbox_test` as a diagnostic method.
- Documentation updated for the new hCaptcha interaction stage.

## v0.5.6 — 2026-08-14

### Added
- Added `hcaptcha-challenger` method `local_probe` for configuration-only runtime inspection of local/pluggable hCaptcha capabilities.
- Probe records upstream package version, candidate local model/solver modules, packaged model resource files, current hCaptcha frames/response fields, and Gemini-key presence without exposing the key.
- Probe writes `hcaptcha-local-probe.json` into each run artifact directory.
- Added sample `hcaptcha-local-probe` scenario to normal and debug configs.

### Changed
- `capabilities` now advertises `local_probe` and explicitly reports that a built-in universal local solver is not yet claimed.
- Updated plugin/roadmap documentation to make the next local backend decision depend on live probe results.

## v0.5.5 — 2026-08-14

### Added
- Added modular `select` action in `app/actions/select.py` with automatic registry discovery.
- Native `<select>` support by `value`, `label`, or `index` using Playwright `select_option`.
- Custom dropdown/combobox support with ARIA `role=option`, explicit `option_selector`, and selection by label/value/index.
- Added hCaptcha backend abstraction: `agentv` and pluggable `custom` backend (`Class(config).solve(page, params)`).
- Added hCaptcha `capabilities` method for backend/dependency discovery.

### Changed
- Suppress only `SyntaxWarning` originating from `pydub` while loading `playwright-recaptcha`; other warnings/errors remain visible.
- hCaptcha research conclusion documented: upstream 0.19 high-level `AgentV` still requires Gemini, while local ONNX resources exist for lower-level challenge types.
- Updated sample hCaptcha config with explicit `backend: agentv`.

### Tests
- Added native/custom dropdown action tests and custom hCaptcha backend tests.
- Regression suite: 31 tests.

## v0.5.4 — 2026-08-14

### Changed
- Maintenance/roadmap synchronization release based on v0.5.3 runtime.
- Added hCaptcha-without-Gemini research task to `../FUTURE.md`.
- Added future consent/cookie-banner plugin specification to `../FUTURE.md`; no consent plugin is included in this release.
- Documented current `hcaptcha-challenger` `GEMINI_API_KEY` / AgentV live-test limitation in `PLUGINS.md`.
- Kept `pydub SyntaxWarning` cleanup as future work.
- Updated release notes and version metadata to 0.5.4.


## v0.5.3 — 2026-08-13

### Added
- Experimental `hcaptcha-challenger` adapter using the existing plugin layer.
- `hcaptcha-test-easy` ZennoLab scenario.
- Sync-to-async Playwright page bridge so the adapter can reuse the existing Camoufox page/session.
- Unit test for the hCaptcha adapter bridge.

### Changed
- Added `hcaptcha-challenger==0.19.0` and its runtime dependencies to the base image without allowing it to replace Camoufox's Playwright dependency.
- hCaptcha adapter is disabled by default until live validation is complete.

## v0.5.2 — 2026-08-13

### Added
- First real third-party adapter: `PlaywrightRecaptchaPlugin` with reCAPTCHA v2 support.
- `PLUGINS.md` documentation.
- ZennoLab `captcha-test-v2` sample scenario.
- FFmpeg/ffprobe and pinned non-Playwright dependencies required by `playwright-recaptcha`.

### Changed
- Controlled `PluginError` failures now log a concise structured message without duplicate traceback output.
- Plugin documentation/examples standardized on `adapter: "module:Class"` and `plugin_call.method`.
- Regression suite expanded to 24 tests.

### Compatibility
- Existing v0.5.1 configs/scenarios remain valid.
- Base image rebuild is required once because runtime dependencies changed.


## v0.5.1 - 2026-08-13

- Started the 0.5.x release line from the stable v0.4.33 codebase.
- Added a generic optional third-party plugin/adaptor framework under `app/plugins/`.
- Added the stable `BasePlugin` lifecycle: `setup`, `invoke`, `teardown`.
- Added `PluginManager` with explicit enable/disable policy, lazy imports, isolated adapter configuration, and controlled loading errors.
- Added the `plugin_call` scenario action so plugins can be invoked without modifying `ActionEngine`.
- Added the dependency-free `EchoPlugin` as a reference adapter/contract test.
- Kept optional third-party dependencies out of the core runtime unless an enabled adapter requires them.
- Added plugin framework tests; full suite: 19 tests.
- Added `RELEASE_NOTES.md` as a required per-release document and `../FUTURE.md` for roadmap items.
- Updated README, FUNCTIONS, SCENARIO, and API documentation.

## v0.4.33 - 2026-08-13

- Switched persistent locale handling to Camoufox's supported `locale=` API for Identity generation and normal browser launches.
- Removed manual `locale:*` keys from the runtime Camoufox `config` payload and reconstruct them through the public locale parameter.
- Combined `fingerprint.locale` and `fingerprint.languages` into one ordered accepted-locale list with the primary locale first and duplicates removed.
- Kept persistent timezone/geolocation as intentional Identity-owned low-level overrides and set `i_know_what_im_doing=true` where Camoufox launch options are generated.
- Kept `geoip` disabled for normal launches; proxy GEO remains validation-only after Identity creation/update.
- Added an explicit warning when proxy is enabled but `proxy_public_ip` cannot be determined during network preflight.
- Added locale bridge tests; total test suite: 15 tests.

## v0.4.32 - 2026-08-13

- Made persistent Identity location settings authoritative across proxy changes.
- Stopped passing `geoip` to normal Camoufox launches; proxy GEO can no longer silently rewrite locale/languages/timezone/geolocation on every run.
- Kept GEO-assisted values for initial Identity generation and explicit `--update-identity`.
- Added Identity schema 4 with persisted `location_identity` and automatic schema-3 migration.
- Added `fingerprint.languages` and `fingerprint.timezone` profile settings.
- Added structured `proxy.geoip.enabled`, `validate_identity`, and `fail_on_mismatch` options while preserving the legacy boolean form.
- Added proxy GEO comparison, warning logs, optional strict failure (`proxy_identity_geo_mismatch`), and `proxy-geo-validation.json`.
- Added proxy GEO/profile tests; total test suite: 13 tests.


## v0.4.31 - 2026-08-13

- Removed Playwright `steps` from native-humanized `click(method="mouse")` and `mouse_move`; Camoufox now owns the movement trajectory.
- Kept legacy `steps`/`duration` fields accepted for scenario backward compatibility, but they are ignored in native-humanized movement.
- Added a default 30-second hard watchdog to normal browser actions; `wait` and `wait_input` retain their own timing semantics.
- Added bounded Camoufox context cleanup (4 seconds). If teardown hangs after a fatal action, browser/helper child processes are terminated and run finalization continues.
- Fixed the case where the log reached `FAIL ... reason=action_timeout` but the container stayed alive until Ctrl+C. Failed runs now reach `Result: FAIL` and exit with code 1.
- Added cleanup/default-watchdog tests; 8 tests pass.

## v0.4.30

- Added an engine-level hard watchdog for actions that define `timeout_ms` or explicit `action_timeout_ms`, preventing a stuck synchronous Camoufox/Playwright IPC call from hanging the scenario indefinitely.
- `click.timeout_ms` is now treated as one overall click deadline across visibility lookup, bounding-box resolution and the final click path.
- Added phase logging for `click`: `wait_visible`, `bounding_box`, `mouse_move`, `mouse_click` / `locator_click`.
- Watchdog failures are controlled scenario failures with reason `action_timeout`.
- Preserved the modular v0.4.29 action architecture and existing scenario JSON compatibility.

## 0.4.30 - 2026-08-13

### Changed

- Replaced the monolithic `app/actions.py` implementation with a modular `app/actions/` framework.
- `ActionEngine` now handles orchestration, result collection, runtime-template resolution, error policy, and shutdown only.
- Added shared `ScenarioContext`, `BaseAction`, and `ActionRegistry`.
- Existing 14 actions were moved into focused modules without changing their JSON names or behavior.
- Action modules are auto-discovered; adding a new registered module no longer requires modifying the engine or a central import list.
- Updated README, function, scenario, and API documentation for the modular extension model.

### Compatibility

- Existing scenario JSON remains compatible.
- Existing `from app.actions import ActionEngine` imports remain compatible.
- Control API and runtime-input contracts are unchanged.

## 0.4.27

- Limited supported browser proxy schemes to HTTP and HTTPS.
- Marked SOCKS4/SOCKS5 proxy endpoints deprecated/unsupported; they now fail cleanly with `unsupported_proxy_type` before browser startup.
- Added `proxy.verify_ssl` (default `true`) for proxy network-preflight TLS verification.
- Renamed network diagnostic `proxy_http_ip` to `proxy_public_ip` and added `proxy_verify_ssl`.
- Converted blocked Identity proxy changes to controlled `proxy_change_not_allowed` failures without Python traceback.
- Added controlled proxy failure classification for configuration, authentication, timeout, TLS validation, and connection failures.
- Expected proxy failures return `FAIL` / exit code 1; unexpected application errors continue to emit tracebacks.
- Updated README, FUNCTIONS, SCENARIO, API, sample configs, VERSION, and changelog.

## 0.4.26

- Reworked VM diagnostics console logging to keep large raw diagnostic blobs out of `run.log`/stdout.
- Full raw VM snapshots and full raw diffs remain available in `vm-diagnostics/snapshot.json` and `vm-diagnostics/diff.json`.
- `host.x11.xdpyinfo` changes are summarized to display size, DPI, root depth, visual count, X.Org vendor, and X.Org version.
- `host.memory.meminfo` changes are summarized to key memory/swap values only.
- `host.proc.status` changes are summarized to PID/thread/memory/context-switch fields only.
- Volatile capture timestamps remain stored in artifacts but are suppressed from console drift detail.
- Long generic string values are safely truncated in console output; complete values remain in artifacts.
- Preserved all v0.4.25 debug display behavior and the cache-friendly base/app Docker layer architecture.

## 0.4.25

- Added `browser.debug_display` configuration for debug/noVNC sessions.
- Debug Xvfb size can follow the persistent identity window automatically.
- Openbox pins new browser windows to the configured position (default `0,0`).
- Default debug window mode is maximized inside an identity-sized Xvfb desktop.
- noVNC link now uses local scaling (`resize=scale`) so the client browser does not resize the remote X11 session.
- Preserved the v0.4.24 base/app Docker layer split and cache-friendly build layout.

## 0.4.24

- Split the Docker build into a stable `Dockerfile.base` runtime image and a small application `Dockerfile`.
- The base image contains system dependencies, Python dependencies, Playwright ffmpeg, Camoufox package metadata, and the extracted custom Camoufox browser.
- `camoufox-custom.zip` is consumed only by the base build and is removed after extraction, so the archive is not retained in the image filesystem.
- Added Dockerfile-specific ignore files so normal app builds do not send the large browser archive as build context.
- Normal changes under `app/` or `scripts/` now rebuild only small top layers.
- Base image rebuild is required only when the custom browser, `SOURCE_COMMIT`, `requirements.txt`, or base runtime dependencies change.
- `baseline_stale` behavior from v0.4.23 is unchanged.

## 0.4.23

- Fixed the Camoufox 0.5.x wrapper compatibility regression introduced by the 0.4.22 image optimization.
- Registers the prebuilt custom browser as the active `official/stable` Camoufox installation using minimal package-manager metadata.
- Uses a symlink from `~/.cache/camoufox/browsers/official/152.0.4-beta.28` to `/opt/camoufox-custom`; no second browser bundle is stored.
- Keeps the slim runtime image, multi-stage custom-browser extraction, and removal of `camoufox fetch`.
- Keeps the 0.4.22 `baseline_stale` behavior unchanged.

## 0.4.23

- Added automatic fingerprint baseline staleness handling for Identity profile changes.
- `PATCH /api/v1/identities/{identity}/config` sets `baseline_stale: true` only when fingerprint settings actually change.
- On the next run with fingerprint diagnostics enabled, a stale baseline is refreshed automatically and `baseline_stale` returns to `false`; no drift warning is emitted for the expected profile change.
- Optimized Docker runtime image: switched to `python:3.12-slim-bookworm`.
- Removed the unused `python -m camoufox set/fetch` browser download; the POC continues to launch only `/opt/camoufox-custom/camoufox-bin`.
- Moved `camoufox-custom.zip` unpacking to a temporary multi-stage build so the ZIP is not retained in final image layers.
- Runtime image keeps only required X11/noVNC/browser libraries and Playwright ffmpeg.

## 0.4.23

### Added
- Persistent per-Identity `config.json` profile configuration layer.
- Profile fingerprint settings for `os`, `preset`, `screen`, `locale`, `window`, `device_pixel_ratio`, `hardware_concurrency`, and `webgl`.
- `GET /api/v1/identities/{identity}/config`.
- `PATCH /api/v1/identities/{identity}/config`; changes apply on the next run.
- `resolved-profile.json` artifact for every run.
- `DEBUG_DISPLAY_SIZE` for the debug Xvfb desktop.

### Changed
- `"default"` in run JSON now means inherit the Identity profile; profile `"default"` reuses the persistent generated Identity value.
- Generation-level profile changes (`os`, `preset`, `screen`, `locale`) regenerate the saved Camoufox fingerprint on the next run while preserving the browser profile.
- Direct overrides (`window`, DPR, CPU concurrency, WebGL vendor/renderer) are layered on the persistent Camoufox config without full regeneration.
- Debug Xvfb default size increased from 1440x900 to 2560x1600 to avoid clamping persistent Identity windows.
- `test-debug.json` fingerprint-check now uses Google runtime-input search while the external fingerprint service cools down.

## 0.4.20

- Fixed graceful shutdown while a synchronous Playwright action is actively blocking.
- The first SIGINT/SIGTERM now both marks the RuntimeContext shutdown request and raises a controlled `ShutdownRequested` in the main thread, unwinding `mouse_move`, `click`, `open`, `screenshot`, and other blocking Playwright calls.
- Shutdown-triggered action interruption is reported as `STOPPED/user_interrupt`, not as an application error.
- A second signal during artifact finalization no longer interrupts cleanup.
- Increased Docker `stop_grace_period` to 60 seconds to leave sufficient time for browser/context and video finalization.
- Expected graceful stop sequence ends with `Container stoping bye` and process exit code `0`.

## 0.4.19

- Added global SIGINT/SIGTERM handling for the complete application lifecycle.
- `wait` and `wait_input` can now be interrupted immediately by a shutdown request.
- Added controlled `STOPPED` / `user_interrupt` run result for manual or orchestrator shutdown.
- Shutdown no longer appears as scenario `FAIL` and intentionally returns container exit code 0.
- Debug supervisor now waits for Python artifact finalization and normalizes requested stop to exit code 0.
- Video finalization remains ordered before Control API/helper process shutdown.
- Final shutdown log message: `Container stoping bye`.

## 0.4.18

- Fixed graceful SIGINT/SIGTERM shutdown in debug mode.
- The entrypoint now supervises the Python application and forwards stop signals instead of abandoning helper processes.
- Xvfb, Openbox, x11vnc, and websockify are stopped only after the application finishes artifact finalization.
- Added a 30 second Docker Compose stop grace period.
- Video finalization no longer calls Playwright `Video.save_as()` after browser transport shutdown; finalized local `.raw` WebM files are copied to stable `page-XX.webm` artifact names.
- Controlled shutdown no longer emits a `TargetClosedError` traceback merely because Playwright transport has closed.
- SIGINT/SIGTERM shutdown metadata is stored under `shutdown` in `summary.json`.
- A successful user-requested shutdown ends with `Container stoping bye` in the log.

## 0.4.17

- Controlled scenario failures now finish cleanly without Python tracebacks.
- `wait_input` with `on_timeout: "fail"` returns reason `timeout_data_not_received`.
- `summary.json` now records machine-readable controlled failure fields such as `reason`, `message`, `failed_action`, `action_type`, `input_key`, and `timeout_sec`.
- Unexpected application/runtime errors still include full tracebacks and use reason `unexpected_error`.

## 0.4.16

- Added versioned Control API on `/api/v1`.
- Added Identity-first API resource hierarchy: `/api/v1/identities/{identity}/runs/{run_id}/...`.
- Added collision-resistant run IDs (`UTC timestamp + 4 hex chars`).
- Added `RuntimeContext` for active run state and in-memory external inputs.
- Added `wait_input` scenario action with configurable `timeout_sec` and `on_timeout` policies (`fail`, `continue`, `default`).
- `on_timeout=fail` is fatal even in debug mode.
- Added recursive `{{input.<key>.<field>}}` runtime template resolution.
- Added early input delivery: API input can arrive before `wait_input` is reached.
- Added `runtime-events.json` metadata without storing submitted payload values.
- Added `API.md`.
- Removed misspelled `FUNTIONS.md`; canonical file is `CONFIG.md`.
- Added Control API port 8090 to Docker Compose normal and debug services.

## 0.4.15 - 2026-08-12

### Changed
- Debug mode now continues execution after individual action failures instead of aborting the scenario.
- Failed debug actions remain visible as `FAIL` entries in `run.log` and `summary.json`.
- Added `action_failures` and `debug_continue_on_error` fields to the run summary.
- Per-action `continue_on_error` remains supported; in debug mode an explicit `continue_on_error: false` restores fail-fast behavior for that specific action.

### Added
- Added `SCENARIO.md` with the complete scenario/action reference and examples.
- Added `CONFIG.md` with the JSON configuration, diagnostics, proxy, fingerprint, debug and artifact reference.
- Added `FUNTIONS.md` as a compatibility pointer for the originally requested filename spelling.

### Fixed
- Manual noVNC mouse/keyboard takeover no longer causes a single Playwright action failure to terminate the whole debug scenario.
- Updated application/identity metadata version to 0.4.15.

## 0.4.14 - 2026-08-12

### Added
- Added `click.method: "mouse"` for physical pointer-based clicks at the center of a located element.
- Added optional `click.steps` and `click.button` for mouse-click behavior.
- Added optional `click.force` for locator-click mode.

### Changed
- `click.timeout_ms` now applies to both the visibility wait and the Playwright locator click itself.
- The sample `fingerprint-check` scenario now uses `method: "mouse"` for the Fingerprint.com score-details button.

### Fixed
- Prevented locator clicks from silently falling back to Playwright's default 30000 ms timeout when a shorter `timeout_ms` was configured.
- Avoided automatic retry after an ambiguous click timeout, preventing accidental double-toggle behavior.

## 0.4.13 - 2026-08-12

### Added
- Added deterministic `mouse_move` action with `x`, `y`, optional `duration`, optional `steps`, and viewport clamping enabled by default.
- Added exact wheel scrolling through `scroll.delta_y` and optional horizontal `scroll.delta_x`.
- Added `fingerprint-check` sample scenario to both normal and debug configs for repeatable detector/VM-observation runs.

### Changed
- `test-debug.json` now selects `fingerprint-check` by default and enables `vm_diagnostics`, matching the interactive VM-detection troubleshooting workflow.
- Existing random `scroll.direction` + `scroll.distance` behavior remains fully supported for backward compatibility.

### Fixed
- Fixed `Unsupported action type: mouse_move` when a scenario requests an explicit mouse position.
- Fixed exact `delta_y` values being ignored by the previous scroll implementation.

## 0.4.12

### Fixed
- VM diagnostics no longer fail on Firefox/Camoufox opaque origins (`about:blank`) when `localStorage`, `indexedDB`, service worker, or similar APIs raise `SecurityError`.
- Security-sensitive capability probes are now best-effort and return `null` instead of aborting the scenario.
- Added top-level fault isolation around the browser-side VM snapshot so diagnostics cannot crash the core worker scenario.
- VM diagnostics schema bumped to 2.

# 0.4.12

- Added optional `vm_diagnostics` module, disabled by default.
- Added browser-visible runtime snapshot: navigator, screen/window geometry, media devices, AudioContext, WebGL limits/extensions, CSS pointer/hover and browser capabilities.
- Added container-side debug snapshot: CPU/cgroup/DMI/kernel/DISPLAY/Xvfb information where available.
- Added per-Identity VM diagnostics baseline, persistent history and cross-run diff.
- Added optional operator `label` for manually annotating runs such as `vm-detected` / `vm-not-detected`; no third-party detector scraping or bypass behavior is implemented.
- Kept noVNC on `0.0.0.0:6080` and preserved all v0.4.10 runtime behavior.

# 0.4.10

- Removed the CreepJS-specific `fingerprint_stability` module, configuration, scenario visit, screenshots, baselines, and aggregate/module extraction.
- Kept internal cross-run fingerprint diagnostics, including Canvas/WebGL rendering probes.
- Kept persistent Identity/profile behavior and interactive debug/noVNC keep-alive from 0.4.9.
- External anti-fraud/tampering results are treated as observational validation; this release does not implement detector-specific bypass logic.

## 0.4.9 - 2026-08-11

### Added
- Configurable interactive debug mode via `debug.keep_alive=true`; after automation completes the live Camoufox context remains open for manual mouse/keyboard control over noVNC.
- Graceful SIGINT/SIGTERM handling while waiting in interactive mode so video and run artifacts can be finalized during shutdown.
- Explicit noVNC readiness check before the application starts.

### Fixed
- Debug startup race where Camoufox could start before Xvfb was ready and fail with `Error: cannot open display: :99`.
- Entrypoint now fails clearly and prints Xvfb/noVNC logs if either service does not become ready.

### Changed
- Debug noVNC port is explicitly published as `0.0.0.0:6080:6080`.

## 0.4.8 - 2026-08-11

### Added
- Canvas PNG diagnostics now records `dataUrlHash`, decoded `dataUrlBytesHash`, `blobHash`, byte sizes and the existing raw RGBA `pixelHash`.
- `fingerprint_stability.creepjs_aggregate_mode` with `informational` (default) and `compare` modes.
- Stability logs classify the common case where Canvas serialization changes while raw pixels remain stable.

### Fixed
- WebGL rendering probe no longer aborts on Firefox/Camoufox Xray access to `MAX_VIEWPORT_DIMS`; deterministic WebGL shader `renderPixelHash` and `renderDataUrlHash` can now complete.
- Fingerprint diagnostics schema raised to 3; old baselines are refreshed once instead of producing false drift.
- Stability baseline also refreshes automatically when the diagnostics schema changes.

### Changed
- CreepJS aggregate `FP ID` and `Fuzzy` are informational by default and do not by themselves classify Identity drift. CreepJS module hashes and our own observed signals are still compared.

## 0.4.7 - 2026-08-11
- Added configurable CreepJS fingerprint stability module with same-page, reload, new-tab and cross-run comparisons.
- Added Canvas/WebGL rendering probes and CreepJS module extraction.

## 0.4.6 - 2026-08-11
- Added configurable cross-run fingerprint diagnostics and baseline diff.
