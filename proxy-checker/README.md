# proxy-checker 0.1.2

Autonomous asynchronous proxy health and exit-location verifier. It reads proxy endpoints and jobs directly from PostgreSQL, routes every provider request through the tested proxy, stores immutable attempt history, and updates only technical health/GEO fields.

Configuration has two levels: local `config.json` provides standalone/bootstrap defaults; the `proxy_checker` record in `controller_settings`, managed through Controller/Web Console, overrides runtime values without restart.

Built-in free providers are `ipwhois`, `freeipapi`, and `ipapi_co`. Future paid adapters use `provider_config` and mounted secret files. Manual jobs have priority 100, create/update jobs 50, and scheduled jobs 0. An active check is never interrupted.

Only `healthy` proxies are eligible for Identity country pools. A healthy result must include exit IP, country and timezone so a new Identity can materialize a complete location. Healthy and pending endpoints use the configurable monitoring interval (default 300 seconds). Repeated failures transition an endpoint to `unhealthy`; that state is terminal for automatic scheduling until a successful manual Verify restores `healthy`.

Attempt history distinguishes reaching a GEO provider from failing to connect to the proxy itself. Quota counters include only the former. Transport failures preserve their exception type and details in endpoint state, job history and logs.

On restart, interrupted manual/create/update checks are returned to the durable queue. Interrupted scheduled checks for endpoints already marked unhealthy are finalized without reactivating automatic monitoring.

```bash
docker compose --profile controller up -d --build proxy-checker
```

Internal endpoints: `GET /api/v1/health` and `GET /api/v1/status`.
