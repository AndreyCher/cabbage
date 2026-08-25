# Application Changelog

This is the global release history for all application components. Component changelogs remain authoritative for detailed implementation-level changes.

## Unreleased

- Added Web Console 0.1.19-dev with scrollbar-free noVNC and recorded-video dialogs.
- Added Web Console 0.1.18-dev with media-aspect-aware live/video dialogs that resize with the current browser viewport.
- Added Controller 0.1.9, Web Console 0.1.17-dev and worker-firefox 0.5.27 with authenticated Controller-proxied noVNC for active debug runs, server-enforced view-only access and recorded WebM playback after completion.
- Added worker-firefox 0.5.26 with structured, user-readable scenario action failures instead of raw Python exception representations.
- Fixed example scenario mouse-movement stalls, its current Wikipedia selector, and durable Controller failure finalization with worker-firefox 0.5.25 and Controller 0.1.8.
- Added Web Console 0.1.16-dev with sorting across all Workers table data columns.
- Added Web Console 0.1.15-dev with non-wrapping full Identity names in Workers.
- Added Web Console 0.1.14-dev with compact right-aligned Workers status and log actions.
- Added Web Console 0.1.13-dev with right-aligned Workers status placement and precise task creation timestamps.
- Fixed scenario statistics with Controller 0.1.7 and Web Console 0.1.12-dev: Steps and durable per-version Runs are now displayed separately.
- Added firefox-image-builder 0.3.0 and worker-firefox 0.5.24 with pinned UBO 1.73.0 baked into the immutable base image.
- Added Web Console 0.1.11-dev with URL-backed section persistence across page reloads.
- Added Controller 0.1.6 and Web Console 0.1.10-dev with exact `name:version` scenario labels in Workers.
- Added Web Console 0.1.9-dev with cloning for active versions and compact tooltip-based scenario actions.
- Added Controller 0.1.5 and Web Console 0.1.8-dev with safe archived-version cloning into uniquely named independent scenarios.
- Fixed Web Console scenario trees to visibly move the activated version to the root and the previous active version into the archive.
- Added Controller 0.1.4 and Web Console 0.1.6-dev with collapsible scenario version trees and archived-version activation.
- Added Controller 0.1.3 and Web Console 0.1.5-dev with history-safe scenario deletion.
- Added Controller 0.1.2 and Web Console 0.1.4-dev with Identity defaults and guarded profile/account deletion.
- Added Controller 0.1.1 and Web Console 0.1.3-dev with editable persistent Identity profiles and versioned scenario viewing/editing/import.
- Fixed Controller bootstrap migration failure when seeding the initial JSON scenario.
- Fixed Controller scheduler locking for queued runs with optional proxy relations.
- Added a versioned correction for the initial Controller scenario and documented runtime scenario updates without service redeploy.
- Added Controller 0.1.0 with authenticated API, PostgreSQL/Redis persistence and resource-aware Docker worker scheduling.
- Added Web Console 0.1.2-dev Create Run, queue/history, priority and Stop/Cancel workflow.
- Reorganized documentation by ownership: `worker-firefox` and `firefox-image-builder` now keep their README and detailed changelog beside their code.
- Established this root changelog as the cross-component release index.

## Component releases

### firefox-image-builder 0.2.2

- Pinned the source-builder OS and Rust toolchain for the known Firefox 152 build.
- Added early Docker, architecture, memory and Rust target compatibility checks.
- Corrected environment override precedence and made automatic parallelism safe for memory-heavy Rust LTO.
- Detailed history: `tools/firefox-image-builder/CHANGELOG.md`.

### web-console 0.1.1-dev

- Synchronized the console with the modular worker layout and root deployment workflow.
- Revalidated the production image and global component-registry integration.
- Detailed history: `web-console/CHANGELOG.md`.

### worker-firefox 0.5.23

- Moved the component into `workers/worker-firefox/` while preserving root-integrated and autonomous Compose operation.
- Added shared defaults and scenarios under `workers/config/`, optional local defaults and complete local scenario replacement.
- Flattened artifact storage to `artifacts/<identity>/<scenario>/<run-id>/`.
- Verified all 61 unit tests, both Docker build modes and Control API startup.
- Detailed history: `workers/worker-firefox/CHANGELOG.md`.

### web-console 0.1.0-dev

- Released the first React/TypeScript and Material UI control-plane interface.
- Added a live component overview backed by the global component registry and temporary Nginx API proxies.
- Added collapsible navigation, system/light/dark appearance modes and a module extension contract for pages, menu entries and settings.
- Detailed history: `web-console/CHANGELOG.md`.

### data-provider 0.1.0

- Promoted the worker-local webhook mock into a standalone, independently versioned data-resolution component.
- Added a generic backend provider interface and initial mounted JSON provider.
- Added versioned API endpoints while preserving the previous mock endpoint for compatibility.
- Detailed history: `data-provider/CHANGELOG.md`.

### worker-firefox 0.5.22

- Added resilient Camoufox startup readiness retries.
- Added complete Xvfb/noVNC debug-session recording with live and gracefully finalized VP9 WebM output.
- Preserved Playwright recording for normal virtual/headless runs.
- Added deterministic local pytest discovery; all 59 tests pass.
- Detailed history: `workers/worker-firefox/CHANGELOG.md`.

### worker-firefox 0.5.21-1

- Documentation-only synchronization with `firefox-image-builder` v0.2.0.
- Clarified the boundary between worker runtime images and the standalone browser base-image builder.
- Runtime behavior is unchanged from `worker-firefox` v0.5.21.
- Detailed history: `workers/worker-firefox/CHANGELOG.md`.

### firefox-image-builder 0.2.0

- Introduced the complete source-build pipeline: Camoufox checkout, Firefox source preparation, compilation, packaging and immutable worker base-image creation.
- Removed the old requirement for operator-provided `camoufox-custom.zip` and `SOURCE_COMMIT` inputs.
- Detailed history: `tools/firefox-image-builder/CHANGELOG.md`.
