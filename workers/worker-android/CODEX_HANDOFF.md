# worker-android — Codex handoff

This document is the implementation handoff for the standalone Android worker. It is intentionally scoped to `workers/worker-android`; do not modify Controller or WebUI unless explicitly requested later.

## Update — 0.1.2 (2026-09-16)

JuicySMS v2 is now a direct `PhoneNumberProvider` (`provider: "juicysms"`) for
one-time numbers. It allocates one order per worker run, polls its messages and
cancels on graceful cleanup. The only credential path is the mounted
`WORKER_JUICY_SMS_TOKEN_FILE`; never place a bearer token in JSON, artifacts or
Identity state. JuicySMS's webhook routes currently return `403
feature_unavailable`, so use polling for this provider. No paid/live order was
created during tests.

Phone allocation is deliberately non-persistent: worker restarts never reclaim
or demand the previous number. `phone_number_provider.required` is false by
default; missing/unavailable allocation logs a warning, continues Android
startup and exposes `null` for an app-scoped cloud line number. A scenario that
needs phone/SMS still has to wait for it, and `required: true` remains the
explicit fail-fast option. Controller/WebUI Android integration is still deferred.

## Update — 0.1.1 (2026-09-16)

The user approved **application-scoped QA API fixtures** for explicitly configured
packages. `telephony.backend=app_api` uses pinned Frida 16.7.19 on the adb-root
x86_64 emulator; `launch_app` installs Java API fixtures before app startup.
It does not modify the whole Android modem/OS identity. Main-process coverage and
limitations are documented in `TELEPHONY.md` (required reading for this domain).
IMEI/IMSI can be fixed or deterministically generated; operator MCC/MNC and phone
fields are validated. New telephony/provider domains merge Identity config before
launch-profile overrides. MEID/device system-property placeholders remain deferred.

The replaceable `PhoneNumberProvider` contract is implemented with `mock` and
normalized `http` bridge backends. One allocation and one SMS per run are exposed
through existing runtime inputs. Polling/webhook delivery, allocation validation,
idempotency key, request limits, secret-file credentials and graceful release
are implemented. A concrete commercial provider/gateway deployment and crash
reconciliation remain future work. Controller/WebUI Android integration remains
deferred. Native Android SMS injection is not part of the provider flow.

Unit, HTTP/API contract tests and a QA APK that calls real Android APIs now exist.
The application smoke test passed all configured fields; full scenario run
`b424d3ad-6cc5-4607-a36f-4bbff076ec9a` passed all four steps with mock SMS,
screenshot and video. Fatal errors/shutdown now propagate in debug mode.

The sections below describe the original v0.1.0 baseline and original roadmap;
the update above and TELEPHONY.md supersede telephony/provider placeholder claims.

Final clean-container verification on 2026-09-16: run
`f93726b2-acfb-4f8d-9695-f6f0f617eaeb` passed all four actions, mock SMS, screenshot
and MP4 checks. The QA APK's persisted output matched every configured Android
telephony API field. All 23 unit/HTTP/API tests pass. Startup order matters:
prepare adb-root -> establish Appium session -> start Frida -> launch app with
fixture. Frida before cold Appium setup produced Appium Settings readiness
failures. Repeated Frida-server cycles in a guest also exposed system-service
readiness failures; retain the fresh disposable container requirement.

## Goal

`worker-android` must remain a sibling of `worker-firefox` with the same outer worker contract wherever possible, so Controller can eventually select either worker type without having two unrelated execution models.

Target invariants:

- one run = one disposable worker container;
- worker can also run completely standalone without Controller;
- same config ownership pattern (`WORKER_SYSTEM_CONFIG`, `WORKER_PROFILE`);
- same scenario envelope and portable action names where an Android equivalent exists;
- same runtime-input mechanism and template syntax;
- same Control API shape and artifact layout;
- Android-specific behavior stays behind the Android execution backend.

## Current implementation (v0.1.0)

### Runtime stack

- Docker image: `budtmo/docker-android:emulator_14.0_v3.7.0-p0`.
- Android Emulator runs with KVM acceleration (`/dev/kvm`).
- Appium 3 + UiAutomator2 is the primary automation backend.
- ADB is used for boot readiness, URL opening, app launch helpers and device inspection.
- noVNC debug UI is exposed by the base image.

Validated on a Proxmox VM with nested AMD-V/KVM enabled. The tested chain is:

`Proxmox -> development VM -> /dev/kvm -> Docker -> Android Emulator`.

### Control API

Implemented on worker port 8090 (compose maps debug instance to host 8091):

- `GET /api/v1/health`
- `GET /api/v1/identities/<identity>/runs`
- `GET /api/v1/identities/<identity>/runs/current`
- `GET /api/v1/identities/<identity>/runs/<run-id>`
- `POST /api/v1/identities/<identity>/runs/<run-id>/inputs/<key>`
- identity config GET/PATCH endpoints

Validated health response:

```json
{
  "status": "ok",
  "api_version": "v1",
  "project": "cabbage",
  "component": "worker-android",
  "worker_type": "android"
}
```

### Scenario engine

Portable actions currently implemented:

- `open`
- `new_tab`
- `go_back`
- `wait`
- `wait_input`
- `webhook`
- `click`
- `type`
- `press`
- `scroll`
- `screenshot`

Android-specific actions:

- `launch_app`
- `tap`
- `swipe`

Supported selector dialect in the common `selector` field:

- `id=...`
- `text=...`
- `text_contains=...`
- `desc=...`
- `accessibility_id=...`
- `class=...`
- `xpath=...`
- `android=new UiSelector()...`

Runtime templates use the same shape as the Firefox worker, including `{{input.*}}` and `{{webhook.*}}`.

### Verified real run

A real Android 14 emulator run has completed successfully with:

1. `open https://example.com`
2. wait
3. screenshot
4. Android BACK key
5. wait
6. screenshot

Observed result:

- all six actions passed;
- Android reported `sys.boot_completed=1`, `dev.bootcomplete=1`, `init.svc.bootanim=stopped`, `device_provisioned=1`;
- ADB device: `emulator-5554`;
- Android version: 14;
- screenshots were written under the normal run artifact directory;
- debug `keep_alive` kept the worker available after scenario completion.

### Device profile selection

`EMULATOR_DEVICE` and `android.emulator_device` are supported for the Docker-Android device/skin selection.

Important: this currently changes emulator characteristics/skin, but the guest OS still reports its generic emulator identity (for example `sdk_gphone64_x86_64`). It does NOT yet make Android system properties/API-visible identity match a real Samsung/Pixel device.

### Proxy

The shared top-level `proxy` block is translated at container startup into Android Emulator `-http-proxy` arguments.

Current proxy support is for emulator/system network routing only. Do not assume it changes telephony identity.

### Artifacts

Run artifacts are written under:

`artifacts/<identity>/<scenario>/<run-id>/`

Current observed files include:

- `run.log`
- `device.json`
- `screenshots/*`

Video uses Android `screenrecord` in the worker implementation.

## Known issues discovered during real testing

### 1. `summary.json` is delayed in debug keep-alive mode

Current flow marks the run `completed`, then enters the `debug.keep_alive` loop. Final summary writing occurs later in cleanup/finalization, so `summary.json` is not immediately available while the debug container stays alive.

Required behavior:

- finalize run result immediately after scenario execution;
- write `summary.json` and `runtime-events.json` before entering debug keep-alive;
- container may remain alive afterward, but run result must already be final and queryable.

### 2. Bind-mount ownership

The worker process runs as UID 1300 / GID 1301 and initially failed to create `/artifacts/...` when host directories were owned by root.

Current manual workaround used during testing:

```bash
chown -R 1300:1301 artifacts identities
```

Fix this in worker startup/image/compose without using `chmod 777`. The solution must preserve sane permissions for standalone and future Controller-created containers.

### 3. Reusing the same Android container is unreliable

A second `docker compose up` against the same existing debug container caused the base image `device` supervisor process to fail. A clean disposable container fixed it:

```bash
docker compose --profile debug down --remove-orphans
docker compose --profile debug up --force-recreate worker-android-debug
```

This reinforces the architectural rule: a run should use a fresh disposable Android worker container. Do not design persistent emulator-container state into the normal run path.

### 4. `log_web_shared` supervisor process

The Docker-Android base image repeatedly reports `log_web_shared` exiting and eventually FATAL. This did not block Android, Appium, VNC or scenario execution in the tested run. Treat it as non-fatal unless later evidence shows otherwise.

### 5. Selector operations currently have no explicit wait

`click` and `type` call `find_element()` immediately. This is brittle for asynchronous Android UI.

Future implementation should provide explicit locator waits and controlled failure reasons, analogous to the browser worker direction:

- locator timeout;
- element not found;
- element not visible/enabled;
- click timeout;
- typing timeout.

Keep action index/type/selector in diagnostics.

## Next implementation steps

Recommended order:

1. Fix run finalization so `summary.json` and runtime events are written before debug keep-alive.
2. Fix bind-mount ownership/permissions automatically.
3. Add explicit selector waits/timeouts to `click`, `type`, and future visibility actions.
4. Complete and validate Android UI scenario: `launch_app(Settings) -> selector click -> scroll/swipe -> BACK -> screenshots`.
5. Add robust action failure reasons and diagnostics consistent with `worker-firefox` philosophy.
6. Add semantic recording/debug capture inside `worker-android` so manual Android interaction can be converted into scenario actions. Do not implement this as raw coordinate-only recording if UI hierarchy can identify the target element.
7. Add a real Android device identity layer (system/API-visible model/manufacturer/brand/product/device) separately from Docker-Android skin selection.
8. Add telephony identity support and a cloud phone-number provider adapter as described below.

## Future device / telephony identity model

The sample identity at `identities/android-test-001/config.json` now reserves the configuration structure for this work. These fields are configuration placeholders only; v0.1.0 does not yet apply them to Android.

Reserved fields include:

```json
{
  "device": {
    "profile": "Samsung Galaxy S10",
    "android_version": "14.0",
    "manufacturer": "Samsung",
    "brand": "samsung",
    "model": "SM-G973F",
    "product": "beyond1lte",
    "device": "beyond1"
  },
  "telephony": {
    "enabled": false,
    "mode": "emulated",
    "imei": {"mode": "generated", "value": null},
    "meid": {"mode": "generated", "value": null},
    "imsi": {"mode": "generated", "value": null},
    "operator": {
      "name": null,
      "mcc": null,
      "mnc": null,
      "country_iso": null
    },
    "phone_number": {
      "source": "cloud_provider",
      "value": null
    }
  }
}
```

Design requirement: values presented to apps should be internally coherent. Do not treat IP/proxy, IMEI, IMSI and MSISDN as the same identity source; they are separate layers that may need coordination.

## Future cloud phone-number provider

The user wants the real phone number/SMS side to come from a cloud provider, while telephony device identity can be emulated.

Do not hard-code one provider into the scenario engine. Introduce an adapter interface, conceptually:

```text
PhoneNumberProvider.allocate()
PhoneNumberProvider.get_status()
PhoneNumberProvider.wait_message()
PhoneNumberProvider.release()
```

Suggested normalized allocation result:

```json
{
  "allocation_id": "...",
  "number": "+...",
  "country": "...",
  "operator": "...",
  "mcc": "...",
  "mnc": "..."
}
```

The worker/scenario should consume normalized values, not provider-specific response fields.

Intended flow:

1. allocate a number for the run;
2. make the normalized number available to the scenario/runtime input namespace;
3. application requests SMS;
4. provider adapter receives/polls message;
5. normalize verification code/message into runtime input data;
6. scenario continues using existing template syntax (for example `{{input.sms.verification_code}}`);
7. release the number at run end when configured.

The provider layer must support future replacement without changes to the scenario syntax.

Keep cloud-provider credentials out of identity JSON and artifacts. Use environment/secrets injection and redact secrets from logs.

## Out of scope for now

Do not add in the current phase unless explicitly requested:

- Controller worker selection logic;
- Controller DockerExecutor changes;
- WebUI changes;
- Kubernetes executor support;
- persistent Android emulator containers as the normal execution model.

The immediate scope remains the autonomous `worker-android` container and its worker contract.
