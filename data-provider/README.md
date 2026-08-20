# data-provider v0.1.0

Standalone data-resolution component for automated workers. A worker requests a logical profile or task dataset; `data-provider` resolves it from configured backends and returns normalized JSON for scenario templates.

Version `0.1.0` includes a JSON-file backend and a provider interface prepared for Redis, PostgreSQL, secret stores, or external APIs. Real credentials must not be committed or baked into the image.

## Start

Copy the example data and start from the repository root:

```bash
cp data-provider/config/profiles.json.example data-provider/config/profiles.json
docker compose --profile data-provider up -d --build data-provider
```

When started with workers through the root Compose file, the internal URL is:

```text
http://data-provider:8080
```

## API

Health:

```bash
curl http://127.0.0.1:8080/api/v1/health
```

Resolve generic data by namespace and key:

```bash
curl -X POST -H 'Content-Type: application/json' \
  -d '{"namespace":"profiles","key":"user-001","identity":"test-user-001"}' \
  http://127.0.0.1:8080/api/v1/data/resolve
```

Profile convenience endpoint:

```bash
curl -X POST -H 'Content-Type: application/json' \
  -d '{"id":"user-001","identity":"test-user-001","run_id":"run-1"}' \
  http://127.0.0.1:8080/api/v1/profiles/resolve
```

The legacy `POST /api/profile` endpoint remains available for existing worker scenarios.

## Worker scenario

```json
{
  "type": "webhook",
  "url": "http://data-provider:8080/api/v1/profiles/resolve",
  "method": "POST",
  "json": {
    "id": "user-001",
    "identity": "{{input.identity}}"
  },
  "save_as": "profile"
}
```

Following actions can use values such as `{{webhook.profile.login}}`.

## Adding backends

Implement `DataProvider` in `app/providers.py`, register the provider in `app/main.py`, and preserve the resolver contract: resolve `namespace + key` to a dictionary or return `None` when the backend has no match. Backend credentials should be supplied through environment variables or mounted secrets.
