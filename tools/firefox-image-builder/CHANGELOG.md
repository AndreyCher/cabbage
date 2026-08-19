# Changelog

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
