# Controller 0.1.12

FastAPI control plane for queued, resource-aware execution of disposable
Firefox workers. PostgreSQL stores durable run/scenario/proxy records; Redis
Streams provides the operational queue, live state and bounded logs.

## Start

Create local secrets (never commit the resulting files):

```bash
openssl rand -hex 32 > secrets/controller_api_token
openssl rand 32 | openssl base64 -A | tr '+/' '-_' > secrets/controller_encryption_key
docker compose build worker-firefox
docker compose --profile controller --profile web-console up --build
```

The first command creates the Bearer token used by API clients and Web Console.
The second creates a URL-safe Base64-encoded 32-byte Fernet key without requiring
Python packages on the Docker host. It is used to encrypt proxy credentials in
PostgreSQL. Keep both files private and backed up: changing the Fernet key makes
previously encrypted proxy passwords unreadable.

Get the generated Controller API token when configuring Web Console or another
API client:

```bash
cat secrets/controller_api_token
```

Copy the printed value without adding spaces and save it under
**Settings → Controller API** in Web Console. Treat this value as a secret and
do not publish it in logs, screenshots or source control.

## Lifecycle commands

```bash
# Start or rebuild the complete Controller stack
docker compose --profile controller --profile web-console up -d --build

# Check service state
docker compose --profile controller --profile web-console ps

# Follow Controller logs
docker compose --profile controller logs -f controller

# Stop services without deleting PostgreSQL/Redis/worker volumes
docker compose --profile controller --profile web-console down
```

PostgreSQL migrations run automatically before Controller starts. Do not add
`-v` to `docker compose down` unless persistent database, Redis, Identity and
artifact volumes intentionally need to be deleted.

Controller listens on `127.0.0.1:8088`; Web Console proxies it internally at
`/api/controller`. Put the API token into Web Console Settings.

## API

- `GET /api/v1/health` is public.
- `GET/POST /api/v1/runs` lists or queues runs. List requests support a bounded
  `limit` up to 10,000 for non-dynamic client-side pagination.
- `PATCH /api/v1/runs/{id}` changes queued priority or cancels a queued run.
- `POST /api/v1/runs/{id}/stop` performs cooperative-to-forced shutdown.
- `GET /api/v1/runs/{id}/logs` and `/logs/stream` expose bounded live logs.
- `POST /api/v1/runs/{id}/stream-ticket` creates a short-lived run-scoped
  access ticket for browser media. `/novnc/...` proxies a read-only debug
  session and `/videos/{filename}` streams finalized WebM artifacts.
- `GET /api/v1/identities`, `/scenarios`, and `/proxies` populate Create Run.
- Run responses include the immutable `scenario_name` and `scenario_version` selected for that task. Scenario catalog responses include durable `run_count` per version.
- `POST /api/v1/identities` creates a persistent Identity profile;
  `GET/PUT /api/v1/identities/{identity}` reads or updates it. Profile changes
  increment `revision` and apply to the next run.
- `DELETE /api/v1/identities/{identity}` removes only profile metadata;
  `?delete_account_data=true` also removes persistent browser/account data.
  Active Identities cannot be deleted and run history/artifacts are retained.
- `GET/PUT /api/v1/settings/identity-defaults` manages the versioned base
  profile merged into every newly created Identity.
- `POST /api/v1/scenarios` creates a new immutable scenario version and makes
  it active. Existing runs keep their selected version; new runs use the latest
  active version. This is the persistence contract for the future scenario
  editor and does not require rebuilding or redeploying services.
- `DELETE /api/v1/scenarios/{name}` logically deletes all versions from the
  catalog and Create Run while retaining definitions referenced by run history.
- `POST /api/v1/scenarios/versions/{id}/activate` atomically switches the
  active version without changing version numbers or definitions.
- `POST /api/v1/scenarios/versions/{id}/clone` copies a selected version into
  an independent scenario at v1. Its name must be unique across all current and
  logically deleted scenarios.

All endpoints except health require `Authorization: Bearer <token>`.

## Debug stream and recorded video

Debug runs start noVNC only inside the application Docker network. Controller
resolves the assigned container from `run_id` and proxies both the noVNC assets
and WebSocket; the worker's port 6080 is never published on the host. Web
Console first exchanges the configured Bearer token for a short-lived,
run-scoped media ticket (default TTL: 300 seconds), so the API token is never
placed in an iframe, WebSocket or video URL.

The Workers live-stream icon is available only while a debug scenario is
running or waiting for input. The embedded noVNC client is forced into
view-only mode. When a run finishes and a non-empty `.webm` exists inside its
validated artifact directory, Web Console replaces the live icon with a
recorded-video icon and streams the file through Controller with HTTP range
support. Configure ticket lifetime with
`CONTROLLER_STREAM_TICKET_TTL_SECONDS` (30–3600 seconds).

Each worker summary stores its owning Controller `run_id`. Video discovery
requires that exact match and an explicit WebM entry in `summary.recording.files`;
legacy summaries are accepted only when Identity, scenario and start timestamp
match. A recording from another execution cannot enable playback on the wrong
Workers row.

The scheduler limits global concurrency by configured maximum and Docker host
CPU/RAM capacity. Runs are ordered by priority then creation time. Multiple runs
may be queued for the same Identity, but its per-Identity queue is serialized to
one active worker; busy profiles are skipped while free server slots are filled
with eligible runs from other Identities. Docker options are generated from a safe internal
template and cannot be overridden through the public API.

A worker-reported terminal state is treated as `finalizing` until Docker really
exits. The exit code is authoritative; Controller then reads `summary.json` from
the shared artifact volume and persists the exact failure reason, failed action,
finish time and run-specific artifact directory.

Controller materializes an immutable run configuration into a shared volume.
The existing worker resolver consumes it without changing the worker's
standalone Compose/config workflow.

## Updating a scenario without redeploy

```bash
curl -X POST http://127.0.0.1:8088/api/v1/scenarios \
  -H "Authorization: Bearer $(cat secrets/controller_api_token)" \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "identity",
    "definition": {
      "name": "identity",
      "actions": [
        {"type": "open", "url": "https://example.com"},
        {"type": "wait", "seconds": 2}
      ]
    }
  }'
```

The API assigns the next version number transactionally and deactivates the
previous active version. Scenario definitions are domain data in PostgreSQL,
not files baked into the Controller or worker image.
