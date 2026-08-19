# firefox-image-builder

Standalone source builder for immutable base images consumed by `worker-firefox`.

Version: **0.2.0**

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
find
```

The heavy Firefox compiler dependencies run inside Camoufox's official builder image.

## Directory layout

```text
firefox-image-builder-v0.2.0/
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

Expected output image:

```text
worker-firefox-base:152.0.4-beta.28
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
