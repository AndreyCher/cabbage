# Webhook mock service

Test-only FastAPI service for the worker webhook action.

1. Copy `config/profiles.json.example` to `config/profiles.json`.
2. Edit test values locally; do not commit real credentials.
3. Start with `docker compose --profile webhook-mock up -d webhook-mock`.
4. From Camoufox use `http://webhook-mock:8080/api/profile`.

Request: `POST /api/profile` with JSON `{ "id": "user-001" }`.
