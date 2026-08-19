# Release Notes — worker-firefox v0.5.21

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
