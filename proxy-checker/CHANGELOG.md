# Proxy Checker changelog

## 0.1.1

- Required provider responses to include timezone before a proxy can become healthy.

## 0.1.0

- Added autonomous PostgreSQL-backed verification jobs and immutable provider-attempt history.
- Added periodic, create/update and high-priority manual checks without interrupting active checks.
- Added three free provider adapters with retries, fallback and mismatch confirmation.
- Added local JSON defaults with database overrides, stale handling, failure thresholds and concurrency controls.
- Added a paid-provider placeholder using mounted secret files.
