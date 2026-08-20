# Application Changelog

This is the global release history for all application components. Component changelogs remain authoritative for detailed implementation-level changes.

## Unreleased

- Reorganized documentation by ownership: `worker-firefox` and `firefox-image-builder` now keep their README and detailed changelog beside their code.
- Established this root changelog as the cross-component release index.

## Component releases

### worker-firefox 0.5.22

- Added resilient Camoufox startup readiness retries.
- Added complete Xvfb/noVNC debug-session recording with live and gracefully finalized VP9 WebM output.
- Preserved Playwright recording for normal virtual/headless runs.
- Added deterministic local pytest discovery; all 59 tests pass.
- Detailed history: `worker-firefox/CHANGELOG.md`.

### worker-firefox 0.5.21-1

- Documentation-only synchronization with `firefox-image-builder` v0.2.0.
- Clarified the boundary between worker runtime images and the standalone browser base-image builder.
- Runtime behavior is unchanged from `worker-firefox` v0.5.21.
- Detailed history: `worker-firefox/CHANGELOG.md`.

### firefox-image-builder 0.2.0

- Introduced the complete source-build pipeline: Camoufox checkout, Firefox source preparation, compilation, packaging and immutable worker base-image creation.
- Removed the old requirement for operator-provided `camoufox-custom.zip` and `SOURCE_COMMIT` inputs.
- Detailed history: `tools/firefox-image-builder/CHANGELOG.md`.
