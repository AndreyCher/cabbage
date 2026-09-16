# Telephony QA and cloud phone numbers

These are two independent, opt-in capabilities. Both work standalone. The
Controller/Web Console Android-worker integration remains a separate task.

## Application-scoped telephony fixture

Configure `telephony` in a launch profile or Identity `config.json`. Only these
new domains use precedence: shared defaults -> local defaults -> Identity
telephony/provider config -> launch profile. Other existing domains retain their
previous resolver behavior.

```json
{
  "telephony": {
    "enabled": true,
    "mode": "emulated",
    "backend": "app_api",
    "packages": ["com.example.qa"],
    "imei": {"mode": "generated"},
    "imsi": {"mode": "generated"},
    "operator": {"name": "QA Germany", "mcc": "262", "mnc": "01", "country_iso": "de"},
    "phone_number": "+4915112345678"
  }
}
```

IMEI/IMSI also accept explicit strings or `{"mode":"fixed","value":"..."}`.
Generated identifiers are deterministic per Identity name, use a synthetic
IMEI prefix, and are QA fixtures, not issued equipment/SIM credentials. IMEI
requires 15 digits with a valid check digit. IMSI requires 15 digits beginning
with the supplied MCC/MNC. MCC/MNC must be strings to preserve leading zeroes.
Operator name and two-letter `country_iso` are explicit; no remote lookup occurs.
The operator/country relationship is caller-supplied rather than registry-verified.

The bundled, version/checksum-pinned Frida runtime requires `adb root` on the
Android x86_64 QA emulator. It binds only to guest loopback, with an internal ADB
forward. No Frida host port is published by Compose. With telephony disabled it
does not start and ADB privileges are unchanged.
Startup prepares adb-root first, initializes the Appium session, then starts
telephony instrumentation. This avoids restarting ADB after Appium creates its
port forwards and keeps instrumentation out of Appium's initial app setup.

Use `launch_app` to start each configured package. The worker force-stops its
previous process, spawns it suspended, installs the fixture, then resumes it.
Fixtures apply before `Application.onCreate`. The test APK must already be
installed. Repeated `launch_app` starts a new app process. Launch through an
external intent/noVNC or automatic restart does not install the fixture.

Overridden Java APIs:

- `TelephonyManager.getImei`, `getDeviceId`, `getSubscriberId`, `getLine1Number`;
- `getNetworkOperatorName`, `getSimOperatorName`;
- `getNetworkOperator`, `getSimOperator` (MCC + MNC);
- `getNetworkCountryIso`, `getSimCountryIso`;
- `SubscriptionManager.getPhoneNumber`.

The fixture covers available overloads in the application's main process.
Secondary app processes, direct Binder/native access, `SubscriptionInfo`, MEID,
SIM registration and system settings are not overridden. QA hooks return the
fixture directly, including when the normal API would require phone permissions;
disable them when testing permission denial. They do not create a SIM, change
the modem/OS identity or provide real calls/SMS. Android proxy/IP remains separate.
App termination, detach and worker cleanup remove the runtime fixture.
Use a fresh emulator container per run. Repeated Frida-server start/stop cycles
in the same Android guest have caused temporary Android system-service failures;
they are not
the normal disposable-worker lifecycle. Runtime startup retries temporary service
readiness failures for up to 20 seconds.

## Phone-number provider

```json
{
  "phone_number_provider": {
    "enabled": true,
    "provider": "http",
    "required": false,
    "country": "NL",
    "service": "your-qa-service",
    "allocation_timeout_sec": 60,
    "request_timeout_sec": 10,
    "poll_interval_sec": 5,
    "delivery_mode": "polling",
    "message_timeout_sec": 180,
    "number_input_key": "phone",
    "input_key": "sms",
    "release_on_finish": true
  }
}
```

Inject `WORKER_PHONE_PROVIDER_URL` and optionally
`WORKER_PHONE_PROVIDER_TOKEN_FILE` into the container. Mount the token file
read-only via a private Compose override/Docker secret. Credentials never belong
in Identity/scenario JSON. HTTPS is required; HTTP is allowed only for loopback
test servers. Redirects are rejected. Responses are limited to 64 KiB. Errors
exclude response bodies, URLs and token contents.

`required` defaults to `false`. A provider that is disabled, unconfigured or
temporarily unavailable never blocks Android startup in that mode: the worker
records a warning and the telephony fixture returns no line number (`null`) to
the configured QA app. A scenario which actually waits for `phone`/`sms` will
naturally time out. Set `required: true` only when a scenario must fail before
automation without an allocated number. Numbers are per-run allocations; a
restarted container never attempts to reclaim its previous number.

`provider: "http"` is a normalized bridge API, not an adapter for an arbitrarily
shaped vendor API. Implement the contract below in a provider-specific gateway
or add a `PhoneNumberProvider` implementation. No commercial provider has been
selected or charged as part of implementation/testing.

### HTTP bridge contract

| Request | Response |
| --- | --- |
| `POST /allocations` with `{country, service}` and `Idempotency-Key: <run-id>` | `{allocation_id, number, country?, operator?, mcc?, mnc?}` |
| `GET /allocations/<id>` | Provider allocation status |
| `GET /allocations/<id>/message` | `204`/JSON `null` while waiting, otherwise `{allocation_id, verification_code?, text?}` |
| `DELETE /allocations/<id>` | Successful 2xx; release must be idempotent |

IDs contain only letters, digits, `_`, `-` (1–128 characters). Numbers use E.164.
SMS allocation IDs must match the run's allocation. Explicit verification codes
are strings, preserving leading zeroes. If absent, the first isolated 4–8 digit
sequence in `text` is used. Provider-specific extraction belongs in the gateway.

Allocation occurs once after Android boot and before scenario execution. There
are no automatic allocation retries: a network timeout may mean the provider
allocated a number but its response was lost. Gateways must reconcile by the run
idempotency key. Worker/container crashes likewise require provider TTL or
external reconciliation; graceful cleanup alone cannot guarantee release.

The allocation is published as `{{input.phone.number}}` (and other normalized
allocation fields). Set `telephony.phone_number.source: "cloud_provider"` to
expose this same number through the configured application's telephony APIs.
Cloud allocation does not determine IMEI/IMSI or operator identity; configure
those separately for the QA case.

Polling starts when the scenario reaches `wait_input` for `sms`, and uses the
smaller of the action and provider message timeouts. Successful delivery is
available as `{{input.sms.verification_code}}` and `{{input.sms.text}}`. This
first version supports one phone allocation and one SMS input per run.

```json
{"type":"wait_input","key":"sms","timeout_sec":180,"on_timeout":"fail"}
```

The normal `on_timeout: "default"` behavior remains supported. Provider transport
or protocol errors are fatal even in debug mode. Shutdown cancels polling;
an in-flight HTTP request can take up to `request_timeout_sec` to unwind.

A trusted webhook bridge may instead POST normalized input through the existing
run-scoped `/api/v1/identities/<identity>/runs/<run-id>/inputs/sms` endpoint.
Use `delivery_mode: "webhook"` to disable polling and wait only for API input;
the `wait_input` action controls that wait's timeout. Payloads must include the
matching `allocation_id` and `verification_code` or `text`; invalid/mismatched
payloads receive HTTP 400 without occupying the input slot.
API-delivered input takes priority over polling. The bridge must validate the
vendor webhook signature, correlate its allocation to the exact run and enforce
authentication before forwarding. The worker API is an internal API, not a public
vendor webhook receiver. Android routing through Controller is not added here.

The worker releases allocations on completion/failure/graceful stop when
`release_on_finish` is true, including before debug keep-alive. Cleanup failures
are recorded without leaking credentials. Phone numbers and SMS bodies are not
included in provider lifecycle logs/summary; downstream actions/screenshots may
still expose data they intentionally use.

### JuicySMS

`provider: "juicysms"` is a direct adapter for the documented JuicySMS v2
one-time order API. It polls order messages because JuicySMS does not currently
offer webhook delivery. Use a least-privilege, account-scoped token with the
`services:read`, `orders:read` and `orders:write` scopes:

```json
{
  "phone_number_provider": {
    "enabled": true,
    "provider": "juicysms",
    "token": "your-private-juicysms-token",
    "required": false,
    "country": "NL",
    "service_id": 1,
    "max_price": 0.50,
    "poll_interval_sec": 5,
    "message_timeout_sec": 180,
    "release_on_finish": true
  }
}
```

For the standalone worker, put the token directly in a private launch profile,
for example `config/profiles/android-juicysms.local.json`. Files matching
`*.local.json` are ignored by Git. `WORKER_JUICY_SMS_TOKEN_FILE` remains a
supported alternative for Controller/future secret materialization. The worker
sends `POST /orders`, polls `GET /orders/<id>/messages`, and requests
`POST /orders/<id>/cancel` during graceful cleanup. At the current API version,
JuicySMS supports one-time orders only for `USA`, `UK`, `NL` and `PH`; the worker
rejects any other country before an order request. `service_id` must come from
JuicySMS's `/services` catalogue and `max_price` is optional. The direct adapter
never logs the token, number, SMS body, response body or provider URL. See
`config/profiles/android-juicysms-example.json` for a non-secret profile.

In a debug profile (`debug.keep_alive: true`), the worker additionally logs the
JuicySMS request method/path, safe order payload fields, HTTP status and stable
provider error code. It never logs bearer tokens, phone numbers, SMS text or
verification codes. Normal runs log the same stable reason in the startup
warning, for example `JuicySMS request failed: price_above_maximum`.

## Mock and tests

`provider: "mock"` needs no credentials/network and does not acquire a real
number. Optional fixture settings are `mock_number` (default `+15555550100`),
`mock_code` (default `123456`) and `mock_delay_sec` (default `1`).

`config/profiles/android-telephony-qa.json` and `android-phone-example` demonstrate
both features together. They require the fixture APK in `tests/qa-app` to be
built and installed into that disposable emulator first; it is not a production
image application. `tests/qa-app/build.sh` uses the SDK bundled in the base image.

Run unit/HTTP contract tests from the repository root:

```bash
PYTHONPATH=workers/worker-android python3 -m unittest discover -s workers/worker-android/tests -v
```

For the Android API smoke test, copy `tests` into an emulator container, run
`bash /tmp/tests/qa-app/build.sh`, then run
`PYTHONPATH=/opt/worker-android python3 /tmp/tests/android_telephony_smoke.py`.
The application calls real Android Java APIs and the test compares its output
against all configured fixture fields.
