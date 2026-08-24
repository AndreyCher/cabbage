#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  ./build.sh versions/<build>.env

Pipeline:
  1. clone Camoufox build-system source
  2. checkout configured ref/tag/commit
  3. optionally override Firefox version/release in upstream.sh
  4. use Camoufox's official Docker build flow to compile/package Linux x86_64
  5. extract the produced Camoufox package
  6. build worker-firefox-base:<version>

Requirements on host:
  docker, git, unzip, sed, awk, grep
EOF
}

if [[ $# -ne 1 ]]; then
  usage
  exit 2
fi

VERSION_FILE="$1"
if [[ ! -f "$VERSION_FILE" ]]; then
  echo "ERROR: version file not found: $VERSION_FILE" >&2
  exit 2
fi

# Explicit process-environment values must override version-file defaults.
# Preserve them before sourcing the trusted local configuration.
CONFIG_KEYS=(
  CAMOUFOX_REPO CAMOUFOX_REF TARGET_OS TARGET_ARCH PYTHON_BASE_IMAGE
  CAMOUFOX_PRERELEASE SOURCE_BUILDER_BASE_IMAGE RUST_TOOLCHAIN
  FIREFOX_VERSION_OVERRIDE CAMOUFOX_RELEASE_OVERRIDE IMAGE_TAG BUILDER_IMAGE
  KEEP_WORKDIR BUILD_JOBS BUILD_MEMORY_RESERVE_MIB BUILD_MEMORY_PER_JOB_MIB
  REBUILD_BUILDER KEEP_BUILDER_IMAGE WORK_ROOT UBO_VERSION UBO_URL UBO_SHA256
)
declare -A ENV_OVERRIDES=()
for key in "${CONFIG_KEYS[@]}"; do
  if [[ -v "$key" ]]; then
    ENV_OVERRIDES["$key"]="${!key}"
  fi
done

# Version files are trusted local tool configuration.
# shellcheck disable=SC1090
source "$VERSION_FILE"

for key in "${!ENV_OVERRIDES[@]}"; do
  printf -v "$key" '%s' "${ENV_OVERRIDES[$key]}"
done

CAMOUFOX_REPO="${CAMOUFOX_REPO:-https://github.com/daijro/camoufox.git}"
CAMOUFOX_REF="${CAMOUFOX_REF:-main}"
TARGET_OS="${TARGET_OS:-linux}"
TARGET_ARCH="${TARGET_ARCH:-x86_64}"
PYTHON_BASE_IMAGE="${PYTHON_BASE_IMAGE:-python:3.12-slim-bookworm}"
CAMOUFOX_PRERELEASE="${CAMOUFOX_PRERELEASE:-false}"
SOURCE_BUILDER_BASE_IMAGE="${SOURCE_BUILDER_BASE_IMAGE:-ubuntu:24.04}"
RUST_TOOLCHAIN="${RUST_TOOLCHAIN:-nightly-2026-07-01}"
KEEP_WORKDIR="${KEEP_WORKDIR:-false}"
BUILD_JOBS="${BUILD_JOBS:-auto}"
BUILD_MEMORY_RESERVE_MIB="${BUILD_MEMORY_RESERVE_MIB:-2048}"
BUILD_MEMORY_PER_JOB_MIB="${BUILD_MEMORY_PER_JOB_MIB:-10240}"
REBUILD_BUILDER="${REBUILD_BUILDER:-false}"
KEEP_BUILDER_IMAGE="${KEEP_BUILDER_IMAGE:-false}"
FORCE_FIREFOX_VERSION="${FIREFOX_VERSION_OVERRIDE:-}"
FORCE_CAMOUFOX_RELEASE="${CAMOUFOX_RELEASE_OVERRIDE:-}"
UBO_VERSION="${UBO_VERSION:-}"
UBO_URL="${UBO_URL:-}"
UBO_SHA256="${UBO_SHA256:-}"

if [[ -z "$UBO_VERSION" || -z "$UBO_URL" || ! "$UBO_SHA256" =~ ^[a-f0-9]{64}$ ]]; then
  echo "ERROR: UBO_VERSION, UBO_URL and a lowercase 64-character UBO_SHA256 are required" >&2
  exit 2
fi

if [[ "$TARGET_OS" != "linux" ]]; then
  echo "ERROR: worker-firefox base images currently require TARGET_OS=linux" >&2
  exit 2
fi

if [[ "$TARGET_ARCH" != "x86_64" ]]; then
  echo "ERROR: v0.2.0 currently packages worker-firefox base images for TARGET_ARCH=x86_64 only" >&2
  exit 2
fi

for cmd in docker git unzip sed awk grep find; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "ERROR: required host command not found: $cmd" >&2
    exit 2
  }
done

echo "==> Verifying host build dependencies"
docker version >/dev/null
docker buildx version >/dev/null

read -r AVAILABLE_CPUS AVAILABLE_MEMORY_BYTES < <(
  docker info --format '{{.NCPU}} {{.MemTotal}}'
)
DOCKER_ARCHITECTURE="$(docker info --format '{{.Architecture}}')"

if [[ "$DOCKER_ARCHITECTURE" != "x86_64" ]]; then
  echo "ERROR: Docker architecture must be x86_64, got: $DOCKER_ARCHITECTURE" >&2
  exit 2
fi

if [[ ! "$AVAILABLE_MEMORY_BYTES" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: unable to detect Docker memory size: $AVAILABLE_MEMORY_BYTES" >&2
  exit 2
fi
AVAILABLE_MEMORY_MIB=$((AVAILABLE_MEMORY_BYTES / 1024 / 1024))

for value_name in AVAILABLE_CPUS AVAILABLE_MEMORY_MIB BUILD_MEMORY_RESERVE_MIB BUILD_MEMORY_PER_JOB_MIB; do
  value="${!value_name}"
  if [[ ! "$value" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: $value_name must be a positive integer, got: $value" >&2
    exit 2
  fi
done

if [[ "$BUILD_JOBS" == "auto" ]]; then
  if (( AVAILABLE_MEMORY_MIB <= BUILD_MEMORY_RESERVE_MIB )); then
    MEMORY_JOBS=1
  else
    MEMORY_JOBS=$((
      (AVAILABLE_MEMORY_MIB - BUILD_MEMORY_RESERVE_MIB) /
      BUILD_MEMORY_PER_JOB_MIB
    ))
    (( MEMORY_JOBS >= 1 )) || MEMORY_JOBS=1
  fi

  EFFECTIVE_BUILD_JOBS="$AVAILABLE_CPUS"
  (( MEMORY_JOBS < EFFECTIVE_BUILD_JOBS )) && EFFECTIVE_BUILD_JOBS="$MEMORY_JOBS"
else
  if [[ ! "$BUILD_JOBS" =~ ^[1-9][0-9]*$ ]]; then
    echo "ERROR: BUILD_JOBS must be 'auto' or a positive integer, got: $BUILD_JOBS" >&2
    exit 2
  fi
  EFFECTIVE_BUILD_JOBS="$BUILD_JOBS"
fi

REQUIRED_MEMORY_MIB=$((
  BUILD_MEMORY_RESERVE_MIB + EFFECTIVE_BUILD_JOBS * BUILD_MEMORY_PER_JOB_MIB
))
if (( REQUIRED_MEMORY_MIB > AVAILABLE_MEMORY_MIB )); then
  echo "ERROR: selected BUILD_JOBS=$EFFECTIVE_BUILD_JOBS requires at least" >&2
  echo "       ${REQUIRED_MEMORY_MIB} MiB by the configured safety policy, but" >&2
  echo "       Docker exposes only ${AVAILABLE_MEMORY_MIB} MiB." >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_ROOT="${WORK_ROOT:-$SCRIPT_DIR/work}"
mkdir -p "$WORK_ROOT"
BUILD_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
BUILD_DIR="$WORK_ROOT/$BUILD_ID"
SOURCE_DIR="$BUILD_DIR/camoufox-source"
DIST_DIR="$BUILD_DIR/dist"
RUNTIME_CONTEXT="$BUILD_DIR/runtime-context"
BUILDX_BUILDER="firefox-image-builder-${BUILD_ID//[^a-zA-Z0-9_.-]/-}"
BUILDX_BUILDER_CREATED="false"
BUILDER_IMAGE_AVAILABLE="false"
FINAL_IMAGE_CREATED_THIS_RUN="false"
BUILD_COMPLETED="false"

ensure_buildx_builder() {
  if [[ "$BUILDX_BUILDER_CREATED" == "false" ]]; then
    echo "==> Creating isolated BuildKit builder"
    docker buildx create \
      --name "$BUILDX_BUILDER" \
      --driver docker-container \
      >/dev/null
    BUILDX_BUILDER_CREATED="true"
  fi
}

cleanup() {
  exit_status=$?
  set +e

  if [[ "$BUILDX_BUILDER_CREATED" == "true" ]]; then
    echo "==> Removing isolated BuildKit builder and cache"
    docker buildx rm --force "$BUILDX_BUILDER" >/dev/null 2>&1
  fi

  if [[ "$BUILD_COMPLETED" != "true" ]]; then
    if [[ "$FINAL_IMAGE_CREATED_THIS_RUN" == "true" ]]; then
      echo "==> Removing unverified runtime image: $IMAGE_TAG"
      docker image rm --force "$IMAGE_TAG" >/dev/null 2>&1
    fi
  fi

  if [[ "$BUILDER_IMAGE_AVAILABLE" == "true" && "$KEEP_BUILDER_IMAGE" != "true" ]]; then
    echo "==> Removing source-builder image: $BUILDER_IMAGE"
    docker image rm --force "$BUILDER_IMAGE" >/dev/null 2>&1
  fi

  if [[ "$KEEP_WORKDIR" == "true" ]]; then
    echo "Keeping build workspace: $BUILD_DIR"
  else
    rm -rf "$BUILD_DIR"
  fi

  return "$exit_status"
}
trap cleanup EXIT

mkdir -p "$DIST_DIR" "$RUNTIME_CONTEXT"

echo "==> Cloning Camoufox build system"
git clone "$CAMOUFOX_REPO" "$SOURCE_DIR"
git -C "$SOURCE_DIR" checkout "$CAMOUFOX_REF"

UPSTREAM_DOCKERFILE="$SOURCE_DIR/Dockerfile"
if [[ ! -f "$UPSTREAM_DOCKERFILE" ]]; then
  echo "ERROR: Dockerfile not found in Camoufox checkout" >&2
  exit 1
fi

if ! grep -Eq '^FROM[[:space:]]+ubuntu(:[^[:space:]]+)?([[:space:]]|$)' "$UPSTREAM_DOCKERFILE"; then
  echo "ERROR: unsupported Camoufox Dockerfile base image; expected FROM ubuntu..." >&2
  exit 1
fi
sed -i -E \
  "0,/^FROM[[:space:]]+ubuntu(:[^[:space:]]+)?([[:space:]]|$)/s##FROM ${SOURCE_BUILDER_BASE_IMAGE}#" \
  "$UPSTREAM_DOCKERFILE"

RUSTUP_INSTALL='bash -s -- -y'
if ! grep -Fq "$RUSTUP_INSTALL" "$UPSTREAM_DOCKERFILE"; then
  echo "ERROR: unsupported Camoufox Dockerfile rustup command" >&2
  exit 1
fi
sed -i \
  "s#${RUSTUP_INSTALL}#${RUSTUP_INSTALL} --default-toolchain ${RUST_TOOLCHAIN}#" \
  "$UPSTREAM_DOCKERFILE"

SOURCE_COMMIT_VALUE="$(git -C "$SOURCE_DIR" rev-parse HEAD)"
SOURCE_COMMIT_SHORT="$(git -C "$SOURCE_DIR" rev-parse --short HEAD)"
SOURCE_BUILDER_BASE_KEY="${SOURCE_BUILDER_BASE_IMAGE//[^a-zA-Z0-9_.-]/-}"
RUST_TOOLCHAIN_KEY="${RUST_TOOLCHAIN//[^a-zA-Z0-9_.-]/-}"

# Upstream multibuild.py does not expose Firefox's -j option. Patch only the
# temporary checkout so the runtime container can pass an explicit job count.
UPSTREAM_MAKEFILE="$SOURCE_DIR/Makefile"
MACH_BUILD_COMMAND='./mach build $(_ARGS)'
if ! grep -Fq "$MACH_BUILD_COMMAND" "$UPSTREAM_MAKEFILE"; then
  echo "ERROR: unable to locate upstream mach build command in Makefile" >&2
  exit 1
fi
sed -i 's#\./mach build \$(_ARGS)#./mach build -j$${FIREFOX_BUILD_JOBS} $(_ARGS)#' \
  "$UPSTREAM_MAKEFILE"

UPSTREAM_FILE="$SOURCE_DIR/upstream.sh"
if [[ ! -f "$UPSTREAM_FILE" ]]; then
  echo "ERROR: upstream.sh not found in Camoufox checkout" >&2
  exit 1
fi

if [[ -n "$FORCE_FIREFOX_VERSION" ]]; then
  echo "==> Overriding upstream Firefox version: $FORCE_FIREFOX_VERSION"
  sed -i -E "s/^version=.*/version=${FORCE_FIREFOX_VERSION}/" "$UPSTREAM_FILE"
fi

if [[ -n "$FORCE_CAMOUFOX_RELEASE" ]]; then
  echo "==> Overriding Camoufox release: $FORCE_CAMOUFOX_RELEASE"
  sed -i -E "s/^release=.*/release=${FORCE_CAMOUFOX_RELEASE}/" "$UPSTREAM_FILE"
fi

FIREFOX_VERSION="$(awk -F= '$1=="version"{print $2}' "$UPSTREAM_FILE")"
FIREFOX_BUILD="$(awk -F= '$1=="release"{print $2}' "$UPSTREAM_FILE")"

if [[ -z "$FIREFOX_VERSION" || -z "$FIREFOX_BUILD" ]]; then
  echo "ERROR: unable to read version/release from upstream.sh" >&2
  exit 1
fi

CAMOUFOX_BROWSER_VERSION="${FIREFOX_VERSION}-${FIREFOX_BUILD}"
IMAGE_TAG="${IMAGE_TAG:-worker-firefox-base:${CAMOUFOX_BROWSER_VERSION}}"
BUILDER_IMAGE="${BUILDER_IMAGE:-firefox-image-builder-source:${SOURCE_COMMIT_SHORT}-${CAMOUFOX_BROWSER_VERSION}-${TARGET_OS}-${TARGET_ARCH}-${SOURCE_BUILDER_BASE_KEY}-${RUST_TOOLCHAIN_KEY}-policy-v2}"

echo
echo "Build plan"
echo "  Camoufox repo:       $CAMOUFOX_REPO"
echo "  Camoufox ref:        $CAMOUFOX_REF"
echo "  source commit:       $SOURCE_COMMIT_VALUE"
echo "  Firefox version:     $FIREFOX_VERSION"
echo "  Camoufox release:    $FIREFOX_BUILD"
echo "  target:              $TARGET_OS/$TARGET_ARCH"
echo "  builder base image:  $SOURCE_BUILDER_BASE_IMAGE"
echo "  Rust toolchain:      $RUST_TOOLCHAIN"
echo "  output image:        $IMAGE_TAG"
echo "  keep builder image:  $KEEP_BUILDER_IMAGE"
echo

if [[ -n "$FORCE_FIREFOX_VERSION" || -n "$FORCE_CAMOUFOX_RELEASE" ]]; then
  cat <<'EOF'
WARNING:
  Firefox/release override mode is experimental. Camoufox patches are version-
  sensitive. A newer Firefox version may require changes to the Camoufox patch
  stack. If patch application or compilation fails, select a Camoufox ref that
  officially supports that Firefox version or update the patch set.
EOF
fi

echo "==> Detecting Docker build resources"
echo "  Docker CPUs:          $AVAILABLE_CPUS"
echo "  Docker memory:        ${AVAILABLE_MEMORY_MIB} MiB"
echo "  memory reserve:       ${BUILD_MEMORY_RESERVE_MIB} MiB"
echo "  memory per job:       ${BUILD_MEMORY_PER_JOB_MIB} MiB"
echo "  Firefox build jobs:   $EFFECTIVE_BUILD_JOBS"

if [[ "$REBUILD_BUILDER" != "true" ]] && docker image inspect "$BUILDER_IMAGE" >/dev/null 2>&1; then
  echo "==> Reusing Camoufox source-builder image"
  echo "  builder image:        $BUILDER_IMAGE"
else
  echo "==> Building Camoufox source-builder image"
  ensure_buildx_builder
  docker buildx build \
    --builder "$BUILDX_BUILDER" \
    --load \
    --pull \
    -t "$BUILDER_IMAGE" \
    "$SOURCE_DIR"
fi
BUILDER_IMAGE_AVAILABLE="true"

echo "==> Verifying source-builder toolchain compatibility"
docker run --rm --entrypoint /bin/bash "$BUILDER_IMAGE" -lc \
  'set -euo pipefail
   active_toolchain="$(rustup show active-toolchain | awk "{print \$1}")"
   [[ "$active_toolchain" == "'"$RUST_TOOLCHAIN"'-x86_64-unknown-linux-gnu" ]]
   rust_targets="$(rustc --print target-list)"
   grep -Fxq x86_64-unknown-linux-gnu <<<"$rust_targets"
   if grep -Fxq x86_64-oe-linux-gnu <<<"$rust_targets"; then
     echo "ERROR: Rust target list contains x86_64-oe-linux-gnu, which is incompatible with this Firefox source" >&2
     exit 1
   fi
   python3 --version
   rustc --version
   cargo --version'

echo "==> Compiling and packaging Camoufox from Firefox source"
docker run --rm \
  -e "FIREFOX_BUILD_JOBS=${EFFECTIVE_BUILD_JOBS}" \
  -v "$DIST_DIR:/app/dist" \
  "$BUILDER_IMAGE" \
  --target "$TARGET_OS" \
  --arch "$TARGET_ARCH"

echo "==> Locating packaged browser"
PACKAGE_ZIP="$(find "$DIST_DIR" -maxdepth 2 -type f \
  \( -name "camoufox-*-lin.${TARGET_ARCH}.zip" -o -name "*-lin.${TARGET_ARCH}.zip" \) \
  | sort | tail -n 1)"

if [[ -z "$PACKAGE_ZIP" || ! -f "$PACKAGE_ZIP" ]]; then
  echo "ERROR: no Linux ${TARGET_ARCH} Camoufox package found under $DIST_DIR" >&2
  find "$DIST_DIR" -maxdepth 3 -type f -print >&2 || true
  exit 1
fi

echo "  package: $PACKAGE_ZIP"

EXTRACT_DIR="$BUILD_DIR/extracted"
mkdir -p "$EXTRACT_DIR"
unzip -q "$PACKAGE_ZIP" -d "$EXTRACT_DIR"

CAMOUFOX_BIN="$(find "$EXTRACT_DIR" -type f -name camoufox-bin -perm -u+x | head -n 1)"
if [[ -z "$CAMOUFOX_BIN" ]]; then
  # Some zip tools/filesystems may lose the executable bit during extraction.
  CAMOUFOX_BIN="$(find "$EXTRACT_DIR" -type f -name camoufox-bin | head -n 1)"
fi

if [[ -z "$CAMOUFOX_BIN" || ! -f "$CAMOUFOX_BIN" ]]; then
  echo "ERROR: camoufox-bin not found in packaged browser" >&2
  find "$EXTRACT_DIR" -maxdepth 4 -type f -print >&2 || true
  exit 1
fi

BROWSER_ROOT="$(dirname "$CAMOUFOX_BIN")"
chmod +x "$CAMOUFOX_BIN"

echo "==> Preparing runtime image context"
cp "$SCRIPT_DIR/Dockerfile.runtime" "$RUNTIME_CONTEXT/Dockerfile"
cp "$SCRIPT_DIR/requirements.txt" "$RUNTIME_CONTEXT/requirements.txt"
mkdir -p "$RUNTIME_CONTEXT/browser"
cp -a "$BROWSER_ROOT"/. "$RUNTIME_CONTEXT/browser/"
printf '%s\n' "$SOURCE_COMMIT_VALUE" > "$RUNTIME_CONTEXT/SOURCE_COMMIT"

echo "==> Building immutable Firefox worker base image"
ensure_buildx_builder
docker buildx build \
  --builder "$BUILDX_BUILDER" \
  --load \
  --pull \
  --build-arg "PYTHON_BASE_IMAGE=$PYTHON_BASE_IMAGE" \
  --build-arg "FIREFOX_VERSION=$FIREFOX_VERSION" \
  --build-arg "FIREFOX_BUILD=$FIREFOX_BUILD" \
  --build-arg "CAMOUFOX_BROWSER_VERSION=$CAMOUFOX_BROWSER_VERSION" \
  --build-arg "CAMOUFOX_PRERELEASE=$CAMOUFOX_PRERELEASE" \
  --build-arg "SOURCE_COMMIT_VALUE=$SOURCE_COMMIT_VALUE" \
  --build-arg "UBO_VERSION=$UBO_VERSION" \
  --build-arg "UBO_URL=$UBO_URL" \
  --build-arg "UBO_SHA256=$UBO_SHA256" \
  -t "$IMAGE_TAG" \
  "$RUNTIME_CONTEXT"
FINAL_IMAGE_CREATED_THIS_RUN="true"

echo "==> Verifying image metadata and executable"
docker run --rm --entrypoint /bin/sh "$IMAGE_TAG" -c \
  'test -x /opt/camoufox-custom/camoufox-bin && test -s /opt/camoufox-custom/SOURCE_COMMIT && test -s /root/.cache/camoufox/addons/UBO/manifest.json'

BUILD_COMPLETED="true"

echo
echo "Build completed"
echo "  image:             $IMAGE_TAG"
echo "  Firefox:           $FIREFOX_VERSION"
echo "  Camoufox release:  $FIREFOX_BUILD"
echo "  source commit:     $SOURCE_COMMIT_VALUE"
echo
echo "Inspect labels:"
echo "  docker image inspect '$IMAGE_TAG' --format '{{json .Config.Labels}}'"
