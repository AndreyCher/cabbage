# Changelog — firefox-image-builder

Paths and commands in this document are relative to the current `tools/firefox-image-builder/` directory unless stated otherwise.

## 0.3.0

- Added pinned, SHA-256-verified UBO installation to immutable runtime base images.
- Added `Dockerfile.addons` for creating an addon-enhanced base from an already verified browser base without recompiling Firefox.
- Published the local `worker-firefox-base:152.0.4-beta.28-ubo1` base with UBO 1.73.0.

## 0.2.2

- Pinned the known Firefox 152 build to Ubuntu 24.04 and Rust nightly 2026-07-01 instead of Camoufox's floating `ubuntu:latest` and current rustup default.
- Added an early source-builder compatibility preflight for the active Rust toolchain and Linux x86_64 target list.
- Added guarded upstream Dockerfile transformations that fail early when Camoufox changes the expected base-image or rustup commands.
- Increased the automatic memory budget to 10240 MiB per Firefox compiler job plus a 2048 MiB reserve after observing Rust LTO exceed 9 GiB RSS.
- Added an early memory-policy failure for unsafe explicit job counts.
- Fixed configuration precedence so explicit environment overrides such as `BUILD_JOBS=1` and `REBUILD_BUILDER=true` are no longer overwritten by the version file.
- Added an early Docker daemon, Buildx, architecture and resource preflight before cloning sources or starting image builds.

## 0.2.1

- Added automatic Firefox build parallelism selection based on the CPU count and memory available to the Docker daemon.
- Added configurable `BUILD_JOBS`, `BUILD_MEMORY_RESERVE_MIB` and `BUILD_MEMORY_PER_JOB_MIB` resource-policy controls.
- Added an explicit `mach build -jN` bridge for Camoufox's upstream build flow, preventing memory exhaustion from unchecked host CPU parallelism.
- Added a per-invocation isolated BuildKit builder so builder cache can be removed without touching caches owned by other projects.
- Added automatic isolated BuildKit cache cleanup after both successful and failed runs.
- Added cleanup of unverified runtime images after failed builds.
- Changed source-builder retention to opt-in: multi-gigabyte intermediate images are removed by default after successful and failed runs.
- Added `KEEP_BUILDER_IMAGE="true"` for deliberately retaining a source-builder for repeated compilation or debugging.
- Added deterministic source-builder tags for safe reuse when retention is enabled.
- Verified the complete source checkout, Firefox/Camoufox compilation, packaging, runtime-image build and executable validation flow for `worker-firefox-base:152.0.4-beta.28`.

## 0.2.0

- Replaced the v0.1.0 package-only workflow with a complete browser source-build pipeline.
- Removed manual `camoufox-custom.zip` input.
- Removed manual `SOURCE_COMMIT` input.
- Added automatic Camoufox Git clone/ref checkout.
- Added automatic source commit capture through Git.
- Added use of Camoufox's official Docker/multibuild pipeline for Firefox source download, patching, compilation and packaging.
- Added reproducible ref/tag builds.
- Added optional advanced Firefox/release overrides through temporary `upstream.sh` changes.
- Added automatic package discovery/extraction and `camoufox-bin` validation.
- Added final `worker-firefox-base:<version>` runtime image creation.
- Added image metadata labels for future Controller compatibility checks.
- Added automatic final image verification.
- Added optional retained work directory for debugging incompatible Firefox/patch builds.

## 0.1.0

- Initial image packager.
- Required an externally prebuilt `camoufox-custom.zip` and `SOURCE_COMMIT`.
- Superseded by v0.2.0.
