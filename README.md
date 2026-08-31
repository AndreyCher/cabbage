# Cabbage application workspace

This directory is the current source of truth for the application and its independently versioned components.

`config/components.json` is the global component/API registry used by Web Console for health discovery and internal proxy routing. Controller is the implemented control plane for workers; distributed service discovery remains future work.

`workers/config/` contains configuration shared by worker types: the required global `default.json` and reusable scenarios. A concrete worker may optionally override defaults and fully replace individual scenarios in its own `config/` directory.

`cabbage` is an internal configurable project codename. Public component names, APIs, Docker resources and environment variables remain neutral and must not be derived from this codename.

## Components

### worker-firefox

Current version: **0.5.30**

Firefox/Camoufox execution worker with modular scenario actions, plugin adapters, persistent Identity profiles, reliable full-session X11/FFmpeg recording, debug support and a per-worker Control API.

- Code and component documentation: `workers/worker-firefox/`
- Overview: `workers/worker-firefox/README.md`
- Detailed component history: `workers/worker-firefox/CHANGELOG.md`
- Current release notes: `workers/worker-firefox/RELEASE_NOTES.md`

### firefox-image-builder

Current version: **0.3.0**

Standalone source builder for immutable `worker-firefox-base:<browser-version>` images. It owns Camoufox compilation, browser provenance and pinned addon layers. The current base `worker-firefox-base:152.0.4-beta.28-ubo1` includes SHA-256-verified UBO 1.73.0.

- Code and component documentation: `tools/firefox-image-builder/`
- Overview: `tools/firefox-image-builder/README.md`
- Detailed component history: `tools/firefox-image-builder/CHANGELOG.md`

### controller

Current version: **0.1.13**

FastAPI control plane with authenticated API, PostgreSQL history/configuration,
Redis queue/live state, global resource-aware and per-Identity serialized Docker scheduling, disposable workers
authenticated noVNC/video proxying, typed complete worker configuration,
runtime-input routing, readiness and run timeouts without direct worker exposure.

- Code and documentation: `controller/`
- SQL migrations: `databases/postgres/migrations/`

### data-provider

Current version: **0.1.0**

Standalone data-resolution service used by automated workers. The initial backend reads mounted JSON; its provider interface is intended for Redis, PostgreSQL, secret stores and external APIs.

- Code and component documentation: `data-provider/`
- Overview: `data-provider/README.md`
- Detailed component history: `data-provider/CHANGELOG.md`

### web-console

Current development release: **0.1.27-dev**

React/TypeScript control-plane interface using Material UI. It provides Controller-backed worker queue/history, versioned scenario and Identity management, Create Run, live logs, responsive read-only debug streams, automatic recorded-video playback, sorting, persisted navigation, settings and service health.

- Code and documentation: `web-console/`
- Detailed component history: `web-console/CHANGELOG.md`

## Documentation ownership

- `AGENT.md` — durable agent memory, architecture decisions, release rules and the complete documentation map.
- `CHANGELOG.md` — global application changelog covering releases of every component.
- `FUTURE.md` — concise application roadmap.
- `FUTURE_BOT.md` — detailed implementation-oriented notes for deferred work.
- `workers/worker-firefox/*.md` — documentation owned by the Firefox worker module.
- `data-provider/*.md` — documentation owned by the worker-facing data-resolution component.
- `tools/firefox-image-builder/*.md` — documentation owned by the base-image builder module.

Each component keeps its detailed release history beside its code. Every component release must also receive a concise entry in the global `CHANGELOG.md`.

## Running components

Run integrated application Docker Compose commands from the repository root. The root `compose.yml` is the primary application entry point and includes worker definitions from `workers/`.

```bash
docker compose build worker-firefox
docker compose up worker-firefox
WORKER_DEBUG_PROFILE=test-user-001-debug docker compose --profile debug up worker-firefox-debug
```

Controller stack:

```bash
openssl rand -hex 32 > secrets/controller_api_token
openssl rand 32 | openssl base64 -A | tr '+/' '-_' > secrets/controller_encryption_key
docker compose build worker-firefox
docker compose --profile controller --profile web-console up -d --build
```

Open `http://localhost:3000`, then save the value from
`secrets/controller_api_token` under **Settings → Controller API**. Database
migrations execute automatically during Controller startup. Detailed startup,
status, log and shutdown commands are documented in `controller/README.md`.

Print the Controller API token:

```bash
cat secrets/controller_api_token
```

`worker-firefox` is intentionally the only current autonomous component. In addition to the preferred root workflow, it may be built and run directly from `workers/worker-firefox/`. Other components are not required to provide a standalone Compose workflow unless that requirement is explicitly introduced later.
