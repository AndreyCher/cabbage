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
  docker, git, unzip, sed, awk
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

for cmd in docker git unzip sed awk find; do
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

cleanup() {
  if [[ "$KEEP_WORKDIR" == "true" ]]; then
    echo "Keeping build workspace: $BUILD_DIR"
  else
    rm -rf "$BUILD_DIR"
  fi
}
trap cleanup EXIT

mkdir -p "$DIST_DIR" "$RUNTIME_CONTEXT"

echo "==> Cloning Camoufox build system"
git clone "$CAMOUFOX_REPO" "$SOURCE_DIR"
git -C "$SOURCE_DIR" checkout "$CAMOUFOX_REF"

SOURCE_COMMIT_VALUE="$(git -C "$SOURCE_DIR" rev-parse HEAD)"
SOURCE_COMMIT_SHORT="$(git -C "$SOURCE_DIR" rev-parse --short HEAD)"

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
BUILDER_IMAGE="firefox-image-builder-source:${SOURCE_COMMIT_SHORT}-${BUILD_ID}"

echo
echo "Build plan"
echo "  Camoufox repo:       $CAMOUFOX_REPO"
echo "  Camoufox ref:        $CAMOUFOX_REF"
echo "  source commit:       $SOURCE_COMMIT_VALUE"
echo "  Firefox version:     $FIREFOX_VERSION"
echo "  Camoufox release:    $FIREFOX_BUILD"
echo "  target:              $TARGET_OS/$TARGET_ARCH"
echo "  output image:        $IMAGE_TAG"
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

echo "==> Building Camoufox source-builder image"
docker build -t "$BUILDER_IMAGE" "$SOURCE_DIR"

echo "==> Compiling and packaging Camoufox from Firefox source"
docker run --rm \
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
docker build \
  --pull \
  --build-arg "PYTHON_BASE_IMAGE=$PYTHON_BASE_IMAGE" \
  --build-arg "FIREFOX_VERSION=$FIREFOX_VERSION" \
  --build-arg "FIREFOX_BUILD=$FIREFOX_BUILD" \
  --build-arg "CAMOUFOX_BROWSER_VERSION=$CAMOUFOX_BROWSER_VERSION" \
  --build-arg "CAMOUFOX_PRERELEASE=$CAMOUFOX_PRERELEASE" \
  --build-arg "SOURCE_COMMIT_VALUE=$SOURCE_COMMIT_VALUE" \
  -t "$IMAGE_TAG" \
  "$RUNTIME_CONTEXT"

echo "==> Verifying image metadata and executable"
docker run --rm --entrypoint /bin/sh "$IMAGE_TAG" -c \
  'test -x /opt/camoufox-custom/camoufox-bin && test -s /opt/camoufox-custom/SOURCE_COMMIT'

echo
echo "Build completed"
echo "  image:             $IMAGE_TAG"
echo "  Firefox:           $FIREFOX_VERSION"
echo "  Camoufox release:  $FIREFOX_BUILD"
echo "  source commit:     $SOURCE_COMMIT_VALUE"
echo
echo "Inspect labels:"
echo "  docker image inspect '$IMAGE_TAG' --format '{{json .Config.Labels}}'"
