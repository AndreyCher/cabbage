# firefox-image-builder

Standalone source builder for immutable base images consumed by `worker-firefox`.

Paths and commands in this document are relative to the current `tools/firefox-image-builder/` directory unless stated otherwise.

Version: **0.3.0**

Unlike v0.1.0, this tool does **not** require a prebuilt `camoufox-custom.zip` or a manually supplied `SOURCE_COMMIT`.

It performs the complete chain:

```text
Camoufox Git repository
        ↓
checkout ref/tag/commit
        ↓
Firefox source download
        ↓
Camoufox additions + patches
        ↓
Firefox/Camoufox compilation
        ↓
Camoufox Linux package
        ↓
extract browser package
        ↓
worker-firefox-base:<version>
```

The source build is delegated to Camoufox's own Docker build system and `multibuild.py` interface rather than reimplementing the patch/compiler process here.

## Why this tool exists

`worker-firefox` is an execution module and should not contain a Firefox compiler toolchain.

This builder is used only when:
- a new Camoufox/Firefox browser version is required;
- a specific Camoufox tag/commit must be reproduced;
- an experimental newer Firefox version should be tested against the current Camoufox patch stack;
- stable base runtime dependencies need to be rebuilt.

Normal `worker-firefox` releases reuse an already-built image.

## Host requirements

The host needs:

```text
Docker
Git
unzip
sed
awk
grep
find
```

The heavy Firefox compiler dependencies run inside Camoufox's official builder image.

Before cloning sources, `build.sh` verifies that the Docker daemon and Buildx
are available, the Docker architecture is `x86_64`, and the reported CPU and
memory values are valid. Explicit environment values take precedence over the
version file, so one-off overrides work as expected:

```bash
BUILD_JOBS=1 REBUILD_BUILDER=true ./build.sh versions/152.0.4-beta.28.env
```

### Automatic resource tuning

Before compilation, `build.sh` detects the CPU count and memory available to
the Docker daemon. Firefox build parallelism is capped by both resources. By
default, the builder reserves 2048 MiB for the operating system/build
orchestration and budgets 10240 MiB for each compiler job. The larger per-job
budget accounts for Firefox's final Rust LTO stages, where one `rustc` process
can exceed 9 GiB RSS. An unsafe explicit job count is rejected before Firefox
compilation starts.

The version file can override the policy:

```text
BUILD_JOBS="auto"
BUILD_MEMORY_RESERVE_MIB="2048"
BUILD_MEMORY_PER_JOB_MIB="10240"
```

Set `BUILD_JOBS` to a positive integer only when a fixed value is intentional.
The effective values are printed before compilation. For example, a Docker
environment with 12 CPUs and 16 GiB selects one build job with the defaults,
avoiding OOM kills during Rust LTO.

Camoufox's `multibuild.py` does not expose Firefox's jobs option. The builder
therefore adjusts the cloned temporary checkout's Makefile to pass the
calculated value as `mach build -jN`. The upstream repository is not modified.

### Reproducible toolchain and compatibility preflight

Known version files pin both the Camoufox source-builder base image and Rust:

```text
SOURCE_BUILDER_BASE_IMAGE="ubuntu:24.04"
RUST_TOOLCHAIN="nightly-2026-07-01"
```

The builder rewrites Camoufox's floating `ubuntu:latest` and default rustup
toolchain only in the temporary checkout. Before Firefox compilation it verifies
the active Rust toolchain, the required `x86_64-unknown-linux-gnu` target and
the absence of the incompatible `x86_64-oe-linux-gnu` target. Unexpected
upstream Dockerfile structure, insufficient Docker memory, or an incompatible
toolchain fails early instead of after a partial Firefox build.

The source-builder image uses a deterministic tag derived from the Camoufox
commit, browser version, target, pinned build dependencies and resource-policy
revision. By default this
multi-gigabyte intermediate image is removed when the invocation finishes,
because a browser version is normally compiled only once. Set
`KEEP_BUILDER_IMAGE="true"` to retain it for an expected repeat build or for
debugging. A retained matching image is reused on the next run; set
`REBUILD_BUILDER="true"` only when a clean source-builder rebuild is required.

### Automatic cleanup

Each invocation creates its own isolated BuildKit builder. Its cache is removed
by the exit trap after both successful and failed runs, so this tool does not
accumulate cache in Docker's shared default builder or remove caches belonging
to other projects.

The source-builder image used by the invocation is also removed after either a
successful or failed run unless `KEEP_BUILDER_IMAGE="true"`. Any unverified
runtime image is removed after a failure. The temporary source workspace
remains controlled separately by `KEEP_WORKDIR`.

## Directory layout

```text
firefox-image-builder/
├── VERSION
├── CHANGELOG.md
├── README.md
├── build.sh
├── Dockerfile.runtime
├── requirements.txt
└── versions/
    ├── 152.0.4-beta.28.env
    └── custom-firefox.example.env
```

There is no `assets/` directory and no browser ZIP input.

## Rebuild a known Camoufox release

For the currently known worker browser:

```bash
./build.sh versions/152.0.4-beta.28.env
```

The version file uses:

```text
CAMOUFOX_REF=v152.0.4-beta.28
```

The builder clones the Camoufox repository, checks out that ref and reads Firefox/release values from the checked-out `upstream.sh`.

Expected output image (including the pinned UBO layer):

```text
worker-firefox-base:152.0.4-beta.28-ubo1
```

## Build another officially supported Firefox/Camoufox version

Create another version file:

```bash
cp versions/152.0.4-beta.28.env versions/<new-version>.env
```

Normally only change:

```text
CAMOUFOX_REF
IMAGE_TAG
```

For example, when the Camoufox repository provides a tag that already pins a newer Firefox version:

```bash
CAMOUFOX_REF="v153.0.1-beta.29"
IMAGE_TAG="worker-firefox-base:153.0.1-beta.29"
```

Then:

```bash
./build.sh versions/<new-version>.env
```

The exact available tag/version depends on the upstream Camoufox repository.

## Experimental Firefox version override

Camoufox patches are tied to Firefox internals. A newer Firefox release is **not guaranteed** to accept an older Camoufox patch stack.

The tool nevertheless supports an advanced override for development/testing:

```bash
CAMOUFOX_REF="main"
FIREFOX_VERSION_OVERRIDE="153.0.0"
CAMOUFOX_RELEASE_OVERRIDE="custom.1"
IMAGE_TAG="worker-firefox-base:153.0.0-custom.1"
```

See:

```text
versions/custom-firefox.example.env
```

The builder changes the checked-out temporary `upstream.sh`; it does not modify the remote repository.

If patch application or compilation fails, this generally means the selected Camoufox patch stack is not compatible with that Firefox version. At that point use a newer compatible Camoufox ref or update/test the Camoufox patches.

## What build.sh does

### 1. Source checkout

```text
git clone <CAMOUFOX_REPO>
git checkout <CAMOUFOX_REF>
```

It records:

```bash
git rev-parse HEAD
```

as browser `SOURCE_COMMIT`.

### 2. Optional upstream override

When configured, the temporary checkout's:

```text
upstream.sh
```

is changed from its pinned Firefox/release values to the requested experimental values.

### 3. Build Camoufox's own builder image

Equivalent conceptually to upstream's documented flow:

```bash
docker build -t <temporary-builder> <camoufox-source>
```

### 4. Compile/package Linux x86_64

The tool invokes the upstream builder:

```bash
docker run \
  -v <temporary-dist>:/app/dist \
  <temporary-builder> \
  --target linux \
  --arch x86_64
```

Firefox source download, Camoufox patch application and compilation happen inside that upstream build pipeline.

### 5. Extract resulting browser

The generated package is located under `dist/`, for example:

```text
camoufox-152.0.4-beta.28-lin.x86_64.zip
```

The builder extracts the package and locates:

```text
camoufox-bin
```

No intermediate `camoufox-custom.zip` is required from the operator.

### 6. Create runtime base image

`Dockerfile.runtime` installs stable runtime dependencies and copies the freshly built browser under:

```text
/opt/camoufox-custom/
```

It also downloads the exact UBO release declared by `UBO_VERSION` and
`UBO_URL`, verifies `UBO_SHA256`, and extracts it into Camoufox's shared addon
cache at `/root/.cache/camoufox/addons/UBO`. Worker containers therefore do not
download or extract the default addon during startup.

The automatically captured source commit is stored at:

```text
/opt/camoufox-custom/SOURCE_COMMIT
```

### 7. Verify

The resulting image is started briefly to verify that:

```text
/opt/camoufox-custom/camoufox-bin
/opt/camoufox-custom/SOURCE_COMMIT
```

exist and are usable.

## Image metadata

The resulting Docker image contains labels:

```text
worker.type=firefox
browser.runtime=camoufox
browser.version=<Firefox version>
browser.build=<Camoufox release>
browser.runtime_version=<combined version>
browser.source_commit=<Git commit>
```

Example inspection:

```bash
docker image inspect worker-firefox-base:152.0.4-beta.28 \
  --format '{{json .Config.Labels}}'
```

These labels are intended to allow the future `controller` to choose and validate compatible prepared browser images without invoking a compiler during a run.

## Workspace

By default temporary source/build files are removed after completion:

```bash
KEEP_WORKDIR="false"
```

For debugging a failed patch/build:

```bash
KEEP_WORKDIR="true"
```

The workspace remains under:

```text
work/<build-id>/
```

This directory is gitignored.

## Responsibility boundary

### firefox-image-builder

Owns:

```text
Camoufox source checkout
Firefox source acquisition
Camoufox patch application
browser compilation
browser packaging
SOURCE_COMMIT capture
stable Linux/browser runtime image
base-image metadata
```

### worker-firefox

Owns:

```text
configuration
profiles
scenarios
Identity persistence
Action Engine
plugins
Control API
diagnostics
recording
artifacts
```

`worker-firefox` must not contain the browser compiler toolchain.

## Upstream build source

The builder follows the build interface provided by the Camoufox repository itself:

```text
https://github.com/daijro/camoufox
```

Camoufox's build system fetches upstream Firefox source, applies its additions/patches and supports Docker builds through `multibuild.py`.
