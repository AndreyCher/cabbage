# worker-firefox v0.5.22

> Component root: `worker-firefox/`. Paths and commands in this document are relative to that directory unless stated otherwise.

### Webhook quick example
```json
{
  "type": "webhook",
  "url": "http://data-provider:8080/api/v1/profiles/resolve",
  "method": "POST",
  "json": {"id": "user-001"},
  "save_as": "profile",
  "timeout_ms": 10000,
  "retries": 2,
  "on_error": "fail"
}
```
A following action can use `{{webhook.profile.login}}`. See `SCENARIO.md` and `CONFIG.md`.

## v0.5.22 — resilient debug startup and recording

- Camoufox startup now performs a readiness check and retries transient `TargetClosedError` failures. Configure this with `browser.startup_attempts` and `browser.startup_retry_delay_sec`.
- Debug/noVNC recording now captures the complete Xvfb display through FFmpeg, including manual input and tab changes during `keep_alive`.
- Debug recordings are written live to `videos/debug-session.webm` and finalized during graceful container shutdown. Configure frame rate with `recording.debug_fps`; set `recording.debug_backend` to `x11` (default) to use this backend.
- Normal `virtual` and `headless` modes continue to use Playwright page recording and finalized `videos/page-XX.webm` artifacts.
- Added a project-local pytest configuration and isolated `.venv` workflow; `python -m pytest -q` now collects only `tests/`.

## v0.5.21-1 — builder documentation sync

Documentation-only revision. Worker runtime is unchanged from v0.5.21.

Documentation now reflects `firefox-image-builder v0.2.0`, which builds the browser package and SOURCE_COMMIT itself from a selected Camoufox source ref instead of requiring operator-provided prebuilt browser artifacts.

## v0.5.21 — external Firefox base-image builder

The worker release no longer contains `Dockerfile.base` or the logic for building the heavy Firefox/Camoufox runtime image.

Base images are now produced by a separate standalone tool:

```text
firefox-image-builder
```

The worker only consumes an already-built immutable image:

```text
worker-firefox-base:<browser-version>
```

This keeps the runtime worker small and makes it easy to maintain several browser base images in parallel.

## v0.5.20 — neutral component naming

v0.5.20 adopts the neutral component naming used by the future multi-worker architecture.

```text
configurable project name: cabbage
component:                 worker-firefox
worker type:               firefox
future component:          worker-android
orchestrator:              controller
```

The internal project codename is data, not architecture. `config/config.json` now contains:

```json
{
  "project": {
    "name": "cabbage"
  },
  "worker": {
    "type": "firefox"
  }
}
```

Changing the internal project name does not require Python/Docker/API naming changes.

Project-owned environment variables are now:

```text
WORKER_SYSTEM_CONFIG
WORKER_PROFILE
WORKER_DEBUG_PROFILE
```

Vendor/runtime variables retain their native names, for example `CAMOUFOX_EXECUTABLE_PATH`.

Docker Compose services are now `worker-firefox` and `worker-firefox-debug`. Fixed worker `container_name` values were removed so the component is not unnecessarily tied to one container identity.

## v0.5.19 — split configuration architecture

v0.5.19 redesigns worker configuration into three independent layers plus a bootstrap path map:

```text
config/
├── config.json
├── default.json
├── profiles/
│   ├── test-user-001.json
│   └── test-user-001-debug.json
└── scenarios/
    ├── identity.json
    ├── fingerprint-check.json
    ├── google-search.json
    ├── behavior.json
    ├── captcha-test-v2.json
    └── consent-test.json
```

`config.json` contains runtime filesystem paths used by the worker. Python runtime code no longer embeds project-specific `/config`, `/identities`, `/artifacts/results`, or browser SOURCE_COMMIT paths.

`default.json` is the canonical complete worker configuration and is read-only to the worker.

`profiles/<name>.json` contains only profile/run overrides. At startup the worker performs a recursive merge:

```text
default.json
    +
profiles/<profile>.json
    +
scenarios/<run.scenario>.json
    ↓
resolved worker configuration
```

Scenarios are now one scenario per file and are reusable by any profile. A worker never modifies `default.json` or scenario files.

The bootstrap files are selected by environment/CLI:
- `WORKER_SYSTEM_CONFIG` or `--system-config`
- `WORKER_PROFILE` or positional profile argument

This keeps the worker autonomous and prepares it for the future Controller without coupling the action engine to Docker orchestration.

## v0.5.18-2 — documentation review

Documentation-only review of v0.5.18. Runtime behavior is unchanged. `../FUTURE.md` was cleaned to contain only unimplemented work; the implemented plugin framework and other completed roadmap items are no longer presented as future features. Runtime actions, Control API endpoints, plugin inventory and documentation coverage were cross-checked.

## v0.5.18-1 — documentation revision

Documentation-only revision of v0.5.18. Runtime behavior is intentionally unchanged. The roadmap now records the rare native mouse-move stall and the planned phase-specific click timeout/error handling plus Playwright pending-future cleanup.

## v0.5.18 — live cursor trajectory in recordings

v0.5.18 fixes `recording.show_cursor` so the red marker now follows the actual `mousemove` events received by the page during Camoufox humanized pointer motion. The marker therefore shows the visible trajectory in recorded video instead of jumping only to the final target point.

Implementation details:
- a lightweight `mousemove` listener is registered through `BrowserContext.add_init_script`;
- every new document/frame receives the listener automatically;
- the current document is initialized immediately;
- the old endpoint update remains only as a fallback;
- the marker remains a simple 14px red circle with `pointer-events: none`.

Configuration is unchanged:

```json
"recording": {
  "video": true,
  "video_size": "default",
  "show_cursor": true
}
```

## v0.5.17 — recording cursor overlay

v0.5.17 adds a simple recording/debug cursor marker. When `recording.show_cursor=true`, a small red circle is injected into the page and moved to the same viewport coordinates used by scripted mouse actions. This makes recorded `.webm` files easier to understand without changing the tested UI interaction.

The marker is:
- visual only (`pointer-events: none`);
- hidden until the first scripted mouse movement;
- re-created after navigation/new tabs/back navigation;
- updated by `mouse_move`, `mouse_move_random`, `click` with `method: "mouse"`, `mouse_press`, and `hover`.

Example:

```json
"recording": {
  "video": true,
  "video_size": "default",
  "show_cursor": true
}
```

`profiles/test-user-001-debug.json` enables it; the canonical `default.json` keeps it disabled.

## v0.5.16-1 — documentation revision

v0.5.16-1 is a documentation/metadata-only revision of the v0.5.16 runtime. No application behavior is intentionally changed.

This revision:
- introduces the `-N` numbering policy for documentation-only releases;
- records the future repository-wide removal of hidden/hardcoded behavioral defaults;
- synchronizes `../FUTURE.md`, `../FUTURE_BOT.md`, `MEMORY.md`, CHANGELOG and release notes.

## v0.5.16 — consent / cookie-banner handler

v0.5.16 implements the previously planned consent automation as the modular `consent-handler` plugin. It supports `accept_all` and `reject_optional`, known-CMP selectors, multilingual generic button-text fallback, main-page and iframe scanning, structured artifacts, and a deterministic local consent test page. The plugin is enabled in the sample configs but performs no action unless explicitly invoked with `plugin_call`.


### Quick consent-handler test

The release includes a deterministic local page:

```bash
docker compose --profile consent-test up -d consent-test-page
```

Set:

```json
"run": {
  "scenario": "consent-test"
}
```

and run the normal/debug Camoufox service. Expected plugin result: `handled=true`, provider `cookieyes`; the final screenshot should show `State: accepted`.


## v0.5.15 — documentation/architecture synchronization

v0.5.15 is a documentation-consistency release. Runtime behavior is unchanged from v0.5.14. All project Markdown files were reviewed against the implemented worker and the approved roadmap. The previously missing Controller/control-plane architecture is now preserved in `../FUTURE.md`, `../FUTURE_BOT.md`, and `MEMORY.md`.

## v0.5.14 — universal physical hover

v0.5.14 adds `hover`, a tag-agnostic selector-based action that waits for a visible element, resolves its bounding box, and physically moves the Camoufox cursor to the center plus an optional offset. Any Playwright/CSS selector may be used, including short CSS-module masks or longer compound selectors. Optional iframe targeting follows the same `frame_selector` / `frames` model as `mouse_press`.

## v0.5.13 — generic mouse press/hold

v0.5.13 adds a reusable `mouse_press` action for long presses and other physical mouse-button interactions. It supports normal selectors, absolute coordinates, one or more iframe levels, configurable mouse button/offsets, and intentional hold duration. The engine watchdog accounts for `hold_ms`, so a 10-second press is not mistaken for a hung action.

## v0.5.12 — outbound webhook integration

v0.5.12 adds a generic outbound HTTP/webhook action. A scenario can request external data, save the response in runtime context, and use it in following actions. An optional FastAPI mock service is included for end-to-end profile-data testing. v0.5.11 tab-switch reliability remains included.

## v0.5.10 — automatic browser tab tracking

v0.5.10 synchronizes scenario tab state with the real Playwright/Camoufox `BrowserContext`. Tabs opened by the site through `target="_blank"`, `window.open()`, or popup flows are now detected automatically and become available to scenario actions. `switch_tab` can wait for a requested tab index to appear and also supports `target: "first"|"oldest"|"last"|"newest"`.

Playwright action timeouts are now reported as concise controlled errors in normal action logs instead of dumping a full Python traceback for expected locator timeout failures. The configuration reference was also renamed from `FUNCTIONS.md` to `CONFIG.md`; all project references were updated.

Example for a site-opened login tab:

```json
{
  "type": "click",
  "selector": "a[data-bi-cn=\"signin\"]:visible",
  "method": "mouse",
  "timeout_ms": 15000
},
{
  "type": "switch_tab",
  "index": 1,
  "timeout_ms": 15000
}
```


## v0.5.9 — hCaptcha direction frozen

v0.5.9 freezes the experimental `hcaptcha-challenger` solver direction after the v0.5.8 live test confirmed that the installed 0.19.x runtime has no stable configuration-only non-Gemini end-to-end local solver. The adapter code is retained for future research, but the plugin remains disabled by default and bundled hCaptcha test scenarios are removed from normal/debug sample configs. `../FUTURE.md` contains the human roadmap; `../FUTURE_BOT.md` preserves the detailed technical continuation context.


Autonomous Firefox execution worker using the Camoufox runtime, with persistent Identities, repeatable browser/device configuration, scenario automation, artifacts, diagnostics, debug/noVNC operation, video recording, plugins, and a versioned Control API.

In debug mode, `recording.video=true` uses X11 display capture by default (`recording.debug_backend="x11"`). This records the complete noVNC/Xvfb session, including manual interaction and tab changes, into `videos/debug-session.webm`. `recording.debug_fps` controls the frame rate (default `15`). The file is finalized during graceful `Ctrl+C`, `docker compose stop`, or `docker compose down` shutdown.



## v0.5.8 hCaptcha non-Gemini decision test

v0.5.8 adds the configuration-only `hcaptcha-challenger.local_solve_test` method. It opens the live hCaptcha challenge through the existing checkbox interaction, verifies the installed `hcaptcha-challenger` runtime for a stable non-Gemini end-to-end solver entry point and packaged local model assets, and **never silently falls back to Gemini**. The test saves `hcaptcha-local-solve-test.json` under the normal run artifacts and returns the controlled reason `hcaptcha_local_solver_unavailable` when the current upstream runtime cannot provide a configuration-only local solver.

Sample scenario: `hcaptcha-local-solve-test`. Use this live result to decide whether the local hCaptcha direction continues or is frozen in favor of a future configurable AI-provider integration.

## v0.5.7 hCaptcha checkbox interaction test

v0.5.7 adds a configuration-only `hcaptcha-challenger.checkbox_test` method. It uses the current Camoufox Playwright page, finds the hCaptcha checkbox iframe, clicks the `I am human` checkbox, and reports whether a visual challenge opened or a response token appeared. It does **not** solve the visual challenge and does not require Gemini.

Sample scenario: `hcaptcha-checkbox-test`.

## v0.5.6 hCaptcha local probe

v0.5.6 adds a user-facing `local_probe` method to the experimental `hcaptcha-challenger` plugin. The probe is invoked only through normal scenario configuration; no source-code edits are required. It inspects the installed upstream package, candidate model/solver modules, packaged ONNX/PT/YAML resources, hCaptcha frames/response fields on the current Camoufox page, and writes `hcaptcha-local-probe.json` to the run artifacts.

This release intentionally does **not** claim a universal local hCaptcha solver. Upstream currently advertises pluggable local ResNet/YOLO/ViT ONNX resources for some challenge types, while the documented high-level AgentV path still uses Gemini. The probe exists so the next local-backend implementation can be based on facts from the real runtime rather than private-API guesses.


## v0.5.5 dropdown + plugin cleanup

v0.5.5 adds a modular `select` action for native HTML `<select>` elements and custom ARIA combobox/listbox dropdowns. The action is implemented as its own `app/actions/select.py` module and is auto-discovered by the existing action registry; `ActionEngine` remains unchanged. The release also suppresses only the known Python 3.12 `pydub` `SyntaxWarning` noise during `playwright-recaptcha` import.

The hCaptcha investigation was also completed: upstream `hcaptcha-challenger` 0.19 exposes local/pluggable ResNet/YOLO/ViT ONNX resources, but its documented high-level `AgentV` workflow still requires Gemini. The Camoufox adapter now exposes a `backend` abstraction (`agentv` or `custom`) so a local/custom vision backend can be plugged in without changing plugin/core code. A universal built-in local solver is intentionally **not** claimed in this release.

## v0.5.4 maintenance / roadmap sync

v0.5.4 keeps the v0.5.3 runtime and plugin set unchanged, but synchronizes the project roadmap and plugin documentation with live validation findings. The experimental `hcaptcha-challenger` adapter remains disabled by default; consent/cookie-banner automation was still future work in v0.5.4; it is implemented later in v0.5.16 as `consent-handler`. See `RELEASE_NOTES.md` and `../FUTURE.md`.

## v0.5.3 experimental hCaptcha adapter

v0.5.3 adds `hcaptcha-challenger==0.19.0` as a second real third-party plugin. It is disabled by default and uses an experimental bridge so the upstream async AgentV can operate on the same underlying Playwright page owned by the synchronous Camoufox runner. A ready `hcaptcha-test-easy` ZennoLab scenario is included for live validation. See `PLUGINS.md` and `RELEASE_NOTES.md`.

## v0.5.2 plugin framework

v0.5.2 builds on the generic plugin/adaptor layer with the first real third-party integration: `playwright-recaptcha` for reCAPTCHA v2. Plugins remain optional, explicitly enabled, lazily imported, and invoked through `plugin_call`; expected plugin failures are now logged as structured errors without duplicate tracebacks.

Plugin configuration lives under `plugins.items.<name>`. Each adapter implements the stable `BasePlugin` lifecycle: `setup(ctx)`, `invoke(method, ctx, params)`, and `teardown(ctx)`. Missing optional Python dependencies do not affect normal runs when the corresponding plugin is disabled.

A dependency-free `EchoPlugin` is included only as a reference/contract test. Adapters for libraries such as `playwright-captcha` and `playwright-recaptcha` can now be added as isolated modules without changing the scenario engine.

Every release includes `RELEASE_NOTES.md`; planned work is tracked in `../FUTURE.md`. Plugin architecture and adapter usage are documented in `PLUGINS.md`.





### First real adapter: playwright-recaptcha

The sample configuration includes a disabled `playwright-recaptcha` adapter and a `captcha-test-v2` scenario. Enable the adapter and select that scenario to test reCAPTCHA v2 against the ZennoLab CAPTCHA test page. The adapter uses `method: "solve_v2"` and the scenario sets `action_timeout_ms: 120000`. See `PLUGINS.md` for the exact configuration and base-image rebuild requirement.

## v0.4.33 locale bridge and warning cleanup

Persisted locale data now goes through Camoufox's public `locale=` API during both Identity generation and normal browser launch. The low-level `locale:*` keys are reconstructed from the persistent Identity and removed from the manual `config` payload before launch, which avoids Camoufox `LeakWarning` messages about manually setting locale.

`fingerprint.locale` remains the authoritative Intl locale. When `fingerprint.languages` is also configured, the runner builds one ordered Camoufox locale list with the primary locale first and any additional accepted languages appended without duplicates. Persistent timezone/geolocation values remain Identity-owned low-level overrides and are acknowledged with `i_know_what_im_doing=true`; normal runs still never pass `geoip=True`, so a proxy cannot rewrite the Identity.

If proxy transport is enabled but network preflight cannot determine `proxy_public_ip`, the runner now emits an explicit warning that proxy GEO validation may be unavailable.


## v0.4.32 persistent location identity

Proxy GEO no longer rewrites a persistent Identity on every run. Camoufox `geoip` is used only when an Identity fingerprint is initially generated or explicitly regenerated with `--update-identity`. Normal browser launches reuse the saved `camoufox_config` as the source of truth for locale, accepted languages, timezone, and geolocation.

When proxy GEO validation is enabled, the runner resolves the proxy exit location separately, compares it with the saved Identity region/timezone, writes `proxy-geo-validation.json`, and logs a warning on mismatch. A mismatch does **not** change the Identity. Set `proxy.geoip.fail_on_mismatch=true` to turn a mismatch into a controlled run failure.

The Identity profile now also supports persistent `fingerprint.languages` and `fingerprint.timezone`. Values set to `default` continue to reuse the values generated and stored in the Identity.

## v0.4.31 action reliability

- Mouse actions now delegate trajectory generation to Camoufox native `humanize`; legacy `steps`/`duration` values remain accepted but are ignored for native-humanized movement.
- Every normal browser action now has a 30-second engine watchdog unless `timeout_ms`/`action_timeout_ms` specifies another deadline. `wait` and `wait_input` keep their own timing semantics.
- Camoufox startup is validated before diagnostics and scenario actions begin. If the browser closes during first-run initialization (for example while preparing an addon), the worker retries up to `browser.startup_attempts` times (default `3`), waiting `browser.startup_retry_delay_sec` seconds (default `1.0`) between attempts.
- Browser shutdown is bounded to 4 seconds. If Camoufox/Playwright cleanup hangs after a fatal action, child browser processes are terminated and the runner continues finalization instead of requiring Ctrl+C.
- Fatal action timeouts therefore end the container with `Result: FAIL` and exit code `1`.

## v0.4.30 modular scenario action framework

The scenario layer is now modular. `ActionEngine` is an orchestration layer only: it resolves runtime templates, dispatches actions through `ActionRegistry`, records PASS/FAIL results, and applies error/shutdown policy. Concrete browser behavior lives under `app/actions/`.

Built-in action modules are discovered automatically. To add a new scenario action, create a Python module under `app/actions/`, implement `BaseAction`, and decorate the class with `@register_action`. No changes to `ActionEngine` or the scenario base class are required. Existing JSON scenarios and action names remain compatible.

Core pieces:

- `app/actions/engine.py` — action orchestration and result/error policy.
- `app/actions/context.py` — shared `ScenarioContext` with browser context, current page/tabs, artifacts, logger, and runtime input context.
- `app/actions/registry.py` — action registration and lookup.
- `app/actions/base.py` — common action contract.
- Other modules under `app/actions/` — concrete scenario functionality.

See `SCENARIO.md` for the extension contract and current action catalog.

## v0.4.27 proxy cleanup

Proxy runtime support is intentionally limited to HTTP/HTTPS. SOCKS proxies are deprecated and rejected cleanly before browser startup. Proxy policy/configuration failures now use machine-readable failure reasons without Python tracebacks. Network diagnostics use `proxy_public_ip`, and `proxy.verify_ssl` controls TLS verification for proxy preflight diagnostics (default `true`). See `CONFIG.md` for the complete proxy reference.

## v0.4.26 layered Docker development build

The heavy browser/runtime is now built once as a reusable base image. Application releases inherit that image and copy only `app/` and `scripts/` into small top layers.

Build the base image when the custom browser or runtime dependencies change:

```bash
```

For normal development builds after Python/script edits, reuse the base image:

```bash
docker compose build
```



## v0.4.23 Identity Profile Configuration

Each Identity now has a persistent `config.json` next to `identity.json` and the browser profile. Runtime JSON values set to `"default"` inherit from this Identity profile. If the profile also contains `"default"`, the already generated Identity fingerprint value is reused. Profile changes apply only to the next run.

Every run stores `resolved-profile.json` in its artifacts. The Control API exposes `GET` and `PATCH /api/v1/identities/{identity}/config`. See `CONFIG.md` and `API.md`.

The debug Xvfb desktop defaults to `2560x1600x24` so the persistent Identity window is not clamped to the old 1440x900 debug desktop.

## Documentation

- `CONFIG.md` — JSON/CLI configuration and action reference.
- `SCENARIO.md` — scenario actions, `wait_input`, runtime templates, and error policy.
- `API.md` — current worker Control API endpoints and future Controller boundary.
- `PLUGINS.md` — plugin framework and adapter status.
- `CHANGELOG.md` — detailed worker version history.
- `RELEASE_NOTES.md` — current release notes.
- `../FUTURE.md` — concise human roadmap.
- `../FUTURE_BOT.md` — detailed continuation context for deferred work.
- `../AGENT.md` — durable agent memory, project handoff, release rules and documentation index.
- `../CHANGELOG.md` — global release history for all application components.
- `../tools/firefox-image-builder/README.md` — standalone base-image builder guide.
- `../tools/firefox-image-builder/CHANGELOG.md` — builder version history.
- `../data-provider/README.md` — standalone worker data-resolution service.

## Build

`worker-firefox` does not build the heavy browser runtime itself.

First make sure a compatible base image already exists, for example:

```bash
docker image inspect worker-firefox-base:152.0.4-beta.28
```

If it does not exist, build it separately with the `firefox-image-builder` tool.

Then build the worker application image:

```bash
docker compose build worker-firefox
```

Select another prepared base image without editing the Dockerfile:

```bash
WORKER_FIREFOX_BASE_IMAGE=worker-firefox-base:153.0.0-beta.1 \
docker compose build worker-firefox
```

The worker archive does not contain `camoufox-custom.zip`, `SOURCE_COMMIT`, or base-image build tooling.

## Normal run

Default sample profile:

```bash
docker compose up worker-firefox
```

Select another profile without editing `default.json`:

```bash
WORKER_PROFILE=test-user-004 docker compose up worker-firefox
```

Control API is published on port `8090` by the supplied compose file.

## Debug run

Default debug sample profile:

```bash
docker compose --profile debug up worker-firefox-debug
```

Select another debug launch profile:

```bash
WORKER_DEBUG_PROFILE=test-user-004-debug docker compose --profile debug up worker-firefox-debug
```

noVNC is available on port `6080`; Control API remains on port `8090`.

## Version

```bash
docker compose run --rm worker-firefox python -m app.main --version
```


## v0.4.20 lifecycle and shutdown

Debug-mode shutdown now handles SIGINT/SIGTERM gracefully: browser/video artifacts are finalized before noVNC/X11 helper processes are stopped. See `CONFIG.md` for shutdown semantics.

### v0.4.23 notes

Identity fingerprint profile changes now automatically mark the old diagnostics baseline stale and refresh it on the next run. The Dockerfile was also reduced to a slim runtime and no longer downloads a second, unused official Camoufox browser.

### Custom browser registration

The runtime image does not download a second official Camoufox browser. The prebuilt `/opt/camoufox-custom` bundle is registered with Camoufox 0.5.x package-manager metadata and exposed through a symlink under `~/.cache/camoufox/browsers/official/152.0.4-beta.28`.

### v0.4.30 action watchdog

Scenario browser actions can no longer remain blocked indefinitely merely because a synchronous Camoufox/Playwright operation fails to return. Actions with `timeout_ms` receive an engine-level emergency watchdog, and `action_timeout_ms` is available when an explicit hard deadline is required. `click` also logs each internal phase to simplify diagnosis of selector/geometry/mouse stalls.
