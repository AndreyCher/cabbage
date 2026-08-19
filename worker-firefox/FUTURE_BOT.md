# Future Bot / Technical Continuation Context

This file preserves detailed technical context for future AI-assisted development. Keep `FUTURE.md` concise for people; keep investigation history, decisions, exact versions, observed results, and resume criteria here. Review and synchronize this file on every release.

## hCaptcha integration — FROZEN / EXPERIMENTAL

### Decision

Development of the `hcaptcha-challenger` solving path is frozen as of Firefox worker v0.5.9. The adapter code is retained for future research, but the plugin is disabled by default and bundled hCaptcha solving scenarios are not part of the active v0.5.19 scenario catalog; the old monolithic `test.json` / `test-debug.json` configuration format was removed from the active config tree. Do not resume this direction merely by reconstructing deprecated upstream internals.

### Tested runtime and evidence

- Upstream package tested: `hcaptcha-challenger 0.19.0` / 0.19.x runtime.
- Real test target: ZennoLab hCaptcha lessons, including Easy challenge.
- Plugin loading/lifecycle works through the generic Camoufox plugin framework.
- `capabilities` worked without Gemini and exposed diagnostic capability information.
- `local_probe` worked without Gemini and inspected the installed package/current page.
- Probe observed package modules/resources but did not establish a supported local end-to-end solver.
- `checkbox_test` successfully detected the hCaptcha checkbox iframe and clicked `I am human` on the live page.
- Confirmed live result: `clicked=True`, `challenge_opened=True`, `response_present=False`.
- `local_solve_test` intentionally never invoked AgentV/Gemini and attempted to discover a stable configuration-only local solver path.
- Confirmed live result: `models=0` and controlled failure `reason=hcaptcha_local_solver_unavailable`.
- Exact conclusion from live v0.5.8 test: no stable non-Gemini end-to-end local solver was available in the installed `hcaptcha-challenger` runtime.
- Earlier high-level `solve` testing reached upstream AgentV configuration and failed because `GEMINI_API_KEY` was required. This proved the bridge/plugin invocation path worked, but also showed Gemini was a mandatory dependency for that upstream high-level flow.

### What is already technically useful

Keep the existing adapter implementation and tests as research scaffolding. It already proves that Camoufox can locate/interact with hCaptcha frames and can host a third-party adapter without coupling it to ActionEngine. Diagnostic methods (`capabilities`, `local_probe`, `checkbox_test`, `local_solve_test`) may be useful when the upstream package changes, even though they are no longer bundled as user sample scenarios.

### Why development was frozen

The project does not want Gemini to become a mandatory paid/external dependency. The tested upstream 0.19.x high-level solver is AgentV/Gemini-oriented, while the live investigation did not discover a maintained stable local end-to-end solver and found no usable packaged local models for the tested path (`models=0`). Continuing to reverse-engineer old/internal local flows would create fragile project-specific code with poor maintenance value.

### Resume procedure

When revisiting hCaptcha, start by checking the current upstream `hcaptcha-challenger` release and documentation. Do not assume 0.19.x behavior is still current. Determine whether upstream now provides: (1) a stable non-Gemini solver, (2) bundled/local vision models, (3) configurable AI/vision providers, or (4) a public API suitable for external vision backends. If upstream has a maintained local solver, test it first through the existing plugin abstraction before writing custom solver code.

If an AI/vision backend is still required, implement a generic pluggable `VisionBackend` abstraction rather than coupling the hCaptcha adapter to Gemini. Desired providers may include `GeminiBackend`, `OpenAIBackend`, `OllamaBackend`, `LocalVisionBackend`, and a generic `ExternalApiBackend`. Provider selection/configuration must live in JSON/plugin configuration and credentials must remain external secrets.

Preferred responsibility split: hCaptcha adapter handles challenge/iframe detection, image/task extraction, browser interaction, answer application, and completion verification; `VisionBackend` handles model/provider-specific inference only. Prefer a separate local/remote vision service over installing large ML stacks in the main Camoufox runtime image.

### Resume criteria

Resume active hCaptcha solver development only when at least one condition is true: upstream gains a stable local/non-Gemini flow; a suitable local vision backend is selected; a generic VisionBackend interface is implemented; or an acceptable external multimodal provider is intentionally selected. After resuming, validate Easy/Moderate/Difficult and other relevant hCaptcha variants before calling the adapter supported.

## v0.5.10 tab-tracking architecture

`ScenarioContext` now owns automatic page synchronization. It subscribes to `browser_context.on("page", ...)` when supported and also merges `browser_context.pages` before page operations. This specifically fixes site-created tabs/popups (`target="_blank"`, `window.open()`) that were absent from the old local `ctx.pages` registry. `switch_tab` accepts an index or first/oldest/last/newest target and index switching waits up to `timeout_ms`. Do not reintroduce a separate unsynchronized tab list in future actions.

Expected Playwright locator timeouts have a controlled `playwright_timeout` path with concise log messages; unexpected implementation exceptions still use traceback logging. `FUNCTIONS.md` was renamed to canonical `CONFIG.md` in this release.



## v0.5.11 Playwright Sync API tab-wait lesson

A real Outlook test exposed an important Sync API behavior: a browser tab can already be visible in noVNC while Python has not yet received the `BrowserContext.on("page")` callback. Do not poll pending Playwright state using only `time.sleep()` in the synchronous execution thread. `ScenarioContext.switch_page()` now calls `page.wait_for_timeout()` during the wait so Playwright can dispatch events, then re-synchronizes `browser_context.pages`. Preserve this behavior in future refactors. The observed failure signature was `switch_tab ... known_tabs=1`, followed immediately during browser close by `TAB detected index=1`.


## Deferred / no target release — country data + Fluent UI dropdown
Implement API-supplied country information, preferably ISO alpha-2 plus optional localized display name. A future custom dropdown action should open the Fluent UI combobox, navigate/select the intended option without generated IDs, and verify the combobox `value` after selection. This is intentionally not assigned to a release.


## Deferred / no target release — centralized Playwright frame/locator errors

Real v0.5.13 case: `mouse_press` used `frame_selector: "iframe"` on a Microsoft/Outlook page and Playwright raised:

`Locator.wait_for: Error: strict mode violation: locator("iframe") resolved to 2 elements`

The two matches were:
- `iframe[data-testid="deviceFingerPrinting"]`
- `iframe[data-testid="humanIframe"]`

At that point `ActionEngine` normalized `PlaywrightTimeoutError`, but generic `playwright.sync_api.Error` fell into the broad `Exception` path and emitted a full traceback.

Future centralized normalization should apply to all selector/frame-based actions (`click`, `type`, `select`, `mouse_press`, `hover`, etc.) rather than being implemented per action. At minimum classify:
- `strict_mode_violation`
- `frame_not_found` / detached frame
- `page_closed` / context closed
- `invalid_selector`

For strict-mode errors, include action index/type, selector or frame selector, match count when available, and short matched-element summaries, then recommend narrowing the selector. Example normal log:

`ERROR MPRESS 029 failed: frame selector 'iframe' matched 2 frames; use a more specific frame_selector`

Keep full traceback only in trace/debug diagnostics.


## Approved future architecture — Controller / control plane

This is an approved post-worker-stabilization direction and must survive future release handoffs.

### Boundary

Today a worker-firefox container is both browser worker and owner of its per-run Control API. The future system adds a separate long-running Controller. External systems and a future web UI talk only to the Controller. Individual workers become internal disposable execution units.

### Responsibilities

Controller:
- expose the external run/profile/input/status API;
- validate and normalize incoming run/profile/scenario configuration;
- own queue, run records, state transitions, worker assignment, cancellation and cleanup;
- create worker containers dynamically with Python Docker SDK / Docker Engine API;
- route mid-run input to the correct worker;
- collect/reference artifacts and persist run metadata;
- enforce concurrency/resource limits and safe container templates.

Worker:
- execute exactly one run;
- retain the modular action/plugin engine, browser/fingerprint/recording diagnostics and internal runtime input mechanism;
- report run state and accept routed inputs;
- terminate/dispose after the run.

### Execution abstraction

Do not hard-wire Controller business logic directly to Docker calls. Define an Executor contract such as create/start/inspect/stop/remove (exact interface to be designed when implemented).

First implementation:
`DockerExecutor -> local Docker Engine via Python Docker SDK`

Possible later implementations:
- `RemoteDockerExecutor`
- `KubernetesExecutor`

Kubernetes is explicitly deferred. Do not introduce Kubernetes complexity while the worker/controller contract is still evolving.

### Lifecycle

Target lifecycle:

`POST run -> validate -> queue -> allocate executor -> create ephemeral worker -> start -> observe -> route inputs -> finalize artifacts/state -> stop/remove worker`

One run = one disposable browser worker container. Do not rely on worker-local filesystem for durable Identity/profile or artifacts.

### Networking

Controller and workers share an internal Docker network. In the orchestrated design, worker API port 8090 must not require a unique host-published port per worker. The Controller locates the worker by run assignment/container identity and communicates internally. Only the Controller API is intended as the normal external integration surface.

### Configuration contract

External clients should submit a Controller-owned run/profile/scenario request model instead of editing worker configuration files. The Controller converts validated fields into the worker configuration/runtime inputs. Never expose raw Docker container-create parameters as the public API. Use allow-listed resource/network/mount/image policies and Controller-generated container specs.

### Persistence

Persistent Identity/profile data must be outside ephemeral workers and mounted/injected per run. Artifacts likewise need durable external storage/reference handling. Exact storage backend remains open; preserve a storage abstraction rather than coupling future Controller API semantics to one host path.

### Mid-run input

The existing worker `wait_input` mechanism is useful as the internal protocol. External caller sends input to Controller using run identity; Controller resolves the assigned worker and forwards the input internally. External callers should not need worker IP/port/container ID.

### Compatibility goal

Adding the Controller must not require rewriting the browser action engine or plugin framework. The worker remains independently testable. Controller API becomes the stable external boundary; Executor implementations and worker placement may change behind it.


## Consent handler implementation state — v0.5.16

The previously deferred consent/cookie-banner feature is now implemented as `app.plugins.consent_handler:ConsentHandlerPlugin`.

Current contract:
- methods: `handle`, `detect`;
- policies: `accept_all`, `reject_optional`;
- provider-first selectors: OneTrust, Cookiebot, Didomi, CookieYes, iubenda, Quantcast, TrustArc;
- generic multilingual fallback: EN/UK/DE/FR/ES/IT/PL built-in labels;
- scans main page plus Playwright-attached frames;
- `required=false` means absence is a successful no-op;
- diagnostic artifact: `consent-handler.json` / `consent-detect.json`;
- deterministic local service: `consent-test-page`;
- bundled scenario: `consent-test`.

Do not move consent matching into `ActionEngine`; keep it plugin-based. Future work, with no target release: `custom` category policy, provider/language expansion, stronger post-click verification, and reuse of future centralized locator/frame diagnostics.


## Deferred / no target release — eliminate hardcoded behavioral defaults

Project rule for future refactor: user/operator-tunable runtime defaults must not be embedded as Python fallback literals.

Observed/current style that should eventually disappear:

```python
action.get("delay_ms", 70)
action.get("timeout_ms", 15000)
action.get("count", 3)
```

The exact current values are less important than the architectural rule: defaults must live in a centralized configuration source rather than being distributed through implementation code.

Required implementation plan:

1. Audit the entire repository for behavioral fallback literals, especially:
   - `dict.get(key, literal)`;
   - default function arguments;
   - module/class constants used for timeouts, retries, delays, counts, ranges or policies;
   - hardcoded plugin defaults;
   - watchdog/cleanup/control-API timing values.
2. Classify each value:
   - structural/algorithmic constant: may remain in code;
   - operator/user-tunable behavior: move to configuration.
3. Introduce a central defaults model/block with explicit sections such as:
   - `defaults.actions.type`
   - `defaults.actions.click`
   - `defaults.actions.hover`
   - `defaults.actions.mouse_press`
   - `defaults.actions.wait_input`
   - `defaults.integrations.webhook`
   - `defaults.runtime.watchdog`
   - `defaults.runtime.cleanup`
   - plugin-specific defaults as appropriate.
4. Resolve values in this precedence order:
   `global defaults -> action/plugin defaults -> scenario override -> individual action override`.
5. Add schema/validation and controlled validation errors.
6. Update `CONFIG.md` with every default and precedence rule.
7. Add regression tests proving that changing config changes behavior without Python edits.
8. Preserve backward compatibility where practical during migration.

Example desired direction:

```json
{
  "defaults": {
    "actions": {
      "type": {
        "delay_ms": 75,
        "timeout_ms": 15000,
        "clear": true
      },
      "mouse_press": {
        "hold_ms": 1000,
        "timeout_ms": 15000,
        "button": "left"
      }
    },
    "runtime": {
      "watchdog": {
        "grace_ms": 2000
      }
    }
  }
}
```

Do not implement piecemeal by moving only `delay_ms`; perform a repository-wide behavioral-default audit when this task is started.


## Recording cursor implementation state — v0.5.17

Implemented minimal `recording.show_cursor`. It is a DOM overlay marker, not OS cursor capture. It is intentionally limited to a small red circle following scripted mouse target coordinates and must remain `pointer-events:none`. Current updates come from `mouse_move`, `mouse_move_random`, physical `click`, `mouse_press`, and `hover`. Navigation re-creates the marker. Manual noVNC pointer movements are not tracked. Do not expand into action labels/click animations unless explicitly requested.


## Recording cursor implementation state — v0.5.18

v0.5.17 endpoint-only visualization was insufficient because the marker mostly appeared at the final target. v0.5.18 changes the primary source to live DOM `mousemove` events. `ScenarioContext` registers the listener through `BrowserContext.add_init_script`, initializes existing documents, and keeps the explicit `move_debug_cursor(x,y)` path only as fallback. The feature remains intentionally minimal: red circle, no click animation/action labels.


## Deferred / no target release — intermittent native mouse move stall

Observed production-style log pattern across releases, predating v0.5.18:

```text
CLICK ... wait_visible
CLICK ... visible
CLICK ... bounding_box
CLICK ... mouse_move x=... y=... native_humanize
... no mouse_click log ...
FAIL ... reason=action_timeout
...
Future exception was never retrieved
TargetClosedError: Target page, context or browser has been closed
```

Interpretation:
- selector resolution succeeded;
- element visibility succeeded;
- bounding box succeeded;
- stall occurred inside or below `page.mouse.move(...)` / native Camoufox humanize;
- engine `SIGALRM` watchdog interrupts the synchronous wrapper;
- underlying Playwright async future may remain pending;
- later context shutdown closes the transport and that future surfaces as unhandled `TargetClosedError`.

Do not classify this as a v0.5.18 cursor-overlay regression by default; user reports the same rare issue on earlier versions.

Future implementation direction:
1. Introduce a small internal phase tracker for `click`:
   - `wait_visible`
   - `bounding_box`
   - `mouse_move`
   - `mouse_click`
2. Allow phase-specific controlled exceptions/reasons:
   - `locator_timeout` or `element_not_visible`
   - `bounding_box_timeout`
   - `mouse_move_timeout`
   - `mouse_click_timeout`
3. Log enough context for diagnostics:
   - action index/type
   - selector
   - phase
   - target x/y where known
   - phase timeout / overall timeout
4. Retain the engine hard watchdog as a final circuit breaker.
5. Investigate safe normalization of interrupted Playwright futures so cleanup does not emit:
   - `Future exception was never retrieved`
   - trailing `TargetClosedError`
6. Keep bounded cleanup and video/artifact finalization even after a phase timeout.
7. Integrate this with the centralized Playwright error-normalization task instead of duplicating per-action exception parsing.
8. When centralized defaults are implemented, phase timeout values must come from configuration rather than hardcoded literals.


## Worker configuration architecture implemented in v0.5.19

The worker now has an orchestration-friendly configuration boundary:

```text
config/config.json       -> filesystem path map
config/default.json      -> canonical read-only worker defaults
config/profiles/*.json   -> named launch/profile overrides
config/scenarios/*.json  -> one scenario per file
             |
             v
        Config Resolver
             |
             v
     resolved worker cfg
             |
             v
       worker-firefox
```

Important continuation rules:
- Python application-storage paths are injected from `config.json`; only structural Linux diagnostic paths under `/proc` and `/sys` remain code constants.
- `default.json` and scenario files are read-only worker inputs.
- launch profiles must not embed scenario definitions; they reference `run.scenario`.
- the resolver deep-merges `default -> profile`, validates identity/scenario, then loads exactly one scenario file.
- the worker keeps the existing internal `cfg["scenarios"][selected]` runtime contract so ActionEngine/plugins did not need orchestration awareness.
- `WORKER_SYSTEM_CONFIG` selects the bootstrap path map; `WORKER_PROFILE` selects a named launch profile.
- direct CLI/Compose execution remains supported without a Controller.

Future Controller must reuse this model rather than inventing a second worker configuration system. Recommended orchestration flow:

```text
Central Console
      |
      | Controller REST API
      v
Controller
      |
      | resolve profile + scenario + run overrides
      | create safe container spec
      v
DockerExecutor (Python Docker SDK)
      |
      v
ephemeral worker-firefox
```

Controller may either mount/provide the canonical read-only config repository plus a selected profile, or materialize a per-run resolved configuration through a dedicated worker contract when that feature is designed. In either case, canonical `default.json` and scenario files are never writable by workers.

The future public Controller API should expose stable domain fields (`profile`, `scenario`, run overrides, inputs) rather than filesystem paths or raw Docker parameters.


## Neutral naming baseline — v0.5.20

Use these names in future design/code/docs:
- `controller`
- `worker-firefox`
- `worker-android`
- `worker_type = firefox|android|...`
- project-owned environment variables: `WORKER_*`

Do not reintroduce `POC`, `Camoufox`, or `QA` as generic project/component prefixes. `Camoufox` remains appropriate only when referring to the real underlying runtime/library, browser executable, source commit, or vendor-specific configuration.

The current internal project codename is `cabbage`, stored as `project.name` in the system config. Treat it strictly as configurable metadata; never build Docker names, API paths/contracts, Python package names, or environment variable prefixes from it.


## Firefox base-image tool boundary — v0.5.21

Base image building was removed from `worker-firefox`. A separate `firefox-image-builder` tool produces immutable images such as `worker-firefox-base:152.0.4-beta.28`.

Rules for future work:
- never re-add `Dockerfile.base` to worker runtime releases;
- browser package and SOURCE_COMMIT are generated by firefox-image-builder from the selected source checkout;
- worker Dockerfile accepts `WORKER_FIREFOX_BASE_IMAGE`;
- builder image labels expose worker type, browser runtime/version/build, and source commit;
- future Controller may inspect/select compatible prepared images through Docker API, but should not build browser base images in the run execution path;
- base-image inventory/registry management can be designed later independently from worker execution.
