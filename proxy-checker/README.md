# proxy-checker 0.1.1

Autonomous asynchronous proxy health and exit-location verifier. It reads proxy endpoints and jobs directly from PostgreSQL, routes every provider request through the tested proxy, stores immutable attempt history, and updates only technical health/GEO fields.

Configuration has two levels: local `config.json` provides standalone/bootstrap defaults; the `proxy_checker` record in `controller_settings`, managed through Controller/Web Console, overrides runtime values without restart.

Built-in free providers are `ipwhois`, `freeipapi`, and `ipapi_co`. Future paid adapters use `provider_config` and mounted secret files. Manual jobs have priority 100, create/update jobs 50, and scheduled jobs 0. An active check is never interrupted.

Only `healthy` proxies are eligible for Identity country pools. A healthy result must include exit IP, country and timezone so a new Identity can materialize a complete location. Results become unavailable when stale; repeated failures transition endpoints to `unhealthy`.

```bash
docker compose --profile controller up -d --build proxy-checker
```

Internal endpoints: `GET /api/v1/health` and `GET /api/v1/status`.
