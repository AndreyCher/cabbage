# worker-android scenario syntax

The scenario envelope is identical to `worker-firefox`:

```json
{
  "name": "login",
  "version": 1,
  "actions": [
    {"type":"launch_app", "package":"com.example.app"},
    {"type":"click", "selector":"text=Sign in"},
    {"type":"type", "selector":"id=com.example.app:id/email", "text":"user@example.com"},
    {"type":"press", "key":"ENTER"},
    {"type":"screenshot", "name":"logged-in.png"}
  ]
}
```

## Portable action names

These use the same `type` names as the Firefox worker where the operation has a meaningful Android equivalent:

- `open` — open URL with Android ACTION_VIEW;
- `new_tab` — compatibility alias for opening a URL through ACTION_VIEW; Android/browser tab behavior is app-dependent;
- `go_back` — Android BACK key;
- `wait`;
- `wait_input`;
- `webhook`;
- `click`;
- `type`;
- `press`;
- `scroll`;
- `screenshot`.

## Android-specific actions

### `launch_app`

```json
{"type":"launch_app", "package":"com.android.settings"}
```

Optional exact activity:

```json
{"type":"launch_app", "package":"com.example.app", "activity":".MainActivity"}
```

### `tap`

```json
{"type":"tap", "x":540, "y":1600}
```

`click` also accepts the same coordinate form:

```json
{"type":"click", "x":540, "y":1600}
```

### `swipe`

```json
{"type":"swipe", "direction":"up", "percent":0.75}
```

Optional rectangle: `left`, `top`, `width`, `height`.

## Android selectors

The field remains named `selector`; only the selector dialect differs from DOM/CSS selectors.

```text
id=com.example:id/login
text=Sign in
text_contains=Continue
desc=Open navigation
accessibility_id=Open navigation
class=android.widget.Button
xpath=//android.widget.Button[@text='Sign in']
android=new UiSelector().resourceId("com.example:id/login")
```

Examples:

```json
{"type":"click", "selector":"text=Sign in"}
```

```json
{"type":"type", "selector":"id=com.example:id/email", "text":"test@example.com", "clear":true}
```

## Keys

`press` currently supports common Android keys: `BACK`, `HOME`, `MENU`, `ENTER`, `TAB`, `ESCAPE`, `SPACE`, DPAD directions, `DELETE`, and digits.

```json
{"type":"press", "key":"BACK"}
```

## Runtime templates

Same syntax as Firefox worker:

```json
{"type":"type", "selector":"id=com.example:id/otp", "text":"{{input.otp.code}}"}
```

Webhook values also use the same namespace:

```json
{"type":"type", "selector":"id=com.example:id/name", "text":"{{webhook.profile.name}}"}
```
## Telephony-enabled scenarios (v0.1.1)

`launch_app` installs the configured telephony fixture before starting packages
listed in `telephony.packages`. This restarts the target application's main
process. Other packages retain normal launch behavior.

With a phone provider enabled, `wait_input` for `phone` reads the allocation and
`wait_input` for `sms` receives the normalized verification code. Use
`{{input.phone.number}}` and `{{input.sms.verification_code}}` in subsequent
actions. Polling and webhook-only delivery share this syntax. See
[TELEPHONY.md](TELEPHONY.md) for configuration, provider protocol and limitations.
