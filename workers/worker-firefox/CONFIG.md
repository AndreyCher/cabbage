# Configuration architecture — v0.5.19

> Component files live in `workers/worker-firefox/`. Run Docker Compose commands from the repository root; file paths in this document are relative to the component directory unless stated otherwise.

The worker no longer uses one monolithic `test.json`.


## Project/component metadata — v0.5.20

`config/config.json` owns internal project/component metadata:

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

`project.name` is an internal configurable codename. Application code, Docker service names and Controller API contracts must not depend on its concrete value.

`worker.type` identifies the execution backend. The current value is `firefox`; the architecture reserves neutral values such as `android` for future workers.

The worker exports this metadata in startup logs, `summary.json`, and `/api/v1/health`.

Project-owned environment variables use the `WORKER_` prefix. Runtime/vendor-specific variables keep their vendor namespace.

## `config/config.json` — bootstrap path map

This is the only bootstrap configuration. It contains paths rather than browser/scenario behavior:

```json
{
  "schema_version": 1,
  "paths": {
    "global_default_config": "/workers-config/default.json",
    "local_default_config": "/config/default.json",
    "profiles_dir": "/config/profiles",
    "global_scenarios_dir": "/workers-config/scenarios",
    "local_scenarios_dir": "/config/scenarios",
    "identities_dir": "/identities",
    "artifacts_dir": "/artifacts",
    "browser_source_commit": "/opt/camoufox-custom/SOURCE_COMMIT"
  }
}
```

The path to this file itself is supplied through `WORKER_SYSTEM_CONFIG` or `--system-config`; it is not hardcoded in Python.

Relative values in `paths` are resolved relative to the directory containing `config.json`.

OS/kernel inspection paths such as `/proc` and `/sys` used by diagnostics are structural Linux interfaces, not application storage/configuration paths, and remain implementation constants.

## Global and local `default.json`

`workers/config/default.json` is required and contains the complete shared worker configuration. `workers/worker-firefox/config/default.json` is optional. The resolver always checks for the local file and, when present, recursively merges it over the global defaults.

A profile is then recursively merged over the resolved defaults. Lists/scalars replace the earlier value; nested objects are merged. Neither default file may embed scenarios.

## `config/profiles/<profile>.json` — launch profile overrides

A profile contains identity-specific and run-specific changes only. Example:

```json
{
  "identity": "test-user-004",
  "run": {
    "scenario": "trustpilot-registration"
  },
  "fingerprint": {
    "locale": "fr-FR",
    "languages": ["fr-FR", "fr"],
    "timezone": "Europe/Paris"
  },
  "recording": {
    "show_cursor": true
  }
}
```

Profiles must not embed a `scenarios` object.

Do not confuse these launch profiles with the persistent Identity override file under `identities/<identity>/config.json`, which is managed by the existing Identity Profile API.

## Global and local scenarios

Shared scenarios live in `workers/config/scenarios/<scenario>.json`. Optional worker-specific scenarios live in `workers/worker-firefox/config/scenarios/<scenario>.json`.

Example:

```json
{
  "name": "trustpilot-registration",
  "version": 1,
  "actions": [
    {
      "type": "open",
      "url": "https://example.com"
    }
  ]
}
```

`run.scenario` contains the simple scenario name. The resolver first checks the local scenario directory. If the named local file exists, it replaces the global file completely. Otherwise the global scenario is loaded. Scenario files are never merged or compared. Path traversal is rejected and the optional `name` field must match `run.scenario`.

## Resolution order

```text
workers/config/default.json (required)
  -> workers/worker-firefox/config/default.json (optional deep merge)
  -> local profile overrides
  -> selected external scenario
  -> worker runtime
```

The selected external scenario is inserted into the existing internal runtime contract only after validation; action modules do not need to know where it was stored.


# Configuration reference

Canonical configuration reference since v0.5.10. This file was previously named `FUNCTIONS.md`; the old filename has been removed.

This document describes top-level JSON configuration. Scenario actions are documented in `SCENARIO.md`; HTTP endpoints are documented in `API.md`.

## `identity`

Persistent Identity name, for example `test-user-001`. It is the primary resource identifier in the Control API and the root for persistent browser profile/device state.

## `identity_policy`

`allow_proxy_change` controls whether an existing Identity may be launched with a different `proxy_id`.

## `run`

`scenario` selects the scenario under `scenarios`.

## `api`

```json
"api": {
  "enabled": true,
  "host": "0.0.0.0",
  "port": 8090
}
```

- `enabled` — enable the Control API. Default: `true`.
- `host` — bind address inside the container. Default: `0.0.0.0`.
- `port` — listen port. Default: `8090`.

See `API.md` for the complete API contract.

## `browser`

- `mode` — `virtual` or `debug`.
- `humanize` — Camoufox humanization factor.
- `enable_cache` — browser cache setting.
- `version` — Camoufox browser version requested by the launcher.

## `recording`

- `video` — enable full-session video recording.
- `backend` — normal-run recording backend; `x11` (default) captures the hidden Xvfb display through FFmpeg into one `videos/session.webm`. It does not enable debug mode or noVNC.
- `video_size` — retained for the optional legacy Playwright backend; X11 capture follows the resolved display size.
- `debug_backend` — debug-mode recording backend; `x11` (default) captures the complete Xvfb/noVNC display into `videos/debug-session.webm`.
- `debug_fps` — X11 recording frame rate for normal and debug runs, default `15`.

Browser startup readiness is controlled by:

- `browser.startup_attempts` — maximum Camoufox startup attempts after transient context/browser closure, default `3`.
- `browser.startup_retry_delay_sec` — delay between startup attempts, default `1.0` seconds.

## `fingerprint_diagnostics`

- `enabled`
- `save_snapshot`
- `compare_with_baseline`
- `update_baseline`
- `fail_on_change`

These settings control browser-side fingerprint snapshots and drift comparison.

## `vm_diagnostics`

- `enabled`
- `save_snapshot`
- `compare_with_baseline`
- `update_baseline`
- `keep_history`
- `label`

VM diagnostics are diagnostic data and do not by themselves determine scenario PASS/FAIL.

## `proxy`

- `enabled`
- `proxy_id` — stable logical proxy identity used by Identity policy.
- `server`
- `username`
- `password`
- `geoip` — boolean (legacy) or GEO policy object

## `fingerprint`

- `os`
- `preset`
- `screen`
- `locale`

The value `default` means the option is intentionally omitted and Camoufox owns default generation. Persistent generated device configuration is stored in Identity metadata.

## Scenario action framework (v0.4.30)

Scenario functionality is implemented as automatically discovered modules under `app/actions/`. The public runtime contract remains the same: `scenarios.<name>.actions` is an ordered list of dictionaries with a required `type`.

Framework components are `BaseAction`, `ScenarioContext`, `ActionRegistry`, and `ActionEngine`. `ActionEngine` contains orchestration/error policy only; concrete action behavior belongs in registered modules. Existing action names and configuration are backward compatible. See `SCENARIO.md` for the extension example and complete action reference.

This separation is intentionally designed so future browser actions, API actions, conditions, loops, extraction steps, or other scenario capabilities can be added as modules without rewriting the base engine.

## `scenarios`

`scenarios` is no longer authored inside `default.json` or profile files. It is an internal resolved-runtime field populated from `config/scenarios/<run.scenario>.json`. See `SCENARIO.md`.

## `debug`

- `keep_alive` — leave the browser/container alive for manual noVNC control after automated actions finish.
- `message` — optional message written to the debug log.

In debug mode ordinary action failures continue by default. Explicit fatal runtime-input timeout policy is not suppressed.

## CLI

Container deployments normally set:

```text
WORKER_SYSTEM_CONFIG=/config/config.json
WORKER_PROFILE=test-user-001
```

The equivalent explicit invocation is:

```bash
python -m app.main test-user-001 --system-config /config/config.json
```

An explicit profile JSON path may be used instead of a profile name.

`--version` prints the application version.

`--reset-identity` deletes the configured persistent Identity and profile before recreating it.

`--update-identity` regenerates fingerprint/device configuration while preserving the existing browser profile.

## Artifacts

Run artifacts are stored below `paths.artifacts_dir`:

```text
{artifacts_dir}/{identity}/{scenario}/{run_id}/
```

With the supplied `config/config.json` this resolves to `/artifacts/<identity>/<scenario>/<run-id>/`.

v0.4.16 run IDs contain UTC timestamp plus a short random suffix, e.g. `20260812T101500Z-a8f3`.

`runtime-events.json` stores runtime event metadata but never the submitted input payload itself.


## Result reason codes (v0.4.17)

Controlled failures expose a machine-readable `reason` in `summary.json`. Runtime input timeout currently uses `timeout_data_not_received`. Unexpected internal failures use `unexpected_error` and retain traceback logging.


## Graceful shutdown (v0.4.20)

In debug mode with `debug.keep_alive=true`, SIGINT (Ctrl+C) and SIGTERM (for example `docker compose down`) request a controlled shutdown. The application first leaves interactive mode, closes the Camoufox context, finalizes local video artifacts, stops the Control API, writes `summary.json`, and exits. The container entrypoint then stops Xvfb/Openbox/x11vnc/websockify.

The worker definition included by root `compose.yml` sets `stop_grace_period` so Docker does not immediately force-kill the container while artifacts are being finalized.

`summary.json` contains:

```json
{
  "shutdown": {
    "requested": true,
    "signal": 15,
    "reason": "user_interrupt",
    "graceful": true
  }
}
```

The final log message for a controlled SIGINT/SIGTERM shutdown is:

```text
Container stoping bye
```


### Global shutdown controller

From v0.4.20, SIGINT and SIGTERM are handled from application startup, not only after the scenario enters interactive debug mode. A shutdown request can therefore interrupt `wait`, `wait_input`, scenario execution, or interactive debug mode.

A requested shutdown produces run status `STOPPED`, reason `user_interrupt`, performs artifact/video finalization, stops the Control API, logs `Container stoping bye`, and exits the container with code `0`.

## Identity Profile Configuration (v0.4.23)

Each Identity now owns a persistent configuration file:

```text
/identities/<identity>/config.json
```

It is separate from `identity.json` (generated fingerprint metadata) and `profile/` (Firefox/Camoufox browser state).

The run JSON `fingerprint` block supports:

```json
"fingerprint": {
  "os": "default",
  "preset": "default",
  "screen": "default",
  "locale": "default",
  "window": "default",
  "device_pixel_ratio": "default",
  "hardware_concurrency": "default",
  "webgl": "default"
}
```

Resolution priority is:

```text
explicit run JSON value
        -> Identity config.json value
        -> persistent generated Identity value
```

Therefore `"default"` in the run JSON means **inherit from the Identity profile**, not generate a fresh value. If the Identity profile also says `"default"`, the value already stored in the persistent Camoufox fingerprint is reused.

Supported profile values:

- `os`: `"default"`, `"windows"`, `"macos"`, `"linux"`, or a Camoufox-supported list.
- `preset`: `"default"`, `true`, or `false`.
- `screen`: `"default"` or BrowserForge constraints such as `{"max_width":1920,"max_height":1080}`.
- `locale`: `"default"`, a locale string, or supported locale list.
- `window`: `"default"` or `{"width":1680,"height":1390}`. With `default`, the outer window generated for the Identity is reused on every run.
- `device_pixel_ratio`: `"default"` or a positive number.
- `hardware_concurrency`: `"default"` or a positive integer.
- `webgl`: `"default"` or `{"vendor":"...","renderer":"..."}`. Only use coherent vendor/renderer pairs supported for the selected OS.

Changes to `os`, `preset`, `screen`, or `locale` are generation-level changes. On the next run, the persistent Camoufox fingerprint is regenerated while the browser profile directory is preserved. Direct settings (`window`, DPR, hardware concurrency, WebGL vendor/renderer) are layered onto the saved fingerprint without regenerating all seeds.

Profile updates never mutate an already-running browser session. They apply to the next run.

Every run saves the effective settings to:

```text
<run artifacts>/resolved-profile.json
```

This file is the authoritative record of the profile configuration and fingerprint values used for that run.

### Debug display geometry

The debug service uses:

```yaml
DEBUG_DISPLAY_SIZE: "2560x1600x24"
```

This is the Xvfb desktop size, not the JavaScript-exposed screen fingerprint. It was increased so the window manager does not clamp a persistent Identity window to the previous 1440x900 debug desktop. It can be overridden through the environment if a profile needs a larger desktop.

## Fingerprint baseline stale state (v0.4.23)

Each Identity profile config contains `baseline_stale` (boolean). It is managed by the service and should not be patched directly.

- `false`: the persisted fingerprint baseline is valid for the current Identity profile settings.
- When `PATCH /api/v1/identities/{identity}/config` actually changes any `fingerprint` value, the service sets `baseline_stale` to `true`.
- On the next run with `fingerprint_diagnostics.enabled=true`, the current fingerprint snapshot becomes the new baseline automatically. The old baseline is not treated as drift, and `baseline_stale` is written back to `false`.
- No profile revision/version counter is used.

### Runtime image optimization

The prepared `worker-firefox-base` image contains the custom Camoufox browser and its runtime dependencies. The worker consumes that image and uses `CAMOUFOX_EXECUTABLE_PATH=/opt/camoufox-custom/camoufox-bin`. Base-image construction details belong to the separate `firefox-image-builder` tool.

## Camoufox runtime registration

Firefox worker uses the prebuilt custom browser from `/opt/camoufox-custom`. Camoufox 0.5.x still requires package-manager installation metadata before launch, so the Docker image creates a minimal active `official/stable` registration. The browser path in the Camoufox cache is a symlink to the custom bundle and does not duplicate browser data.


## v0.4.24 Docker build note

Runtime functionality is unchanged from v0.4.23. The Docker build is split into a stable browser/runtime base image and a small application image to maximize layer reuse during development.

## Debug display (`browser.debug_display`) — v0.4.25

Used only when `browser.mode` is `debug`; it does not change the stored fingerprint profile.

```json
"debug_display": {
  "size": "identity",
  "fallback": {"width": 1920, "height": 1080},
  "depth": 24,
  "window": "maximized",
  "position": {"x": 0, "y": 0},
  "novnc_scaling": "local"
}
```

- `size`: `identity` uses the persisted identity `fingerprint.window` as the Xvfb desktop size; `custom` uses `width`/`height` from this block.
- `fallback`: used when the identity has no explicit persisted window size.
- `depth`: Xvfb color depth, default `24`.
- `window`: `maximized` or `normal`.
- `position`: initial Openbox placement. `{x:0,y:0}` pins the browser to the top-left corner.
- `novnc_scaling`: `local` uses noVNC local canvas scaling (`resize=scale`) and never resizes the remote X11 session; other values use `resize=off`.

With `size: "identity"` and `window: "maximized"`, the debug desktop follows the identity outer window size, avoiding the large unused black area while keeping the same persistent browser geometry.

`NOVNC_VIEW_ONLY=true` is a container-level access control used by Controller.
It adds x11vnc `-viewonly`, so connected clients cannot inject keyboard or
pointer events. It defaults to `false` to preserve interactive standalone debug
operation and is not part of Identity or scenario configuration.


## VM diagnostics logging — v0.4.26

VM diagnostics still capture the complete raw host/browser snapshot and full cross-run diff in artifacts. Console logging is intentionally compact. Large fields such as `host.x11.xdpyinfo`, `host.memory.meminfo`, and `host.proc.status` are summarized instead of dumping their full multi-line contents into stdout/run.log. Capture timestamps are kept in JSON artifacts but omitted from detailed console drift lines.

Example console output:

```text
VM diagnostics cross-run drift: changed=4 added=0 removed=0 same=135 (full diff saved to artifacts)
  VM DIAG CHANGED host.x11.xdpyinfo: size=1440x900, dpi=100x100, depth=24, visuals=390, vendor=The X.Org Foundation, xorg=1.21.1.7 -> size=1680x1390, dpi=100x100, depth=24, visuals=390, vendor=The X.Org Foundation, xorg=1.21.1.7
  VM DIAG CHANGED host.memory.meminfo: MemTotal=4015392 kB, MemAvailable=2619924 kB, ... -> MemTotal=4015392 kB, MemAvailable=2489276 kB, ...
```

The complete values remain available under `vm-diagnostics/snapshot.json` and `vm-diagnostics/diff.json`.

## Proxy configuration — v0.4.27

Firefox worker supports HTTP and HTTPS proxy endpoints. SOCKS4/SOCKS5 are deprecated and rejected before browser startup with `reason: unsupported_proxy_type`; expected proxy configuration/policy errors do not emit Python tracebacks.

```json
"proxy": {
  "enabled": true,
  "proxy_id": "test-proxy-001",
  "server": "http://proxy.example.com:10000",
  "username": "proxy-user",
  "password": "proxy-password",
  "geoip": true,
  "verify_ssl": true
}
```

- `enabled`: enables proxy use.
- `proxy_id`: stable logical proxy identifier stored with the Identity. Changing it is blocked unless `identity_policy.allow_proxy_change=true`.
- `server`: proxy endpoint. Supported schemes are `http://` and `https://`.
- `username` / `password`: optional proxy authentication credentials.
- `geoip`: controls GEO-assisted Identity generation/update and validation. It is intentionally **not** passed to normal browser launches, so proxy changes cannot rewrite persistent locale/timezone/geolocation.
- `verify_ssl`: default `true`. Controls TLS certificate verification for the proxy network-preflight request. Set to `false` only for a trusted provider whose HTTPS proxy endpoint cannot pass certificate validation. This does not globally disable TLS validation inside browser pages.

Network diagnostics now report `proxy_public_ip` instead of the protocol-specific `proxy_http_ip` and include `proxy_verify_ssl`.

Expected proxy failure reasons include `unsupported_proxy_type`, `proxy_change_not_allowed`, `proxy_configuration_error`, `authentication_failed`, `connection_timeout`, `tls_validation_failed`, and `proxy_connection_failed`. These end the run as `FAIL` with exit code 1 but without an application traceback. Truly unexpected exceptions still include a traceback.

## Hard action watchdog (v0.4.30)

The action engine now protects browser actions with an independent hard watchdog. When an action contains `timeout_ms`, the engine arms a watchdog for that timeout plus a 2-second transport-unwind grace period. `action_timeout_ms` can be used to set an explicit watchdog on any action. Watchdog expiration produces the controlled failure reason `action_timeout` rather than leaving the container running indefinitely.

`click` additionally uses `timeout_ms` as a single end-to-end deadline across its internal phases. Phase-level log messages identify whether execution reached visibility detection, bounding-box calculation, mouse movement, or the final click.


## Action reliability and shutdown (v0.4.31)

Mouse movement uses Camoufox native humanization directly (`page.mouse.move(x, y)` without Playwright `steps`). Existing scenario fields `mouse_move.duration`, `mouse_move.steps`, and `click.steps` remain accepted for backward compatibility but are ignored while native humanization is used.

All regular browser actions receive a 30-second hard engine watchdog by default. Explicit `action_timeout_ms` overrides it; actions with `timeout_ms` use that timeout plus the transport grace period. `wait` and `wait_input` are exempt because they have explicit scenario-controlled timing.

Camoufox context shutdown is also bounded. If browser cleanup does not return within 4 seconds, the runner terminates its browser/helper child processes, records `browser_cleanup.status=forced`, finalizes available artifacts, logs `Result: FAIL`, and exits with code 1 for failed runs.


## Persistent Identity location and proxy GEO validation (v0.4.32)

A normal proxy connection no longer mutates locale, languages, timezone, or geolocation stored in the Identity. `geoip` is evaluated during initial Identity generation / `--update-identity`; subsequent runs launch the saved `camoufox_config` unchanged.

Preferred proxy configuration:

```json
"proxy": {
  "enabled": true,
  "proxy_id": "de-proxy-01",
  "server": "http://proxy.example.com:10000",
  "username": "proxy-user",
  "password": "proxy-password",
  "geoip": {
    "enabled": true,
    "validate_identity": true,
    "fail_on_mismatch": false
  },
  "verify_ssl": true
}
```

`geoip.enabled` enables GEO-assisted Identity generation/update and GEO validation. `geoip.validate_identity` checks the current proxy exit against the saved Identity. `geoip.fail_on_mismatch=false` logs warnings only; `true` fails with `proxy_identity_geo_mismatch`. The legacy boolean form (`"geoip": true`) maps to enabled validation with warning-only mismatch handling.

Identity/profile fingerprint settings now include:

```json
"fingerprint": {
  "locale": "en-US",
  "languages": ["en-US", "en"],
  "timezone": "America/New_York"
}
```

All three can be `"default"`. For an existing Identity, `default` means reuse the already persisted generated value, not regenerate from the current proxy.

Each run writes `proxy-geo-validation.json` with the proxy GEO snapshot, saved Identity location fields, comparison result, and mismatch details. GEO lookup failure is diagnostic-only and does not abort a run.


## Locale handling bridge (v0.4.33)

`fingerprint.locale` is passed through Camoufox's public `locale=` API rather than injected as manual `locale:*` config keys. If `fingerprint.languages` is also set, the effective Camoufox locale list is built as:

```text
[primary locale] + [additional accepted languages, de-duplicated]
```

For example:

```json
"fingerprint": {
  "locale": "de-DE",
  "languages": ["en-US", "en", "de-DE", "de"],
  "timezone": "Europe/Berlin"
}
```

becomes an effective Camoufox locale list equivalent to:

```json
["de-DE", "en-US", "en", "de"]
```

The first locale remains authoritative for Intl/browser language consistency. On normal launches, persisted `locale:*` fields are removed from the manual Camoufox `config` payload and reconstructed through `locale=`. Persistent timezone/geolocation remain intentional Identity-level overrides; the runner acknowledges these with `i_know_what_im_doing=true` instead of allowing `geoip=True` to silently replace them.

If proxy is enabled but `proxy_public_ip` cannot be resolved during network preflight, the log contains an explicit warning. GEO validation remains diagnostic unless strict mismatch policy is enabled.

## Plugin configuration (v0.5.1)

Third-party integrations are configured independently of scenarios:

```json
"plugins": {
  "enabled": true,
  "items": {
    "echo": {
      "enabled": true,
      "adapter": "app.plugins.echo:EchoPlugin",
      "config": {}
    }
  }
}
```

- `plugins.enabled` — global plugin subsystem switch. Default: `true`.
- `plugins.items` — named plugin definitions.
- `enabled` — imports/activates that plugin only when `true`.
- `adapter` — Python `module:Class` path. The class must inherit `BasePlugin`.
- `config` — plugin-specific JSON object passed to the adapter constructor.

Disabled plugins are never imported, so optional third-party dependencies may be absent from the runtime image until an adapter actually needs them.


## Plugin configuration update (v0.5.2)

The canonical plugin adapter format is `adapter: "module:Class"`. The canonical scenario call uses `method`, not `operation`. See `PLUGINS.md` for the full contract.

`playwright-recaptcha` adapter example:

```json
"plugins": {
  "enabled": true,
  "items": {
    "playwright-recaptcha": {
      "enabled": true,
      "adapter": "app.plugins.playwright_recaptcha:PlaywrightRecaptchaPlugin",
      "config": {
        "default_wait": true,
        "image_challenge": false
      }
    }
  }
}
```

`solve_v2` params: `wait` (boolean, default from plugin config) and `image_challenge` (boolean). Image mode requires a CapSolver API key. Use `action_timeout_ms` on the `plugin_call` action for long-running solves.

## hcaptcha-challenger plugin parameters (v0.5.3)

Plugin config supports:

- `click_checkbox` — whether the adapter should click the hCaptcha checkbox before waiting for/solving the challenge; default `true`.
- `disable_bezier_trajectory` — asks the upstream agent not to add its own Bezier mouse trajectory so Camoufox remains responsible for browser-level humanization; default `true`.
- `debug` — enables upstream challenger debug output when supported; default `false`.

`plugin_call` supports methods `solve` and alias `solve_checkbox`. Use a longer `action_timeout_ms` (sample: `180000`) because model/challenge work may exceed the normal browser-action watchdog.

## `select` action parameters (v0.5.5)

| Field | Type | Default | Description |
|---|---|---|---|
| `selector` | string | required | Dropdown trigger / native `<select>` selector. |
| `value` | string | — | Select by option value. Mutually exclusive with `label` and `index`. |
| `label` | string | — | Select by visible option label. Mutually exclusive with `value` and `index`. |
| `index` | integer | — | Zero-based option index. Mutually exclusive with `value` and `label`. |
| `method` | `auto`/`native`/`custom` | `auto` | Native detection or forced interaction mode. |
| `option_selector` | string | — | Optional site-specific option selector for custom dropdowns. |
| `exact` | boolean | `true` | Exact accessible-name match when custom selection uses `label`. |
| `timeout_ms` | integer | `15000` | Visibility/interaction timeout. |

Exactly one of `value`, `label`, or `index` is required.

### hcaptcha-challenger backend parameters (v0.5.5)

`config.backend` / `params.backend` supports `agentv` (default) and `custom`. `agentv` remains Gemini-backed upstream. `custom` requires `backend_adapter: "module:Class"`; the class is instantiated with `backend_config` and must expose `solve(page, params)`. Use plugin method `capabilities` to inspect the adapter without requiring Gemini.



### `hcaptcha-challenger.checkbox_test` (v0.5.7)

Configuration-only hCaptcha interaction probe. Finds the checkbox iframe on the current page and clicks `#checkbox` (with semantic fallbacks). Does not invoke AgentV/Gemini and does not solve image challenges.

Parameters:
- `timeout_ms`: per-locator interaction timeout, default `15000`.
- `post_click_wait_ms`: delay after click before state inspection, default `1500`.

Returns checkbox/challenge/response diagnostics.


### `hcaptcha-challenger.local_solve_test` (v0.5.8)

Configuration-only non-Gemini feasibility test. The method clicks/opens the hCaptcha challenge using the current Camoufox page, inspects the installed upstream package for stable non-Gemini end-to-end entry points and packaged model assets, and writes `hcaptcha-local-solve-test.json`. It never invokes `AgentV` and never falls back to Gemini.

```json
{
  "type": "plugin_call",
  "plugin": "hcaptcha-challenger",
  "method": "local_solve_test",
  "params": {
    "timeout_ms": 15000,
    "post_click_wait_ms": 1800
  },
  "action_timeout_ms": 30000,
  "continue_on_error": true
}
```

Expected controlled negative result when no stable local solver is available: `reason=hcaptcha_local_solver_unavailable`.

### `hcaptcha-challenger.local_probe` (v0.5.6)

`plugin_call` method with no required params. It performs a non-solving local capability probe against the current Camoufox page and saves `hcaptcha-local-probe.json` in the run artifact directory. It does not require `GEMINI_API_KEY`.


## v0.5.9 hCaptcha plugin status

`hcaptcha-challenger` is frozen/experimental and disabled by default. Its adapter methods remain in code for future research, but hCaptcha sample scenarios are no longer bundled. Detailed continuation context is stored in `../FUTURE_BOT.md`.


## v0.5.11 compatibility note

No configuration schema changed in v0.5.11. Existing `switch_tab.index`, `switch_tab.target`, and `switch_tab.timeout_ms` syntax remains compatible; only the runtime waiting behavior was fixed.


## `webhook` action
- `url` (required): HTTP endpoint.
- `method`: HTTP method; default `POST`.
- `headers`, `params`, `json`, `data`: request values; normal runtime template resolution applies before execution.
- `timeout_ms`: per-request timeout, default 10000.
- `retries`: additional attempts after the first, default 0.
- `save_as`: runtime response key, default `response`.
- `on_error`: `fail` or `continue`, default `fail`.
- JSON response fields are referenced as `{{webhook.<save_as>.<path>}}`.


## `mouse_press` action (v0.5.13)

Physically moves the Camoufox pointer to a target, calls mouse down, waits, and calls mouse up.

Targeting requires exactly one of:
- `selector`: DOM selector to target.
- `position`: absolute viewport coordinates, e.g. `{"x": 920, "y": 540}`.

Optional frame targeting:
- `frame_selector`: selector for one iframe containing the target.
- `frames`: ordered list of iframe selectors for nested frame chains.
- Frame targeting applies only with `selector`, not with absolute `position`.
- Cross-origin iframe content is supported through Playwright's frame-locator API.

Other parameters:
- `button`: `left` (default), `right`, or `middle`.
- `hold_ms`: duration between mouse down and mouse up; default `1000`, minimum `0`.
- `timeout_ms`: target lookup/bounding-box timeout; default `15000`.
- `offset`: optional pixel offset from the target center: `{"x": 0, "y": 0}`.
- `action_timeout_ms`: optional explicit hard engine timeout. If omitted, `mouse_press` automatically receives a hard watchdog budget of `timeout_ms + hold_ms + watchdog grace`.

Example:

```json
{
  "type": "mouse_press",
  "selector": "#holdButton:visible",
  "button": "left",
  "hold_ms": 10000,
  "timeout_ms": 15000
}
```

Iframe example:

```json
{
  "type": "mouse_press",
  "frame_selector": "iframe[src*=\"verification\"]",
  "selector": "div[role=\"button\"]:has(#checkmark):has(#ripple):visible",
  "button": "left",
  "hold_ms": 10000,
  "timeout_ms": 15000
}
```

Nested iframe example:

```json
{
  "type": "mouse_press",
  "frames": [
    "iframe#outer",
    "iframe#inner"
  ],
  "selector": "#target:visible",
  "hold_ms": 5000,
  "timeout_ms": 15000
}
```

Coordinate example:

```json
{
  "type": "mouse_press",
  "position": {"x": 920, "y": 540},
  "button": "left",
  "hold_ms": 3000,
  "timeout_ms": 5000
}
```


## `hover` action (v0.5.14)

Moves the physical Camoufox mouse pointer over a visible element without clicking.

Parameters:
- `selector` (required): any valid Playwright/CSS selector. The action is not tied to a specific HTML tag.
- `timeout_ms`: time allowed to find the visible target and obtain its bounding box; default `15000`.
- `offset`: optional center-relative pixel offset, e.g. `{"x": 15, "y": -10}`.
- `frame_selector`: optional selector for one iframe containing the target.
- `frames`: optional ordered list of iframe selectors for nested frame chains.

Short generic selector:

```json
{
  "type": "hover",
  "selector": "[class*=\"styles_displayName__\"]:visible",
  "timeout_ms": 15000
}
```

Longer compound selector:

```json
{
  "type": "hover",
  "selector": "[class*=\"styles_displayName__\"][data-navigation-consumer-name-label=\"true\"]:visible",
  "timeout_ms": 15000
}
```

Precise positioning:

```json
{
  "type": "hover",
  "selector": "button[data-testid=\"profile\"]:visible",
  "offset": {
    "x": 15,
    "y": -10
  },
  "timeout_ms": 15000
}
```

Iframe example:

```json
{
  "type": "hover",
  "frame_selector": "iframe[data-testid=\"contentFrame\"]",
  "selector": "a[href^=\"/users/\"]:visible",
  "timeout_ms": 15000
}
```

`offset` is calculated from the center of the target bounding box:
- positive `x` = right;
- negative `x` = left;
- positive `y` = down;
- negative `y` = up.


## Consent handler plugin (v0.5.16)

Top-level sample:

```json
{
  "plugins": {
    "enabled": true,
    "items": {
      "consent-handler": {
        "enabled": true,
        "adapter": "app.plugins.consent_handler:ConsentHandlerPlugin",
        "config": {
          "policy": "accept_all",
          "timeout_ms": 10000,
          "required": false,
          "generic_fallback": true
        }
      }
    }
  }
}
```

Invocation:

```json
{
  "type": "plugin_call",
  "plugin": "consent-handler",
  "method": "handle",
  "params": {
    "policy": "accept_all",
    "timeout_ms": 10000,
    "required": false,
    "generic_fallback": true
  },
  "action_timeout_ms": 15000
}
```

`policy`: `accept_all` or `reject_optional`.

`required`: when `false` (default), absence of a banner is a successful no-op. When `true`, `consent_not_found` is a controlled plugin failure.

`generic_fallback`: enables multilingual semantic/text matching after provider selectors.

Optional plugin config overrides:
- `accept_texts`: list of generic accept labels;
- `reject_texts`: list of generic reject labels;
- `providers`: object overriding/extending provider selector lists.


## Recording cursor overlay (v0.5.17)

`recording.show_cursor` controls a simple red cursor marker in recorded/debug browser pages.

```json
{
  "recording": {
    "video": true,
    "video_size": "default",
    "show_cursor": true
  }
}
```

- `show_cursor: true` injects a small red circle into the current document.
- The marker uses `pointer-events: none`, so it does not intercept clicks or change page behavior.
- It is hidden until the first scripted mouse movement.
- It is re-created after document navigation and on new/selected tabs.
- It follows scripted mouse targets from `mouse_move`, `mouse_move_random`, `click` with `method: "mouse"`, `mouse_press`, and `hover`.
- Manual mouse movement performed directly through noVNC is not tracked by this overlay.

This is intentionally a minimal debug/video visualization, not a click-animation system.


### Live trajectory behavior (v0.5.18)

`show_cursor` now follows DOM `mousemove` events in real time. During Camoufox native humanized mouse movement, each intermediate browser mouse event updates the red marker, so the `.webm` recording shows the movement trajectory rather than only the final coordinate.

The listener is registered as an init script for future documents/frames and installed immediately in the current document. The final coordinate update from mouse actions remains as a fallback only.

The option name and JSON format are unchanged from v0.5.17.


## Firefox base-image boundary — v0.5.21

Base-image construction is outside the worker runtime repository/release.

The worker Dockerfile accepts:

```text
WORKER_FIREFOX_BASE_IMAGE
```

Default:

```text
worker-firefox-base:152.0.4-beta.28-ubo1
```

A separate `firefox-image-builder` tool owns browser bundle extraction, Linux runtime packages, Python runtime dependencies and Camoufox package-manager registration.

`config.paths.browser_source_commit` still points to the `SOURCE_COMMIT` file embedded **inside the prepared base image** so the worker can record browser provenance in run artifacts.

The worker itself never needs the source ZIP or build-time SOURCE_COMMIT file.
