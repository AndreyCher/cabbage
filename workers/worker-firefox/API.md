# Control API

> Component files live in `workers/worker-firefox/`. Run Docker Compose commands from the repository root; file paths in this document are relative to the component directory unless stated otherwise.

Firefox worker v0.4.16 introduced a versioned HTTP Control API for exchanging runtime data with an active scenario.

The API is intentionally addressed by **Identity first**, then by the concrete run:

```text
/api/v1/identities/{identity}/runs/{run_id}/...
```

A run ID is generated automatically in the form:

```text
20260812T101500Z-a8f3
```

The timestamp is UTC and the four hexadecimal characters prevent collisions between runs started in the same second.

## Configuration

```json
"api": {
  "enabled": true,
  "host": "0.0.0.0",
  "port": 8090
}
```

`enabled` starts/stops the Control API. `host` is the bind address inside the container. `port` is the HTTP listen port. The root `compose.yml` publishes port `8090` for both normal and debug services.

> v0.4.16 does not implement API authentication. Do not expose port 8090 directly to an untrusted network. Restrict it using Docker/network/firewall rules or place an authenticated reverse proxy in front of it.

## Health

```http
GET /api/v1/health
```

Response:

```json
{
  "status": "ok",
  "api_version": "v1",
  "project": "cabbage",
  "component": "worker-firefox",
  "worker_type": "firefox"
}
```



`project` comes from configurable `project.name`; `component` and `worker_type` describe the technical worker component and do not depend on the project codename.

## Current run

```http
GET /api/v1/identities/{identity}/runs/current
```

Example:

```bash
curl http://localhost:8090/api/v1/identities/test-user-001/runs/current
```

Typical response while a scenario waits for input:

```json
{
  "identity": "test-user-001",
  "run_id": "20260812T101500Z-a8f3",
  "scenario": "login",
  "status": "waiting_input",
  "current_action": 6,
  "waiting_input": {
    "key": "credentials",
    "timeout_sec": 600.0,
    "remaining_sec": 487
  },
  "expected_inputs": ["credentials"],
  "received_inputs": [],
  "started_at": "2026-08-12T10:15:00+00:00",
  "finished_at": null
}
```

Possible run states are `starting`, `running`, `waiting_input`, `completed`, and `failed`.

## Get a concrete run

```http
GET /api/v1/identities/{identity}/runs/{run_id}
```

Example:

```bash
curl http://localhost:8090/api/v1/identities/test-user-001/runs/20260812T101500Z-a8f3
```

## List runs known by the process

```http
GET /api/v1/identities/{identity}/runs
```

In v0.4.16 one container process owns one active run, so this endpoint returns the run currently known by that process. The URL is reserved now so the API can later support a multi-run orchestrator without changing the resource hierarchy.

## Submit runtime input

```http
POST /api/v1/identities/{identity}/runs/{run_id}/inputs/{key}
Content-Type: application/json
```

Example:

```bash
curl -X POST \
  http://localhost:8090/api/v1/identities/test-user-001/runs/20260812T101500Z-a8f3/inputs/credentials \
  -H 'Content-Type: application/json' \
  -d '{
    "username": "user@example.com",
    "password": "secret"
  }'
```

Successful response uses HTTP `202 Accepted`:

```json
{
  "status": "accepted",
  "identity": "test-user-001",
  "run_id": "20260812T101500Z-a8f3",
  "key": "credentials"
}
```

Input may be submitted before the scenario reaches the matching `wait_input`; when the action is reached it completes immediately.

Only keys declared by `wait_input` actions in the selected scenario are accepted. This prevents accidental delivery to an unrelated input name.

## Error responses

`400 Bad Request` is returned for an empty body, invalid Content-Length, or malformed JSON.

`404 Not Found` is returned for an unknown API path, incorrect identity/run path, or an input key not declared by the scenario.

Example unknown key:

```json
{
  "error": "unknown_input_key",
  "key": "otp2"
}
```

`409 Conflict` is returned when the run has already finished or a value for the same key has already been accepted.

```json
{
  "error": "input_already_exists",
  "key": "credentials"
}
```

## Runtime data and secrets

The payload itself is kept only in the in-memory `RuntimeContext` for use by the current process. `runtime-events.json` records event metadata such as `input_received`, key name, and timestamp, but intentionally does **not** store input values.

The action logger logs the original scenario action before template resolution. Therefore an action such as:

```json
{
  "type": "type",
  "selector": "#password",
  "text": "{{input.credentials.password}}"
}
```

is logged with the template and not with the resolved password.

## API lifecycle

The Control API starts when a Camoufox run starts and stops when the process finalizes the run. In debug mode with `keep_alive=true`, the API remains available while the container remains alive; once scenario execution is completed, new inputs are rejected as a finished run.

## Scenario framework compatibility (v0.4.30)

The modular action refactor does not change Control API URLs or runtime-input payloads. `wait_input`, runtime templates, run status, and controlled failure semantics remain compatible. The API continues to interact with `RuntimeContext`; scenario actions are now dispatched internally through `ActionRegistry`.

This separation allows future action modules to consume runtime input or expose new orchestration capabilities without coupling the HTTP API implementation to individual browser actions.

## Compatibility

The API namespace begins at `/api/v1`. Future incompatible API changes must use a new version prefix rather than silently changing the v1 contract.


## Controlled run failures (v0.4.17)

A required runtime input timeout transitions the run to `failed` normally. The run artifacts contain `reason: "timeout_data_not_received"`; this is not treated as an application crash. API clients should use the run status and reason code rather than parsing Python exception text.


## Shutdown status

From v0.4.20, a run stopped by SIGINT/SIGTERM is represented as `stopped` by the runtime API while final artifacts are being completed. The final `summary.json` uses `status: "STOPPED"`, `reason: "user_interrupt"`, and records the signal number under `shutdown.signal`. This is an intentional stop, not a scenario failure.

## Identity profile configuration (v0.4.23)

The Control API can read and modify the persistent configuration of the active Identity. Profile changes are stored in `/identities/{identity}/config.json` and **apply only to the next run**.

### Read profile configuration

```http
GET /api/v1/identities/{identity}/config
```

Example:

```bash
curl -s http://localhost:8090/api/v1/identities/test-user-001/config | jq
```

Typical response:

```json
{
  "schema_version": 1,
  "identity": "test-user-001",
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
}
```

### Update profile configuration

```http
PATCH /api/v1/identities/{identity}/config
Content-Type: application/json
```

Only supplied fields are changed. Example window update:

```bash
curl -s -X PATCH \
  http://localhost:8090/api/v1/identities/test-user-001/config \
  -H 'Content-Type: application/json' \
  -d '{
    "fingerprint": {
      "window": {
        "width": 1680,
        "height": 1390
      }
    }
  }' | jq
```

Response:

```json
{
  "status": "updated",
  "identity": "test-user-001",
  "applies": "next_run",
  "config": {}
}
```

The `config` field contains the complete updated profile.

To return a field to the persistent generated Identity value, patch it back to `"default"`:

```json
{
  "fingerprint": {
    "window": "default"
  }
}
```

Invalid profile values return HTTP `400` with `error: "invalid_profile_config"`.

Generation-level changes (`os`, `preset`, `screen`, `locale`) may cause the persistent Camoufox fingerprint configuration to be regenerated on the next run while preserving the browser profile. Direct changes (`window`, DPR, hardware concurrency, WebGL vendor/renderer) do not require full fingerprint regeneration.

## Automatic baseline refresh after profile PATCH (v0.4.23)

A successful fingerprint-changing request to:

`PATCH /api/v1/identities/{identity}/config`

sets the returned Identity config field `baseline_stale` to `true`. A PATCH that does not change the effective stored fingerprint values leaves the flag unchanged.

The next container run with fingerprint diagnostics enabled automatically saves the current fingerprint as the new baseline and returns the stored profile flag to `false`. This expected change is logged as a baseline refresh rather than `Fingerprint drift detected`.

Example response fragment after a real profile change:

```json
{
  "status": "updated",
  "applies": "next_run",
  "config": {
    "baseline_stale": true
  }
}
```



## v0.4.24 Docker build note

Runtime functionality is unchanged from v0.4.23. The Docker build is split into a stable browser/runtime base image and a small application image to maximize layer reuse during development.

## Proxy-related run status — v0.4.27

The Control API contract is unchanged. When a run cannot start because of proxy validation/policy or a recognized proxy transport failure, runtime/final artifacts use a controlled `FAIL` status. `summary.json` contains a machine-readable `reason`, such as `unsupported_proxy_type` or `proxy_change_not_allowed`. Proxy configuration itself remains part of the run JSON configuration; no proxy-management API endpoint is introduced in v0.4.27.

## Action timeout failure (v0.4.30)

A hard action watchdog expiration is reported as a controlled failed run with reason `action_timeout`. API clients should treat this as a scenario/action failure, not an application crash. The failure details include the effective watchdog timeout and failed action metadata.


## Failed-run finalization (v0.4.31)

After a fatal action failure such as `reason=action_timeout`, the runtime status becomes `failed`. Browser cleanup is bounded to 4 seconds; if native cleanup hangs, the runner forcibly terminates browser child processes and continues finalization. `summary.json` includes `browser_cleanup.status` (`graceful` or `forced`) and failed runs terminate the process with exit code 1 instead of remaining alive indefinitely.


## Proxy GEO validation artifact (v0.4.32)

Proxy GEO validation does not change Control API routes. Each run summary may contain `proxy_geo_validation`, and the run directory contains `proxy-geo-validation.json`. A strict mismatch (`proxy.geoip.fail_on_mismatch=true`) ends the run with reason `proxy_identity_geo_mismatch`.


## Locale persistence note (v0.4.33)

No Control API route changes were introduced. Identity profile values for `locale`, `languages`, and `timezone` keep their existing API representation. Internally, normal browser launches now reconstruct persisted locale data through Camoufox's public `locale=` API while proxy GEO remains validation-only.

## Plugin runtime note (v0.5.1)

The Control API contract is unchanged. Plugin calls execute as normal scenario actions and therefore appear in current-run/action status and final run artifacts like built-in actions. Plugin-specific HTTP endpoints are intentionally not added to the core API; a plugin integration should expose behavior through its adapter and `plugin_call` unless a future extension explicitly requires another interface.


## Plugin failures (v0.5.2)

Expected plugin failures are controlled scenario failures. They retain their stable `reason` (for example `plugin_not_configured`, `plugin_disabled`, `plugin_import_failed`, `plugin_dependency_missing`, or `recaptcha_v2_solve_failed`) and are finalized through the normal run status/summary path without duplicate traceback logging. The Control API itself gains no new endpoint in v0.5.2; plugin execution remains scenario-driven through `plugin_call`.

## hCaptcha plugin failures (v0.5.3)

The Control API receives the normal scenario run status; no hCaptcha-specific endpoint is added. Expected adapter failures are reported through the existing structured plugin failure path. New reasons can include `hcaptcha_api_incompatible`, `hcaptcha_async_bridge_unavailable`, `hcaptcha_async_bridge_failed`, and `hcaptcha_solve_failed`.

## v0.5.5 scenario/plugin additions

No Control API endpoint changes are required for the new `select` action because scenario steps remain generic JSON actions. Plugin invocation also retains the existing `plugin_call` contract. hCaptcha custom-backend failures use controlled plugin reasons such as `hcaptcha_backend_invalid_config`, `hcaptcha_backend_load_failed`, `hcaptcha_backend_api_incompatible`, and `hcaptcha_backend_not_supported`.



## v0.5.7 hCaptcha checkbox test result

`plugin_call` with `method=checkbox_test` returns structured plugin data containing `checkbox_clicked`, `challenge_opened`, `response_present`, and frame/selector diagnostics. It does not expose or require a Gemini credential.

## v0.5.6 hCaptcha probe artifacts

Runs containing `hcaptcha-challenger` method `local_probe` save `hcaptcha-local-probe.json` under the normal run artifact directory. No new Control API endpoint is required; the probe uses the existing scenario/plugin execution path.

## v0.5.8 hCaptcha local-solve decision artifact

Runs using `hcaptcha-challenger.local_solve_test` save `hcaptcha-local-solve-test.json` in the standard run artifact directory. No new Control API endpoint is introduced. When a stable non-Gemini local solver is unavailable, the existing plugin failure path reports `reason=hcaptcha_local_solver_unavailable`; the bundled sample sets `continue_on_error: true` so the run can still produce the diagnostic artifact and screenshot.


## v0.5.9 hCaptcha status

No API contract changes. The experimental hCaptcha adapter remains disabled and its bundled sample scenarios were removed. Existing generic `plugin_call` behavior is unchanged. Detailed frozen-direction context is in `../FUTURE_BOT.md`.


## v0.5.10 runtime note

No Control API endpoint contract changed in v0.5.10. Scenario runs now track site-opened browser tabs internally, so current-action/run status continues to work while scenarios use the enhanced `switch_tab` action.


## v0.5.11 runtime note

No Control API endpoint contract changed in v0.5.11. Scenario execution now remains responsive to Playwright page events while `switch_tab` is waiting for a site-created tab.


## Outbound webhook responses
The `webhook` scenario action is outbound and does not add a Control API endpoint. Its successful response is stored in the run's in-memory runtime context and can be consumed by later scenario actions through `{{webhook.<save_as>...}}`.


## Controller orchestration boundary

The `/api/v1/identities/...` API is the Control API of a single browser worker. External systems use the implemented Controller API; orchestrated worker Control APIs remain internal on the Docker network, and the Controller routes run status and `wait_input` data to the worker assigned to each run. The public Controller request model accepts validated run/profile/scenario data rather than arbitrary Docker parameters. See `../../FUTURE.md` and `../../FUTURE_BOT.md`.


## Endpoint audit — v0.5.18-2

The Control API implementation and this reference were cross-checked. Documented v1 operations match the current server:

- `GET /api/v1/health`
- `GET /api/v1/identities/{identity}/config`
- `PATCH /api/v1/identities/{identity}/config`
- `GET /api/v1/identities/{identity}/runs`
- `GET /api/v1/identities/{identity}/runs/current`
- `GET /api/v1/identities/{identity}/runs/{run_id}`
- `POST /api/v1/identities/{identity}/runs/{run_id}/inputs/{key}`

The worker remains intentionally single-run-per-process; broader orchestration belongs to Controller.


## Worker configuration model — v0.5.19

The worker Control API is independent from the new launch-configuration layout. Startup configuration is resolved from `config.json` + `default.json` + a launch profile + one external scenario file before the API starts.

The existing `/api/v1/identities/{identity}/config` resource still manages the **persistent Identity override configuration** stored below the Identity storage root. It does not edit shared worker defaults/scenarios, local worker defaults/scenarios, or `config/profiles/*.json`.

The worker treats `default.json` and scenario definitions as read-only input. External mutation/orchestration of Identity profiles and scenario selection belongs to Controller and Web Console.
