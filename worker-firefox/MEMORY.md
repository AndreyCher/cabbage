# MEMORY.md — worker-firefox project handoff

This file is the compact machine-oriented handoff for future development sessions. Read it before modifying a release.

## Release Definition of Done
- Bump `VERSION` and `APP_VERSION`.
- Run tests and Python compile checks.
- Synchronize every relevant Markdown document with actual code.
- Update `CHANGELOG.md` and `RELEASE_NOTES.md` for every release.
- Keep `FUTURE.md` human-readable and `FUTURE_BOT.md` detailed enough to resume deferred work.
- Review and update this `MEMORY.md` on every release.
- From v0.5.21, `worker-firefox` does not build browser base images and does not accept root-level `camoufox-custom.zip` / `SOURCE_COMMIT`. Those operator-provided assets belong only to the separate `firefox-image-builder` tool.


## Versioning policy

Use normal semantic project increments for functional/runtime changes, e.g. `0.5.16 -> 0.5.17`.

For documentation/metadata-only updates that do not intentionally change runtime functionality, append an incremental documentation revision suffix to the current functional release:

```text
0.5.16-1
0.5.16-2
0.5.16-3
```

Rules:
- `-N` revisions are documentation/metadata synchronization releases only.
- A runtime/feature/fix change that modifies application behavior must advance the functional version instead of using `-N`.
- The package directory, `VERSION`, `APP_VERSION`, README current-release heading, CHANGELOG and RELEASE_NOTES must all use the exact packaged revision.
- A later functional release drops the documentation suffix and advances normally, e.g. `0.5.16-2 -> 0.5.17`.

## Documentation map
- `README.md`: overview/current release.
- `CONFIG.md`: configuration/action reference (formerly FUNCTIONS.md; do not restore FUNCTIONS.md).
- `SCENARIO.md`: scenario/action usage.
- `API.md`: Control API.
- `PLUGINS.md`: plugin system.
- `CHANGELOG.md`: factual version history.
- `RELEASE_NOTES.md`: current release notes.
- `FUTURE.md`: concise roadmap for people.
- `FUTURE_BOT.md`: detailed deferred technical context.
- `MEMORY.md`: compact durable project handoff/release rules.

## Architecture and compatibility decisions
- Scenario actions are modular modules under `app/actions`; avoid coupling new actions into the engine.
- Third-party browser libraries use plugin adapters, not core coupling.
- Site-created tabs are tracked through BrowserContext page events and `switch_tab` pumps Playwright Sync events while waiting.
- Debug mode may continue after ordinary action failures, but controlled fatal failures still abort when required.
- Runtime external input is API-first via `wait_input`; outbound integrations use the generic `webhook` action.
- Dynamic Fluent UI IDs such as `fluent-option8667` are not stable selectors. Prefer semantic/test attributes and role/value checks.

- Approved future architecture after worker stabilization: add a separate Controller/control plane. External systems use Controller API; Controller owns queue/runs/state and launches one ephemeral worker-firefox per run through an Executor abstraction, initially `DockerExecutor` using Python Docker SDK/Engine API. Workers communicate only on an internal Docker network in orchestrated mode; do not publish a host port per worker. Controller routes `wait_input` data to the assigned worker. Identity/profile and artifacts persist outside disposable workers. Keep future `RemoteDockerExecutor`/`KubernetesExecutor` possible, but do not implement Kubernetes yet. Controller must generate safe allow-listed container specs rather than accept arbitrary Docker options.

## Build/packaging
- Keep heavy browser/runtime/dependency Docker layers stable; frequently changed app/config/version files belong in late layers.
- Custom browser path: `/opt/camoufox-custom/camoufox-bin`.
- `firefox-image-builder` v0.2.0+ creates the browser package and SOURCE_COMMIT automatically from the selected Camoufox source checkout. The resulting base image embeds runtime provenance under `/opt/camoufox-custom/SOURCE_COMMIT`.

## Current integration direction
- v0.5.12 adds outbound webhook/HTTP action with response storage under `{{webhook.<save_as>...}}`.
- v0.5.13 adds generic `mouse_press` for selector/coordinate targets and iframe chains. Long `hold_ms` is intentional runtime and is included in the hard watchdog budget.
- A test-only `webhook-mock` FastAPI container returns registration profiles from a mounted JSON file. Never bake real credentials into source/image.
- Country data via Control API + robust Fluent UI country selection remains an unversioned future task.

- v0.5.14 adds generic `hover`: any selector, physical Camoufox mouse movement, center-relative offset, and optional iframe chain support. Keep it tag-agnostic.

- v0.5.16 implements cookie/CMP consent as built-in `consent-handler` plugin, not a core action. It supports `accept_all`/`reject_optional`, provider-specific + multilingual generic fallback, iframe scanning, optional/no-op behavior, diagnostics, and a local deterministic consent test page. Keep future consent improvements inside the plugin architecture.

- Future configuration principle: operator-tunable behavioral defaults must be centralized in configuration rather than hidden as fallback literals in Python. When implemented, perform a repository-wide audit and document all defaults/precedence in `CONFIG.md`.

- v0.5.17 adds minimal `recording.show_cursor`: a red, pointer-events-none DOM marker for scripted mouse positions in debug/video recordings. Keep it simple; no action labels/click animation unless explicitly requested later.

- v0.5.18 fixes `recording.show_cursor`: live DOM `mousemove` events now drive the red marker so recordings show the actual Camoufox mouse trajectory; direct action-coordinate updates remain fallback only. Keep this visualization minimal.

- Known rare/intermittent issue predating v0.5.18: Camoufox native `page.mouse.move()` can occasionally stall after selector visibility/bounding-box succeeds. Future fix: phase-specific click timeouts/reasons (`locator_timeout`, `bounding_box_timeout`, `mouse_move_timeout`, `mouse_click_timeout`) plus cleanup of interrupted Playwright futures to avoid unhandled `TargetClosedError`; integrate with centralized error normalization/configurable defaults.

- Documentation review v0.5.18-2: FUTURE.md is a strict backlog-only document; remove completed work after implementation. Runtime registry contains 19 scenario actions and SCENARIO.md documents all 19. Plugin framework itself is implemented; only concrete enhancements/new adapters belong in Future.

- v0.5.19 configuration architecture: `config/config.json` is the runtime path map; `config/default.json` is canonical read-only defaults; `config/profiles/*.json` contains launch/profile overrides; `config/scenarios/*.json` stores one reusable scenario per file. Resolver deep-merges default+profile and loads the selected scenario. Worker must never modify default/scenario files. Future Controller/Central Console must reuse this same resolver/domain model and launch ephemeral workers through DockerExecutor rather than introducing a second config format.

- Naming policy from v0.5.20: generic project-owned components are `worker-firefox`, future `worker-android`, and `controller`; project-owned env vars use `WORKER_*`; do not use POC/Camoufox/QA as generic project namespaces. `Camoufox` remains valid only for the actual vendor/browser runtime and vendor-specific settings such as `CAMOUFOX_EXECUTABLE_PATH`. Internal project codename defaults to configurable `project.name="cabbage"` and must never be baked into component/API/Docker naming.

- v0.5.21 build boundary: `firefox-image-builder` is a separate tool that produces versioned immutable `worker-firefox-base:<browser-version>` images. `worker-firefox` contains only the thin app Dockerfile and consumes a prepared base through `WORKER_FIREFOX_BASE_IMAGE`. Keep the builder outside worker runtime releases.
