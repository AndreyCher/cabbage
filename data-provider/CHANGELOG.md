# Changelog — data-provider

## 0.1.0

- Promoted the former worker-local webhook mock into an independently versioned top-level component.
- Added a generic `namespace + key` provider/resolver interface for future Redis, PostgreSQL, secret-store, and external API adapters.
- Added the JSON-file provider as the initial backend.
- Added versioned health and profile-resolution endpoints.
- Added generic `POST /api/v1/data/resolve` lookup.
- Preserved `/health` and `POST /api/profile` compatibility endpoints.
- Added Docker image, root Compose integration, example configuration, and API tests.
