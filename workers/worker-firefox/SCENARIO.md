# Scenario Guide — v0.5.15

> Component files live in `workers/worker-firefox/`. Run Docker Compose commands from the repository root; file paths in this document are relative to the component directory unless stated otherwise.

This file is the practical reference for writing scenario `actions`. Every currently registered action has a purpose, parameter summary, and copy-ready JSON example. `CONFIG.md` remains the broader configuration reference; `API.md` documents runtime input delivery; `PLUGINS.md` documents adapters.

## Scenario file shape — v0.5.19

Shared scenarios are stored under `workers/config/scenarios/`. A worker may provide a same-named file under its local `config/scenarios/`; when present, that file replaces the shared scenario completely. Scenario contents and `actions` arrays are not merged.

Example worker-local `workers/worker-firefox/config/scenarios/example.json`:

```json
{
  "name": "example",
  "version": 1,
  "actions": [
    {"type": "open", "url": "https://example.com"},
    {"type": "wait", "min": 1, "max": 2},
    {"type": "screenshot", "name": "example.png"}
  ]
}
```

A launch profile selects it with:

```json
{
  "run": {
    "scenario": "example"
  }
}
```

The same scenario file can therefore be reused by any number of profiles without copying its actions into profile configuration.

Current action types: `open`, `new_tab`, `switch_tab`, `go_back`, `wait`, `wait_input`, `type`, `press`, `select`, `scroll`, `mouse_move`, `mouse_move_random`, `click`, `click_link_by_index`, `mouse_press`, `hover`, `screenshot`, `plugin_call`, `webhook`.

---

# Action Reference

## 1. `open`

**Purpose:** navigate the current tab to a URL.

**Required:** `url`.

**Optional:** `wait_until` (default `domcontentloaded`), `timeout_ms` (default `60000`).

```json
{
  "type": "open",
  "url": "https://example.com",
  "wait_until": "domcontentloaded",
  "timeout_ms": 60000
}
```

---

## 2. `new_tab`

**Purpose:** create a new browser tab, optionally navigating it immediately.

**Required:** none.

**Optional:** `url`, `wait_until` (default `domcontentloaded`), `timeout_ms` (default `60000`).

```json
{
  "type": "new_tab",
  "url": "https://www.mozilla.org/",
  "timeout_ms": 60000
}
```

Without `url`, a blank tab is created.

---

## 3. `switch_tab`

**Purpose:** switch the scenario's active page to an already known/newly detected browser tab.

**Required:** normally `index` or `target`.

**Optional:** `index`, `target`, `timeout_ms` (default `15000`).

Index example:

```json
{
  "type": "switch_tab",
  "index": 1,
  "timeout_ms": 15000
}
```

The first tab is index `0`, the second is `1`, etc. `target` is also supported by the runtime page switcher.

---

## 4. `go_back`

**Purpose:** browser Back in the current tab.

**Required:** none.

**Optional:** `wait_until` (default `domcontentloaded`), `timeout_ms` (default `60000`).

```json
{
  "type": "go_back",
  "wait_until": "domcontentloaded",
  "timeout_ms": 60000
}
```

---

## 5. `wait`

**Purpose:** pause between actions. A random duration is chosen between `min` and `max`.

**Required:** none.

**Optional:** `min` seconds (default `1`), `max` seconds (default = `min`).

```json
{
  "type": "wait",
  "min": 2,
  "max": 4
}
```

For a fixed delay, use the same values:

```json
{
  "type": "wait",
  "min": 2,
  "max": 2
}
```

---

## 6. `wait_input`

**Purpose:** pause the run until external runtime data is supplied through the worker Control API.

**Required:** `key`.

**Optional:** `timeout_sec` (default `600`), `on_timeout` = `fail|continue|default` (default `fail`), `default` when policy is `default`, `consume` (default `false`).

```json
{
  "type": "wait_input",
  "key": "code",
  "timeout_sec": 600,
  "on_timeout": "fail"
}
```

Default-value policy:

```json
{
  "type": "wait_input",
  "key": "country",
  "timeout_sec": 60,
  "on_timeout": "default",
  "default": {
    "code": "DE",
    "name": "Germany"
  }
}
```

Received data can be referenced later with runtime templates such as `{{input.code.value}}` according to the supplied payload structure. See `API.md`.

---

## 7. `type`

**Purpose:** enter text into the first element matching `selector`.

**Required:** `selector`, `text`.

**Optional:** `timeout_ms` (default `15000`), `clear` (default `true`), `delay_ms` per character (default `70`).

```json
{
  "type": "type",
  "selector": "input#floatingLabelInputs:visible",
  "text": "example-user",
  "clear": true,
  "delay_ms": 70,
  "timeout_ms": 15000
}
```

Runtime values are allowed:

```json
{
  "type": "type",
  "selector": "input[name=\"verificationCode\"]:visible",
  "text": "{{input.code.value}}"
}
```

---

## 8. `press`

**Purpose:** send a keyboard key to the first element matching `selector`.

**Required:** `selector`.

**Optional:** `key` (default `Enter`).

```json
{
  "type": "press",
  "selector": "input[name=\"q\"]",
  "key": "Enter"
}
```

Another example:

```json
{
  "type": "press",
  "selector": "button[data-testid=\"countryDropdown\"]",
  "key": "ArrowDown"
}
```

---

## 9. `select`

**Purpose:** choose an option from a native `<select>` or a custom combobox/listbox.

**Required:** `selector` and **exactly one** of `value`, `label`, `index`.

**Optional:** `method` = `auto|native|custom` (default `auto`), `timeout_ms` (default `15000`), `exact` for custom label matching (default `true`), `option_selector`.

Native example:

```json
{
  "type": "select",
  "selector": "select[name=\"country\"]",
  "value": "DE",
  "method": "auto",
  "timeout_ms": 15000
}
```

Custom dropdown example:

```json
{
  "type": "select",
  "selector": "button[data-testid=\"countryDropdown\"]",
  "label": "Deutschland",
  "method": "custom",
  "timeout_ms": 15000
}
```

Custom dropdown with explicit option selector:

```json
{
  "type": "select",
  "selector": "#countryDropdownId",
  "label": "Deutschland",
  "option_selector": "[role=\"option\"]",
  "method": "custom",
  "timeout_ms": 15000
}
```

---

## 10. `scroll`

**Purpose:** physically scroll using the mouse wheel.

There are two modes.

Random distance:

```json
{
  "type": "scroll",
  "direction": "down",
  "distance": [400, 900]
}
```

**Optional:** `direction` = `down|up` (default `down`), `distance` = `[min,max]` pixels (default `[350,900]`), `delta_x` (default `0`).

Exact distance:

```json
{
  "type": "scroll",
  "delta_y": 700,
  "delta_x": 0
}
```

When `delta_y` is supplied it takes precedence over `direction`/`distance`. Negative `delta_y` scrolls upward.

---

## 11. `mouse_move`

**Purpose:** physically move the Camoufox pointer to absolute viewport coordinates.

**Required:** `x`, `y`.

**Optional:** `clamp_to_viewport` (default `true`).

```json
{
  "type": "mouse_move",
  "x": 800,
  "y": 450,
  "clamp_to_viewport": true
}
```

Camoufox owns the humanized trajectory. Legacy `duration` and `steps` values are accepted but intentionally ignored.

---

## 12. `mouse_move_random`

**Purpose:** make several random physical pointer movements inside the viewport.

**Required:** none.

**Optional:** `count` (default `3`).

```json
{
  "type": "mouse_move_random",
  "count": 4
}
```

Useful for generic human-like activity when no DOM target is required.

---

## 13. `click`

**Purpose:** click the first visible element matching any valid Playwright/CSS selector.

**Required:** `selector`.

**Optional:** `method` = `locator|mouse` (default `locator`), `timeout_ms` (default `15000`), `force` for locator method, `button` for mouse method.

Physical mouse click:

```json
{
  "type": "click",
  "selector": "button[data-testid=\"primaryButton\"]:visible",
  "method": "mouse",
  "timeout_ms": 15000
}
```

Generic attribute selector:

```json
{
  "type": "click",
  "selector": "a[name=\"navigation-consumer-reviews-desktop\"]:visible",
  "method": "mouse",
  "timeout_ms": 15000
}
```

Locator click:

```json
{
  "type": "click",
  "selector": "#submit",
  "method": "locator",
  "force": false,
  "timeout_ms": 15000
}
```

`method: "mouse"` waits for visibility, resolves the element bounding box, moves the physical pointer to its center using Camoufox humanization, then clicks.

---

## 14. `click_link_by_index`

**Purpose:** click a numbered element from a selector result set. Despite the historical name, the implementation uses whatever selector is supplied.

**Required:** none.

**Optional:** `selector` (default `a[href]`), `index` (default `0`).

```json
{
  "type": "click_link_by_index",
  "selector": "#mw-content-text a[href^=\"/wiki/\"]",
  "index": 3
}
```

If the requested index is larger than the result set, the current implementation clamps it to the last match.

**Architecture note:** this is a specialized/legacy-style action and is a candidate for future replacement by generic `click` with an `index` parameter. Do not remove it until existing scenarios are migrated.

---

## 15. `mouse_press`

**Purpose:** physically move to a target, press a mouse button, hold it for a duration, and release it.

Exactly one target mode is required: `selector` **or** `position`.

**Optional:** `button` = `left|right|middle` (default `left`), `hold_ms` (default `1000`), `timeout_ms` (default `15000`), `offset`, `frame_selector`, `frames`.

Selector example:

```json
{
  "type": "mouse_press",
  "selector": "div[role=\"button\"]:visible",
  "button": "left",
  "hold_ms": 10000,
  "timeout_ms": 15000
}
```

Precise center-relative offset:

```json
{
  "type": "mouse_press",
  "selector": "#hold-button:visible",
  "offset": {
    "x": 10,
    "y": -5
  },
  "hold_ms": 3000,
  "timeout_ms": 15000
}
```

Absolute viewport coordinates:

```json
{
  "type": "mouse_press",
  "position": {
    "x": 900,
    "y": 500
  },
  "button": "left",
  "hold_ms": 2000
}
```

Single iframe:

```json
{
  "type": "mouse_press",
  "frame_selector": "iframe[data-testid=\"contentFrame\"]",
  "selector": "div[role=\"button\"]:visible",
  "hold_ms": 3000,
  "timeout_ms": 15000
}
```

Nested iframes:

```json
{
  "type": "mouse_press",
  "frames": [
    "iframe#outer",
    "iframe#inner"
  ],
  "selector": "button:visible",
  "hold_ms": 3000,
  "timeout_ms": 15000
}
```

`offset` is relative to the center: positive X = right, negative X = left, positive Y = down, negative Y = up.

---

## 16. `hover`

**Purpose:** physically move the Camoufox pointer over an element and leave it there without clicking.

**Required:** `selector`. It may target any HTML/SVG element supported by Playwright; `hover` is not tied to `span`, `div`, etc.

**Optional:** `timeout_ms` (default `15000`), `offset`, `frame_selector`, `frames`.

Short CSS-module-mask example:

```json
{
  "type": "hover",
  "selector": "[class*=\"styles_displayName__\"]:visible",
  "timeout_ms": 15000
}
```

More specific compound selector:

```json
{
  "type": "hover",
  "selector": "[class*=\"styles_displayName__\"][data-navigation-consumer-name-label=\"true\"]:visible",
  "timeout_ms": 15000
}
```

Exact positioning:

```json
{
  "type": "hover",
  "selector": "a[name=\"navigation-consumer-reviews-desktop\"]:visible",
  "offset": {
    "x": 15,
    "y": -10
  },
  "timeout_ms": 15000
}
```

Iframe:

```json
{
  "type": "hover",
  "frame_selector": "iframe[data-testid=\"contentFrame\"]",
  "selector": "button[data-testid=\"profile\"]:visible",
  "timeout_ms": 15000
}
```

Nested iframe chains use `frames` exactly as with `mouse_press`.

---

## 17. `screenshot`

**Purpose:** save a screenshot into the current run's `screenshots` artifact directory.

**Required:** none.

**Optional:** `name` (default `<action-index>.png`), `full_page` (default `false`).

```json
{
  "type": "screenshot",
  "name": "after-submit.png",
  "full_page": true
}
```

---

## 18. `plugin_call`

**Purpose:** invoke a method on an enabled plugin adapter.

**Required:** `plugin`, `method`.

**Optional:** `params` object (default `{}`). Engine-level timeout/error-policy fields may also be used where supported by the action engine.

```json
{
  "type": "plugin_call",
  "plugin": "playwright-recaptcha",
  "method": "solve_v2",
  "params": {
    "wait": true,
    "image_challenge": false
  },
  "action_timeout_ms": 120000
}
```

The named plugin must be enabled/configured in the top-level `plugins` configuration. See `PLUGINS.md`.

---

## 19. `webhook`

**Purpose:** make an outbound HTTP request from the scenario and store the response in runtime context.

**Required:** `url`.

**Optional:** `method` (default `POST`), `timeout_ms` (default `10000`), `retries` (default `0`), `save_as` (default `response`), `on_error` = `fail|continue` (default `fail`), plus `headers`, `params`, `json`, `data`.

GET example:

```json
{
  "type": "webhook",
  "url": "http://data-provider:8080/api/v1/profiles/resolve",
  "method": "GET",
  "timeout_ms": 10000,
  "retries": 1,
  "save_as": "profile",
  "on_error": "fail"
}
```

POST example:

```json
{
  "type": "webhook",
  "url": "https://example.internal/api/data",
  "method": "POST",
  "headers": {
    "X-Source": "camoufox"
  },
  "json": {
    "run_id": "{{run.id}}"
  },
  "timeout_ms": 10000,
  "save_as": "external",
  "on_error": "continue"
}
```

A JSON response saved as `profile` can later be referenced through templates such as:

```json
{
  "type": "type",
  "selector": "input[name=\"firstName\"]",
  "text": "{{webhook.profile.first_name}}"
}
```

---

# Runtime templates

Scenario action values are resolved before execution. Runtime inputs and saved webhook responses can therefore feed later actions.

Examples:

```json
{
  "type": "type",
  "selector": "input[name=\"code\"]",
  "text": "{{input.code.value}}"
}
```

```json
{
  "type": "type",
  "selector": "input[name=\"email\"]",
  "text": "{{webhook.profile.login}}"
}
```

Keep template paths consistent with the actual JSON payload received/stored.

# Engine-level error policy

The action engine supports its existing run/debug failure behavior independently of the action-specific parameters documented above. Some integrations also have their own policies, such as `wait_input.on_timeout` and `webhook.on_error`.

A future centralized Playwright error-normalization layer is documented in `../FUTURE.md` / `../FUTURE_BOT.md`; it is not yet implemented.

# Duplication / API review notes

- `click_link_by_index` overlaps conceptually with `click`; future generic `click.index` can replace it after migration.
- `click(method=mouse)`, `hover`, and `mouse_press` intentionally remain separate scenario actions because their user-visible semantics differ, even though they share target-resolution/mouse-movement logic internally.
- `mouse_move_random` is intentionally a convenience action over generic physical pointer movement.
- Future refactoring should share selector/frame/bounding-box/offset resolution internally rather than collapsing these readable scenario actions into one overloaded action.


# Consent / cookie banners

Consent handling is intentionally implemented through `plugin_call`, so it does not add another core action type.

Typical optional consent step after navigation:

```json
{
  "type": "plugin_call",
  "plugin": "consent-handler",
  "method": "handle",
  "params": {
    "policy": "accept_all",
    "timeout_ms": 8000,
    "required": false
  },
  "action_timeout_ms": 12000
}
```

For privacy-oriented test flows:

```json
{
  "type": "plugin_call",
  "plugin": "consent-handler",
  "method": "handle",
  "params": {
    "policy": "reject_optional",
    "timeout_ms": 8000,
    "required": false
  },
  "action_timeout_ms": 12000
}
```

Use `required=false` in reusable scenarios where a banner may or may not appear. Use `required=true` in a deterministic consent test.

The bundled `consent-test` scenario targets `http://consent-test-page/` and validates the provider-specific path locally.


# Recording cursor visibility

When debugging recorded scenarios, enable:

```json
"recording": {
  "video": true,
  "show_cursor": true
}
```

The red marker follows scripted physical mouse actions. No scenario action is required; the overlay is runtime recording behavior. It does not intercept pointer events and is re-created after navigation.


## Live recording cursor trajectory (v0.5.18)

With `recording.show_cursor=true`, the red marker follows the browser's live `mousemove` events while Camoufox moves the pointer. This is recording/runtime behavior; scenario JSON does not need any additional action.


## Action catalog audit — v0.5.18-2

The runtime action registry and this document were cross-checked. The current implemented action catalog contains **19 actions**, all documented above:

`open`, `new_tab`, `switch_tab`, `go_back`, `wait`, `wait_input`, `type`, `press`, `select`, `scroll`, `mouse_move`, `mouse_move_random`, `click`, `click_link_by_index`, `mouse_press`, `hover`, `screenshot`, `plugin_call`, `webhook`.

When a new action is added to `app/actions/`, its SCENARIO entry and example are part of the release Definition of Done.
