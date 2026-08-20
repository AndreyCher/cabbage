# Cabbage application workspace

This directory is the current source of truth for the application and its independently versioned components.

`cabbage` is an internal configurable project codename. Public component names, APIs, Docker resources and environment variables remain neutral and must not be derived from this codename.

## Components

### worker-firefox

Current version: **0.5.22**

Firefox/Camoufox execution worker with modular scenario actions, plugin adapters, persistent Identity profiles, recording/debug support and a per-worker Control API.

- Code and component documentation: `worker-firefox/`
- Overview: `worker-firefox/README.md`
- Detailed component history: `worker-firefox/CHANGELOG.md`
- Current release notes: `worker-firefox/RELEASE_NOTES.md`

### firefox-image-builder

Current version: **0.2.0**

Standalone source builder for immutable `worker-firefox-base:<browser-version>` images. It owns the Camoufox source checkout, Firefox/Camoufox compilation, browser packaging and embedded source provenance.

- Code and component documentation: `tools/firefox-image-builder/`
- Overview: `tools/firefox-image-builder/README.md`
- Detailed component history: `tools/firefox-image-builder/CHANGELOG.md`

### controller

Planned control-plane component. It will own queues, run state, worker assignment and the external application API. It is not implemented yet; the approved direction is documented in `FUTURE.md` and `FUTURE_BOT.md`.

### data-provider

Current version: **0.1.0**

Standalone data-resolution service used by automated workers. The initial backend reads mounted JSON; its provider interface is intended for Redis, PostgreSQL, secret stores and external APIs.

- Code and component documentation: `data-provider/`
- Overview: `data-provider/README.md`
- Detailed component history: `data-provider/CHANGELOG.md`

## Documentation ownership

- `AGENT.md` — durable agent memory, architecture decisions, release rules and the complete documentation map.
- `CHANGELOG.md` — global application changelog covering releases of every component.
- `FUTURE.md` — concise application roadmap.
- `FUTURE_BOT.md` — detailed implementation-oriented notes for deferred work.
- `worker-firefox/*.md` — documentation owned by the Firefox worker module.
- `data-provider/*.md` — documentation owned by the worker-facing data-resolution component.
- `tools/firefox-image-builder/*.md` — documentation owned by the base-image builder module.

Each component keeps its detailed release history beside its code. Every component release must also receive a concise entry in the global `CHANGELOG.md`.
