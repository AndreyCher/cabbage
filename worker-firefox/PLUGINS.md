# Plugins

Firefox worker v0.5.2 supports isolated third-party adapters through the plugin framework introduced in v0.5.1.

## Architecture

The scenario engine does not import third-party automation libraries directly.

```text
Scenario -> plugin_call -> PluginManager -> BasePlugin adapter -> third-party library
```

Each configured plugin has a stable name, an `adapter` in `module:Class` form, an explicit `enabled` flag, and an isolated `config` object.

Adapters are loaded lazily: a disabled adapter is not imported, and an enabled adapter is imported only when it is first used by `plugin_call`.

## Plugin configuration

```json
{
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
}
```

The adapter syntax is always:

```text
python.module:ClassName
```

## Calling a plugin from a scenario

The action contract is:

```json
{
  "type": "plugin_call",
  "plugin": "echo",
  "method": "echo",
  "params": {
    "message": "hello"
  }
}
```

The action uses `method`, not `operation`.

`params` must be a JSON object. A normal action-level `action_timeout_ms` may be supplied for long-running plugin operations.

## Adapter lifecycle

Every adapter inherits `BasePlugin` and implements `invoke()`:

```python
class MyPlugin(BasePlugin):
    def setup(self, ctx):
        pass

    def invoke(self, method, ctx, params):
        return {"success": True}

    def teardown(self, ctx):
        pass
```

`setup(ctx)` runs once before the first call in a run. `teardown(ctx)` is best-effort and runs during scenario finalization. The same adapter instance is reused for subsequent calls in the same run.

## ScenarioContext available to plugins

The adapter receives the same `ScenarioContext` used by built-in actions. Common access points are:

- `ctx.ensure_page()` - current Playwright page, creating/reusing one if necessary.
- `ctx.page` / `ctx.pages` - current and known tabs.
- `ctx.browser_context` - current Playwright browser context.
- `ctx.artifact_dir` - run artifact directory.
- `ctx.logger` - run logger.
- `ctx.runtime` - runtime/control API state when enabled.

Plugins should avoid modifying core engine state unless that is part of their explicit operation.

## Controlled plugin errors

Expected adapter/configuration failures use `PluginError` with a stable `reason`. v0.5.2 logs these as structured scenario failures without Python traceback noise.

Typical reasons include:

- `plugin_not_configured`
- `plugin_disabled`
- `plugin_import_failed`
- `plugin_dependency_missing`
- `plugin_invalid_config`
- `plugin_method_not_supported`
- `plugin_setup_failed`
- `plugin_invoke_failed`

Example:

```text
FAIL   002 plugin_call reason=plugin_disabled plugin=missing method=run message=Plugin is disabled: missing
Scenario stopped: Plugin is disabled: missing (reason=plugin_disabled)
Result: FAIL
```

Unexpected internal exceptions still retain traceback logging.

# playwright-recaptcha adapter

v0.5.2 includes the first real third-party adapter:

```text
app.plugins.playwright_recaptcha:PlaywrightRecaptchaPlugin
```

The packaged dependency is `playwright-recaptcha==0.5.1`.

## Supported method: solve_v2

`solve_v2` works with the current Playwright page and invokes `playwright_recaptcha.recaptchav2.SyncSolver`.

Plugin configuration:

```json
{
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
}
```

Audio mode is the default:

```json
{
  "type": "plugin_call",
  "plugin": "playwright-recaptcha",
  "method": "solve_v2",
  "params": {
    "wait": true,
    "image_challenge": false
  },
  "action_timeout_ms": 120000
}
```

A successful call returns a JSON-serializable result containing `success`, `captcha_type`, `solver`, `mode`, `wait`, `token`, `token_length`, and `elapsed_ms`.

### Image challenge mode

The upstream library can use CapSolver for image classification. Set `image_challenge=true` and supply the key preferably through the environment:

```bash
CAPSOLVER_API_KEY=...
```

The adapter also accepts `plugins.items.<name>.config.capsolver_api_key`, but environment injection is preferred so secrets do not live in scenario configuration.

### System/runtime dependencies

reCAPTCHA v2 audio solving requires `ffmpeg` and `ffprobe`. These dependencies are provided by the prepared `worker-firefox-base` image.

The third-party package is installed with `--no-deps` so that it cannot silently replace the Playwright version already selected by Camoufox. Its non-Playwright runtime dependencies are pinned separately in `requirements.txt`.

## ZennoLab live test

The sample configs contain a disabled `playwright-recaptcha` entry and a `captcha-test-v2` scenario using:

```text
https://lessons.zennolab.com/captchas/recaptcha/v2_simple.php?level=low
```

To run it:

1. Rebuild the base image because v0.5.2 adds system/Python plugin dependencies:

```bash
Build the required `worker-firefox-base` image with the separate `firefox-image-builder` tool.
```

2. Build the normal application image:

```bash
docker compose build worker-firefox
```

3. Set `plugins.items.playwright-recaptcha.enabled` to `true`.
4. Set `run.scenario` to `captcha-test-v2`.
5. Run the normal Camoufox service:

```bash
docker compose up worker-firefox
```

Expected action sequence:

```text
open -> wait -> plugin_call solve_v2 -> screenshot -> Result: PASS
```

The plugin step intentionally uses a 120 second hard action timeout because an interactive CAPTCHA solve can exceed the normal 30 second action watchdog.

## Why v3 is not exposed yet

The upstream reCAPTCHA v3 solver should be initialized before navigation so its network listener is active before the reCAPTCHA reload request occurs. The current `plugin_call` lifecycle is action-oriented and runs after navigation in a normal scenario. Rather than hide that requirement behind a fragile implementation, v3 support is tracked for a future prepare-before-navigation plugin lifecycle.

## Adding another plugin

Create an adapter module under `app/plugins/`, inherit `BasePlugin`, keep third-party imports inside the adapter/lazy path, return JSON-serializable data, and raise `PluginError` for expected failures. Then configure it using the same `adapter: "module:Class"` contract. No `ActionEngine` changes should be required.

## hcaptcha-challenger adapter (v0.5.3, experimental)

### Current live-test limitation

Live validation reached the upstream `AgentV` configuration stage successfully, confirming that the plugin loads and the scenario reaches the adapter. The current upstream `AgentV` path requires `GEMINI_API_KEY`; without it, the adapter returns a controlled `hcaptcha_solve_failed` error before challenge solving begins. Because Gemini is not intended to become a mandatory paid dependency of the POC, researching a lower-level/local/pluggable vision path is tracked in `FUTURE.md`.


Adapter:

```text
app.plugins.hcaptcha_challenger:HCaptchaChallengerPlugin
```

Configuration:

```json
"hcaptcha-challenger": {
  "enabled": false,
  "adapter": "app.plugins.hcaptcha_challenger:HCaptchaChallengerPlugin",
  "config": {
    "click_checkbox": true,
    "disable_bezier_trajectory": true,
    "debug": false
  }
}
```

Scenario call:

```json
{
  "type": "plugin_call",
  "plugin": "hcaptcha-challenger",
  "method": "solve",
  "params": {
    "click_checkbox": true
  },
  "action_timeout_ms": 180000
}
```

The upstream library uses an asynchronous Playwright API while the current Firefox worker runner uses the synchronous Playwright API. v0.5.3 therefore contains an experimental bridge that wraps the *same underlying Page* with Playwright's async wrapper and executes the coroutine via the sync page dispatcher. No second browser/context is intentionally created.

Expected controlled failure reasons include `plugin_dependency_missing`, `hcaptcha_api_incompatible`, `hcaptcha_async_bridge_unavailable`, `hcaptcha_async_bridge_failed`, and `hcaptcha_solve_failed`.

The adapter is disabled by default until it completes live validation. If it proves incompatible or too heavy, it can be removed without changing the action engine or scenario format.

### hCaptcha backend selection (v0.5.5)

The v0.5.5 investigation found that upstream 0.19 still documents `AgentV` with a required Gemini API key. Upstream also advertises pluggable local ResNet/YOLO/ViT ONNX resources for specific challenge types, but not a documented universal high-level local `AgentV` replacement.

The adapter now separates the backend from the plugin contract:

```json
{
  "enabled": true,
  "adapter": "app.plugins.hcaptcha_challenger:HCaptchaChallengerPlugin",
  "config": {
    "backend": "agentv"
  }
}
```

For a local/custom backend:

```json
{
  "config": {
    "backend": "custom",
    "backend_adapter": "my_plugins.local_hcaptcha:LocalHCaptchaBackend",
    "backend_config": {}
  }
}
```

The custom class contract is `Class(config).solve(page, params)`. It receives the existing Camoufox/Playwright page; it must not create a second browser unless that is an explicit backend design choice. Both synchronous results and awaitable results are supported through the current sync runner bridge.

`plugin_call` with `method: "capabilities"` reports the supported backend modes without constructing `AgentV`, so it does not require a Gemini API key.



### hCaptcha checkbox interaction test (v0.5.7)

`checkbox_test` is a user-facing interaction probe that does not invoke AgentV or Gemini. It operates on the current Camoufox page through Playwright frame APIs.

```json
{
  "type": "plugin_call",
  "plugin": "hcaptcha-challenger",
  "method": "checkbox_test",
  "params": {
    "timeout_ms": 15000,
    "post_click_wait_ms": 1500
  },
  "action_timeout_ms": 30000
}
```

The result includes `checkbox_found`, `checkbox_clicked`, `challenge_opened`, `response_present`, and selector/frame diagnostics. A successful checkbox click only proves widget interaction; it is not a local visual-challenge solver.

### hCaptcha local runtime probe (v0.5.6)

Use `local_probe` before implementing or enabling a built-in local solver:

```json
{
  "type": "plugin_call",
  "plugin": "hcaptcha-challenger",
  "method": "local_probe",
  "params": {},
  "action_timeout_ms": 30000
}
```

The method does not require Gemini. It inspects the installed `hcaptcha-challenger` package and current page, logs a concise summary, and saves `hcaptcha-local-probe.json` in the run artifacts. Important fields include `package_version`, `candidate_modules`, `local_resource_files`, `hcaptcha_frame_urls`, `response_textarea_count`, and `gemini_api_key_present`. The probe is diagnostic only; `local_solver_ready` remains false until a real built-in local backend is implemented and live-tested.

### Non-Gemini local solve decision test (v0.5.8)

`local_solve_test` is intentionally the final feasibility test before investing further in a built-in local hCaptcha solver. It uses the existing Camoufox page, opens the challenge, and inspects the installed upstream 0.19.x runtime for stable non-Gemini solver entry points and packaged model files. It does not instantiate `AgentV` and does not use `GEMINI_API_KEY`.

```json
{
  "type": "plugin_call",
  "plugin": "hcaptcha-challenger",
  "method": "local_solve_test",
  "params": {"timeout_ms": 15000, "post_click_wait_ms": 1800},
  "action_timeout_ms": 30000,
  "continue_on_error": true
}
```

The method writes `hcaptcha-local-solve-test.json`. If the runtime has no stable configuration-only local path, it returns `hcaptcha_local_solver_unavailable`. After live validation, the project decision is either to continue with a proven local path or freeze that direction and defer a future pluggable AI-provider backend.



## v0.5.9 hCaptcha freeze decision

The `hcaptcha-challenger` adapter is retained but frozen/experimental and disabled by default. v0.5.8 live validation confirmed checkbox control but no stable non-Gemini local end-to-end solver (`models=0`, `hcaptcha_local_solver_unavailable`). Bundled hCaptcha scenarios were removed in v0.5.9. Do not treat the adapter as a supported solver. See `FUTURE_BOT.md` before resuming this work.


## v0.5.10 core compatibility note

No plugin contract changed in v0.5.10. The shared `ScenarioContext` now keeps site-opened browser tabs synchronized, so plugins reading `ctx.page` receive the page selected by the enhanced `switch_tab` action.


## v0.5.11 core compatibility note

No plugin contract changed. Plugins receive the same `ScenarioContext`; the selected `ctx.page` is now updated reliably after waiting for a site-created tab.


## consent-handler adapter (v0.5.16)

Adapter:

```text
app.plugins.consent_handler:ConsentHandlerPlugin
```

This is a built-in plugin with no third-party Python dependency. It handles ordinary cookie/CMP consent UI while remaining isolated from the core action engine.

Sample configuration:

```json
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
```

### `handle`

```json
{
  "type": "plugin_call",
  "plugin": "consent-handler",
  "method": "handle",
  "params": {
    "policy": "accept_all",
    "timeout_ms": 10000,
    "required": false
  },
  "action_timeout_ms": 15000
}
```

Policies:
- `accept_all`
- `reject_optional`

`required=false` is the normal browsing mode: if no matching consent banner exists, the plugin returns `handled=false` and the scenario continues. Use `required=true` when the banner is expected and absence should fail the action.

Resolution order:
1. provider-specific stable selectors;
2. multilingual generic button-name/text fallback when `generic_fallback=true`.

Built-in provider selector groups currently cover OneTrust, Cookiebot, Didomi, CookieYes, iubenda, Quantcast, and TrustArc. Provider selectors can be extended/overridden through plugin `config.providers`.

The generic fallback includes common English, Ukrainian, German, French, Spanish, Italian, and Polish consent labels. Additional `accept_texts` / `reject_texts` arrays may be provided in plugin config or per-call params.

The handler scans the main page and attached Playwright frames, including cross-origin frames exposed through Playwright's frame tree.

Successful or no-op runs write `consent-handler.json` into the run artifact directory.

### `detect`

`detect` checks known provider selectors without clicking:

```json
{
  "type": "plugin_call",
  "plugin": "consent-handler",
  "method": "detect",
  "params": {}
}
```

It returns `detected` plus matching provider/scope/selector records and writes `consent-detect.json`.

### Local test page

v0.5.16 includes a deterministic `consent-test-page` service. Start it with:

```bash
docker compose --profile consent-test up -d consent-test-page
```

Then run the bundled `consent-test` scenario. The local page intentionally exposes CookieYes-style selectors so the provider-specific path can be validated consistently.


## Plugin inventory audit — v0.5.18-2

The generic plugin framework is implemented and is **not** a roadmap item. Current adapters/modules are:

- `playwright-recaptcha` — documented above; `solve_v2` is the exposed supported method.
- `consent-handler` — documented above; `handle` and `detect`.
- `hcaptcha-challenger` — experimental/frozen; retained as implementation/diagnostic history, disabled for normal use.
- `echo` — internal minimal development/test plugin used to exercise the generic plugin mechanism; it is not intended as an end-user integration.

Future plugin work is limited to concrete enhancements/new adapters listed in `FUTURE.md`; the plugin layer itself already exists.
