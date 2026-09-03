# Controller changelog

## 0.1.14

- Added reusable default proxy references to Identity profiles and immutable Scenario versions.
- Resolved run proxy selection as explicit run configuration, Scenario default, Identity default, then no proxy; explicit disabled mode always wins.
- Added the `0008_context_proxy_defaults` migration and exposed both references through the typed Controller API.
- Added OpenAPI contract coverage for the new Identity and Scenario proxy fields.

## 0.1.13

- Made PostgreSQL the canonical source for typed Identity and per-run worker configuration and exposed its JSON Schema for Web UI form generation.
- Materialized complete immutable worker defaults, Identity configuration, scenario and run overrides into a read-only per-run configuration tree.
- Added authenticated runtime status and `wait_input` delivery endpoints addressed by Controller run ID.
- Added worker health/readiness gating, startup timeout and enforced whole-run timeout handling.
- Added complete HTTP/HTTPS proxy transport and GEO policy fields, proxy update/disable operations and removed unsupported SOCKS5 creation.
- Added guarded Identity reset/update operations and actual materialized runtime-profile inspection.
- Added Docker init and retained safe allow-listed container environment, volumes, network and resource limits.
- Added `0006_full_worker_control` plus `0007_worker_defaults` migrations and unit coverage for configuration validation, materialization and timeout calculations.
- Verified 14 Controller unit/OpenAPI tests, 69 worker tests, both Docker image builds, live migrations, DB-backed defaults, normal completion, runtime-input delivery, timeout finalization, manual stop finalization, and Identity create/update/reset cycles.

## 0.1.12

- Allowed multiple queued runs for an Identity that already has an active or queued run.
- Added per-Identity serialization on top of global resource capacity: at most one active worker per Identity while other profiles continue using free server slots.
- Fixed scheduler head-of-line blocking by scanning the global priority/FIFO queue past busy Identities until all available slots are filled.
- Preserved queued priority changes and cancellation independently for every pending run.

## 0.1.11

- Increased the authenticated run-list ceiling to 10,000 so Web Console can load a complete client-side pagination dataset without incremental requests.
- Kept API-side validation and a bounded response limit.

## 0.1.10

- Bound artifact discovery to the exact Controller run ID stored in worker summary metadata.
- Added a timestamp-validated compatibility check for summaries created before Controller run IDs were embedded.
- Prevented unrelated recordings from another run of the same Identity/scenario from enabling video playback.
- Required the run summary to explicitly list each non-empty WebM before exposing the playback action.

## 0.1.9

- Added short-lived, run-scoped Redis tickets for browser media access.
- Added Controller-only HTTP/WebSocket proxying from Web Console to internal debug noVNC endpoints.
- Added safe recorded WebM discovery and range-capable streaming from validated artifact directories.
- Forced Controller debug runs to materialize `browser.mode=debug` regardless of Identity configuration.
- Kept ephemeral worker noVNC ports private to the internal Docker network.

## 0.1.8

- Kept runs non-terminal while workers finalize artifacts and made Docker exit authoritative.
- Persisted precise worker failure reasons, final timestamps, failed actions, and exact artifact directories from summary.json.

## 0.1.7

- Added per-version run counts to scenario catalog responses using durable run-to-scenario relationships.

## 0.1.6

- Added the immutable scenario version to run API responses.

## 0.1.5

- Added an authenticated scenario-version clone endpoint that creates an independent v1 scenario and rejects reused names across the complete scenario history.

## 0.1.4

- Added atomic activation of any archived scenario version.
- Preserved immutable version numbers and definitions during active-version switches.

## 0.1.3

- Added history-safe logical deletion for an entire scenario and all versions.
- Excluded deleted scenarios from catalog and Create Run without breaking runs.

## 0.1.2

- Added versioned default Identity profile settings in PostgreSQL.
- Added safe profile-only and profile-plus-account-data deletion modes.
- Prevented deletion of active Identities and retained run history/artifacts.
- Merged server-owned defaults into every newly created Identity.

## 0.1.1

- Added durable editable Identity profiles and revision tracking in PostgreSQL.
- Applied Identity configuration between system defaults and per-run overrides.
- Added API support for listing archived scenario versions for the editor.
- Added stricter scenario action-array validation and server-owned version metadata.

## 0.1.0

- Fixed initial scenario seeding to use a typed Alembic bulk insert so JSON
  values cannot be interpreted as SQL bind parameters.
- Limited scheduler row locks to `runs`, avoiding PostgreSQL rejection of
  `FOR UPDATE` on the nullable proxy relationship join.
- Added a corrective versioned migration replacing the unsupported seed
  `goto` action with valid `open`/`wait`/`screenshot` actions.
- Documented the no-redeploy scenario versioning contract used by the future editor.
- Added authenticated run, history, queue priority, stop, logs and catalog API.
- Added PostgreSQL persistence and versioned scenario schema.
- Added Redis Streams operational queue, state and bounded logs.
- Added resource-aware asynchronous Docker scheduler and executor abstraction.
- Added immutable per-run worker configuration materialization.
