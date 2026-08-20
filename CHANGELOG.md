# Application Changelog

This is the global release history for all application components. Component changelogs remain authoritative for detailed implementation-level changes.

## Unreleased

- Reorganized documentation by ownership: `worker-firefox` and `firefox-image-builder` now keep their README and detailed changelog beside their code.
- Established this root changelog as the cross-component release index.

## Component releases

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
