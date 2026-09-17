# worker-android 0.1.7

Adds two optional Appium capabilities, `android.adb_exec_timeout_ms` and
`android.uiautomator2_server_install_timeout_ms` (default 120000 ms each), so a
slow cold UiAutomator2 install/ADB path can be tuned per profile instead of
requiring a code change. Existing profiles are unaffected: both keys keep their
previous implicit defaults. This finishes releasing a shared `app/android.py`
change that `worker-google-android` 0.1.1 already depended on for its slower
official-emulator cold start.

# worker-android 0.1.6

Compose debug runs now always enable safe provider diagnostics, independently
of the selected profile's `debug.keep_alive` value.

# worker-android 0.1.5

Adds safe JuicySMS diagnostics: Debug logs show lifecycle request/status/error
codes without credentials, phone numbers or SMS contents. Normal startup logs
the stable reason instead of only saying that no phone is connected.

# worker-android 0.1.4

Corrects JuicySMS country validation to match the live v2 OpenAPI contract:
one-time orders can use only `USA`, `UK`, `NL` or `PH`. The shipped sample now
uses `NL`; `DE` is rejected before a paid-order request is sent.

# worker-android 0.1.3

Standalone JuicySMS configuration is now one private profile field:
`phone_number_provider.token`. Copy the example to a profile ending in
`.local.json`; that pattern is ignored by Git. The token-file variable remains
available for a future Controller-managed secret store.

# worker-android 0.1.2

Adds a direct JuicySMS v2 adapter for run-scoped QA numbers and SMS polling.
Configure `provider: "juicysms"`, `country`, `service_id` and optionally
`max_price`; mount its bearer token as a read-only file and set
`WORKER_JUICY_SMS_TOKEN_FILE`. No provider credential is stored in an Identity,
profile or scenario JSON.

Cloud numbers are intentionally not persistent Android-Identity fields. Every
new container allocates independently. With the default `required: false`, an
unavailable/disabled provider logs a warning and lets Android start without a
line number; a scenario can still explicitly fail by waiting for unavailable
phone/SMS input. Use `required: true` for fail-fast allocation.

Verification: 26 automated unit, HTTP-contract and API tests passed on
2026-09-16. No JuicySMS account, credential or paid order was used.

See [TELEPHONY.md](TELEPHONY.md) and
`config/profiles/android-juicysms-example.json` for the exact configuration.

# worker-android 0.1.1

Adds application-scoped telephony QA and the cloud phone-number adapter contract.
See [TELEPHONY.md](TELEPHONY.md) for setup and limitations.

Telephony is opt-in and applies to configured apps launched with `launch_app`.
It uses Android Java API fixtures rather than modifying the emulator's modem.
The HTTP provider requires a compatible gateway; the mock provider is for QA.
No paid allocation was made during verification.

Verification includes unit/HTTP/API tests, Docker build, a real Android application
reading all fixture fields, and the complete mock-number/SMS scenario.

Final verification: 23 automated tests; clean-container run
`f93726b2-acfb-4f8d-9695-f6f0f617eaeb` on 2026-09-16 passed all four actions,
actual Android API-value assertions, screenshot and MP4 checks.
Startup prepares adb-root before Appium and starts Frida after Appium readiness.
