# worker-android v0.1.2

`worker-android` is the Android execution sibling of `worker-firefox`.
The first release is intentionally autonomous: Controller and Web Console changes are not required.

## Contract parity

The worker keeps the same outer contract as `worker-firefox`:

- `WORKER_SYSTEM_CONFIG` + `WORKER_PROFILE` configuration ownership;
- global/local defaults and local-first scenario lookup;
- `artifacts/<identity>/<scenario>/<run-id>/` layout;
- `summary.json`, `runtime-events.json`, `run.log`, screenshots and session recording;
- Control API on port 8090:
  - `GET /api/v1/health`
  - `GET /api/v1/identities/<identity>/runs/current`
  - `GET /api/v1/identities/<identity>/runs/<run-id>`
  - `POST /api/v1/identities/<identity>/runs/<run-id>/inputs/<key>`
  - identity config GET/PATCH;
- scenario runtime templates such as `{{input.key.value}}` and `{{webhook.result.field}}`;
- standalone and debug/noVNC execution.

The execution backend is Android Emulator + Appium UiAutomator2 instead of Camoufox + Playwright.

## Telephony QA and cloud SMS

v0.1.2 includes opt-in `telephony` fixtures for explicitly configured QA applications
and a replaceable `phone_number_provider` (`mock`, normalized `http` bridge, or
JuicySMS v2). Phone allocations are run-scoped rather than bound to a persistent
Android Identity; an unavailable optional provider produces a warning and the
worker continues without a connected phone.
The fixture supplies IMEI, IMSI, phone number, operator and MCC/MNC/country through
Android Java APIs in the main process of apps started by `launch_app`. It requires
an adb-root-capable x86_64 emulator and does not change the whole OS/modem or
provide real calls/SMS.

Cloud allocation is available as `{{input.phone.number}}`; SMS polling or a
trusted webhook bridge supplies `{{input.sms.verification_code}}` through
`wait_input`. Credentials use injected environment/secret files; allocations
are released at run completion by default. The HTTP adapter defines a normalized
gateway contract, and the JuicySMS adapter uses its v2 one-time-order API with a
read-only `WORKER_JUICY_SMS_TOKEN_FILE`; no secret is part of a profile JSON.

See [TELEPHONY.md](TELEPHONY.md) for every setting, API contract, examples,
permissions, process-scope limitations and test commands.

## Host requirements

Linux x86_64 host with hardware virtualization and `/dev/kvm` available to Docker.

Check:

```bash
ls -l /dev/kvm
grep -Eoc '(vmx|svm)' /proc/cpuinfo
```

## Build

```bash
cd workers/worker-android
docker compose build worker-android
```

Default base image is pinned to:

```text
budtmo/docker-android:emulator_14.0_v3.7.0-p0
```

Override if needed:

```bash
WORKER_ANDROID_BASE_IMAGE=budtmo/docker-android:emulator_13.0_v3.7.0-p0 \
  docker compose build worker-android
```

## Autonomous smoke test

```bash
docker compose up worker-android
```

In another terminal:

```bash
curl -s http://127.0.0.1:8091/api/v1/health | jq
curl -s http://127.0.0.1:8091/api/v1/identities/android-test-001/runs/current | jq
```

After completion:

```bash
find artifacts/android-test-001/android-example -maxdepth 3 -type f -print
cat artifacts/android-test-001/android-example/*/summary.json | jq
```

## Debug / manual mode

Debug exposes Android through noVNC and keeps the worker alive after scenario completion:

```bash
docker compose --profile debug up worker-android-debug
```

Open:

```text
http://<docker-host>:6081/?autoconnect=true
```

Control API remains:

```text
http://<docker-host>:8091
```

Stop with Ctrl+C or `docker compose down`; shutdown is finalized into the run summary.

## Select another emulated device

One-off launch:

```bash
EMULATOR_DEVICE='Pixel 7' docker compose up worker-android
```

Persistent worker profile:

```json
{
  "identity": "android-pixel",
  "run": {"scenario": "android-example"},
  "android": {
    "emulator_device": "Pixel 7"
  }
}
```

`EMULATOR_DEVICE` environment variable has priority over profile configuration.
The selected device name must be supported by the underlying Docker-Android image.

## Proxy

The worker understands the same top-level proxy object used by the Firefox worker:

```json
{
  "proxy": {
    "enabled": true,
    "server": "http://proxy.example.com:10000",
    "username": "proxy-user",
    "password": "proxy-password"
  }
}
```

Before Android starts, this is translated into the emulator `-http-proxy` argument. This means apps using the Android system networking stack start behind the configured emulator proxy.

Example:

```bash
WORKER_PROFILE=android-proxy-example docker compose up worker-android
```

## Runtime input test

Create a scenario containing:

```json
{
  "type": "wait_input",
  "key": "code",
  "timeout_sec": 600,
  "on_timeout": "fail"
}
```

While it is waiting:

```bash
RUN_ID=$(curl -s http://127.0.0.1:8091/api/v1/identities/android-test-001/runs/current | jq -r .run_id)

curl -sS -X POST \
  -H 'Content-Type: application/json' \
  -d '{"value":"123456"}' \
  "http://127.0.0.1:8091/api/v1/identities/android-test-001/runs/${RUN_ID}/inputs/code" | jq
```

A following action can use:

```json
{"type":"type", "selector":"id=com.example:id/code", "text":"{{input.code.value}}"}
```

## Current v0.1 boundary

This release implements worker/container behavior only. It does **not** add Android worker selection to Controller or Web Console.

Video recording is implemented with Android `screenrecord`. A semantic recorder that converts arbitrary manual noVNC taps/typing into scenario JSON is a separate feature; it is not silently approximated in v0.1.

## Development handoff

Implementation status, validated behavior, known issues and the planned Android identity / cloud phone-number work are documented in [`CODEX_HANDOFF.md`](CODEX_HANDOFF.md).
