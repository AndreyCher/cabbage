# Release Notes — worker-firefox v0.5.23

## Modular worker layout

The component now lives at `workers/worker-firefox/`, leaving the `workers/` namespace ready for additional implementations such as `worker-android`.

The preferred integrated workflow runs from the repository root:

```bash
docker compose build worker-firefox
docker compose up worker-firefox
WORKER_DEBUG_PROFILE=test-user-001-debug docker compose --profile debug up worker-firefox-debug
```

`worker-firefox` remains intentionally autonomous and supports the same commands from its component directory.

## Shared configuration

Shared worker configuration now lives under `workers/config/`:

```text
workers/config/default.json
workers/config/scenarios/*.json
```

The shared default is required. `workers/worker-firefox/config/default.json` is optional and is deep-merged over it when present. Profiles remain local to the concrete worker.

Scenario resolution uses complete file replacement: a local file under `workers/worker-firefox/config/scenarios/` wins over a same-named shared file. Scenario files and action arrays are never merged.

## Artifact layout

Runs are now written without the redundant `results/` level:

```text
workers/worker-firefox/artifacts/<identity>/<scenario>/<run-id>/
```

Existing artifacts were migrated without deleting historical run data.

This release is verified by 61 unit tests, root and autonomous Docker builds, standalone configuration resolution, and a healthy Control API startup.
