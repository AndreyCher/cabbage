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

# Version files are trusted local tool configuration.
# shellcheck disable=SC1090
source "$VERSION_FILE"

CAMOUFOX_REPO="${CAMOUFOX_REPO:-https://github.com/daijro/camoufox.git}"
CAMOUFOX_REF="${CAMOUFOX_REF:-main}"
TARGET_OS="${TARGET_OS:-linux}"
TARGET_ARCH="${TARGET_ARCH:-x86_64}"
PYTHON_BASE_IMAGE="${PYTHON_BASE_IMAGE:-python:3.12-slim-bookworm}"
CAMOUFOX_PRERELEASE="${CAMOUFOX_PRERELEASE:-false}"
KEEP_WORKDIR="${KEEP_WORKDIR:-false}"
BUILD_JOBS="${BUILD_JOBS:-auto}"
BUILD_MEMORY_RESERVE_MIB="${BUILD_MEMORY_RESERVE_MIB:-1024}"
BUILD_MEMORY_PER_JOB_MIB="${BUILD_MEMORY_PER_JOB_MIB:-2048}"
REBUILD_BUILDER="${REBUILD_BUILDER:-false}"
KEEP_BUILDER_IMAGE="${KEEP_BUILDER_IMAGE:-false}"
FORCE_FIREFOX_VERSION="${FIREFOX_VERSION_OVERRIDE:-}"
FORCE_CAMOUFOX_RELEASE="${CAMOUFOX_RELEASE_OVERRIDE:-}"

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

SOURCE_COMMIT_VALUE="$(git -C "$SOURCE_DIR" rev-parse HEAD)"
SOURCE_COMMIT_SHORT="$(git -C "$SOURCE_DIR" rev-parse --short HEAD)"

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
BUILDER_IMAGE="${BUILDER_IMAGE:-firefox-image-builder-source:${SOURCE_COMMIT_SHORT}-${CAMOUFOX_BROWSER_VERSION}-${TARGET_OS}-${TARGET_ARCH}-jobs-v1}"

echo
echo "Build plan"
echo "  Camoufox repo:       $CAMOUFOX_REPO"
echo "  Camoufox ref:        $CAMOUFOX_REF"
echo "  source commit:       $SOURCE_COMMIT_VALUE"
echo "  Firefox version:     $FIREFOX_VERSION"
echo "  Camoufox release:    $FIREFOX_BUILD"
echo "  target:              $TARGET_OS/$TARGET_ARCH"
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
read -r AVAILABLE_CPUS AVAILABLE_MEMORY_BYTES < <(
  docker info --format '{{.NCPU}} {{.MemTotal}}'
)

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
    -t "$BUILDER_IMAGE" \
    "$SOURCE_DIR"
fi
BUILDER_IMAGE_AVAILABLE="true"

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
  -t "$IMAGE_TAG" \
  "$RUNTIME_CONTEXT"
FINAL_IMAGE_CREATED_THIS_RUN="true"

echo "==> Verifying image metadata and executable"
docker run --rm --entrypoint /bin/sh "$IMAGE_TAG" -c \
  'test -x /opt/camoufox-custom/camoufox-bin && test -s /opt/camoufox-custom/SOURCE_COMMIT'

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
