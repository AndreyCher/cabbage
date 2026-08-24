# Future / Roadmap

> Firefox worker files live in `workers/worker-firefox/`. Application commands are run from the repository root.

This file contains only work that is **not yet implemented** in the current release. Implemented functionality belongs in README/CONFIG/SCENARIO/API/PLUGINS/CHANGELOG and must be removed from this roadmap after release.

## Plugin enhancements

The generic plugin framework, registry/lifecycle, `plugin_call`, controlled plugin failures, `playwright-recaptcha` adapter and `consent-handler` are already implemented.

Remaining ideas:
- add a prepare/before-navigation lifecycle for plugins that must install listeners before navigation;
- add/test `solve_v3` for `playwright-recaptcha` after that lifecycle exists;
- evaluate `playwright-captcha` as another adapter;
- plugin capability/schema metadata for future API/UI discovery;
- dependency manifests / optional Docker build profiles for heavy adapters;
- plugin health/self-test hooks and compatibility metadata;
- standard safe export of selected plugin results into scenario variables;
- consent-handler enhancements: custom category policy, more provider/language signatures, richer post-click verification;
- hCaptcha solver work remains frozen/experimental until a worthwhile backend/upstream path exists.

## Scenario framework enhancements

Current modular actions are documented in `workers/worker-firefox/SCENARIO.md`.

Potential additions when real scenarios require them:
- URL/title/predicate-based tab selection;
- conditions/branching and loops;
- extraction helpers;
- download/upload actions;
- generic HTTP/API actions beyond the existing outbound `webhook`;
- richer variable handling;
- action metadata/schema discovery for a future visual editor.

## UI / orchestration

- Keep the worker API-first.
- The initial `web-console` dashboard is implemented; future increments should use action/plugin metadata to build forms and scenario workflows dynamically.

## Naming / component boundary

Implemented naming baseline:
- current component: `worker-firefox`;
- future Android component: `worker-android`;
- orchestrator: `controller`;
- worker API domain field: `worker_type`;
- internal project codename is configurable and must not become an architectural namespace.

Future components should follow this neutral naming scheme.

## Controller / orchestration enhancements

Controller v0.1 implements the initial local Docker control plane. Remaining work
includes multi-controller coordination, MinIO/S3 artifacts, an external log
archiver, a visual scenario builder, a complete proxy editor and a remote Docker executor.

The implemented boundary remains:

```text
External systems / future UI
            |
            v
      Controller API
            |
      queue / runs / state
            |
          Executor
            |
      DockerExecutor
       /    |    \
      v     v     v
 Camoufox Camoufox Camoufox
 worker   worker   worker
```

Approved direction:
- external systems / the future Central Console integrate with Controller API, not published worker ports;
- reuse the v0.5.19 worker configuration model: canonical `default.json`, named launch profiles, one-file-per-scenario definitions, and a deterministic resolver;
- Controller accepts profile/scenario selection plus validated per-run overrides through API; it must not require clients to edit worker files;
- Controller owns queue, lifecycle, state, worker allocation, cancellation and artifact references;
- Controller owns/uses the configuration source of truth and may materialize a read-only resolved run configuration for each worker; the worker must never modify canonical `default.json` or scenario definitions;
- keep the worker autonomous: it must remain runnable directly from CLI/Compose without Controller, using the same configuration resolver contract;
- initial backend: Python Docker SDK / Docker Engine API through `DockerExecutor`;
- preserve an `Executor` abstraction for future `RemoteDockerExecutor` / `KubernetesExecutor`; do not implement Kubernetes yet;
- one run = one disposable browser worker;
- persistent identity/profile and artifacts live outside workers;
- Controller ↔ workers use an internal Docker network;
- Controller routes mid-run `wait_input` data to the owning worker;
- Controller creates an allow-listed safe container spec; callers cannot submit arbitrary privileged Docker options.
- Controller should select/validate a compatible prepared `worker-firefox-base` image by stable image metadata/labels rather than invoking browser-image builds during a run;

## Unscheduled: country input and Fluent UI selection

Accept stable country data (prefer ISO 3166-1 alpha-2) through the Control API and provide a robust selection mechanism for custom Fluent UI dropdowns. Do not depend on generated `fluent-optionNNNN` IDs.

## Unscheduled: centralized configurable runtime defaults

Move operator-tunable defaults out of Python fallback literals and into validated configuration.

Target precedence:

```text
global defaults
  -> action/plugin defaults
    -> scenario override
      -> action override
```

Audit delays, timeouts, retries, counts/ranges, `mouse_press.hold_ms`, webhook/wait-input behavior, cleanup/watchdog timing and plugin defaults. `workers/worker-firefox/CONFIG.md` becomes authoritative for these values.

## Unscheduled: phase-specific physical click timeouts and watchdog cleanup

The v0.5.25 bounded default fixed `mouse_move_random`; physical click can still
opt into native `page.mouse.move()` and needs finer phase diagnostics.

Split physical click diagnostics into:
1. selector / wait-visible;
2. bounding-box lookup;
3. mouse movement;
4. mouse click.

Use controlled reasons such as `locator_timeout` / `element_not_visible`, `bounding_box_timeout`, `mouse_move_timeout`, and `mouse_click_timeout`, with action/selector/phase/target/timeout context. Keep the overall hard action watchdog as a final safety net.

After watchdog interruption, normalize/drain the pending Playwright operation so shutdown does not emit unhandled `Future exception was never retrieved` / `TargetClosedError`, while keeping cleanup and video/artifact finalization bounded.

## Documentation policy

Every release must synchronize the component README/changelog/reference documents, global `README.md` and `CHANGELOG.md`, `FUTURE.md`, `FUTURE_BOT.md`, and `AGENT.md` as applicable. For `worker-firefox`, this includes the documents under `workers/worker-firefox/`: `README.md`, `CONFIG.md`, `SCENARIO.md`, `API.md`, `PLUGINS.md`, `CHANGELOG.md`, and `RELEASE_NOTES.md`. `FUTURE.md` must contain only unimplemented work; completed roadmap items are moved to implementation/history documentation.
