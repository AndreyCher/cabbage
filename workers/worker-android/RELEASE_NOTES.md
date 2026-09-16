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
