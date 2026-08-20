# Release Notes — worker-firefox v0.5.22

> Component root: `worker-firefox/`. Paths and commands in this document are relative to that directory unless stated otherwise.

## Resilient startup and full debug-session video

Camoufox startup now validates that its first page remains usable before diagnostics and scenario actions begin. Transient `TargetClosedError` failures during first-run addon initialization trigger a bounded retry instead of immediately failing the worker.

Debug/noVNC recording now captures the complete Xvfb display using FFmpeg. The live file is available at:

```text
artifacts/results/<identity>/<scenario>/<run-id>/videos/debug-session.webm
```

It includes automation, tab changes, manual noVNC input, and the interactive `keep_alive` period. Graceful `Ctrl+C`, `docker compose stop`, and `docker compose down` finalize the VP9 WebM file before X11 helpers stop.

Normal virtual/headless mode retains Playwright page recording and `videos/page-XX.webm` artifacts.

New defaults:

```json
{
  "browser": {
    "startup_attempts": 3,
    "startup_retry_delay_sec": 1.0
  },
  "recording": {
    "debug_backend": "x11",
    "debug_fps": 15
  }
}
```

The release was verified with 59 unit tests and an end-to-end Docker/noVNC/API/video lifecycle test.

## Base-image builder separated from worker

`worker-firefox` no longer contains `Dockerfile.base` or browser base-image construction logic.

The worker now expects a prepared immutable base image:

```text
worker-firefox-base:<browser-version>
```

The Docker build argument is:

```text
WORKER_FIREFOX_BASE_IMAGE
```

Example:

```bash
WORKER_FIREFOX_BASE_IMAGE=worker-firefox-base:153.0.0-beta.1 docker compose build worker-firefox
```

A separate standalone tool, `firefox-image-builder` v0.2.0+, is responsible for cloning the Camoufox build system, compiling/packaging the selected Firefox/Camoufox source and producing these images automatically.

The worker release therefore does not require or contain browser build assets. It only contains the thin application Dockerfile and runtime code/configuration.

The base image still embeds `/opt/camoufox-custom/SOURCE_COMMIT`, allowing the worker to record browser provenance in run artifacts.

Future Controller orchestration should select a compatible prebuilt image rather than building browser base images during run execution.
