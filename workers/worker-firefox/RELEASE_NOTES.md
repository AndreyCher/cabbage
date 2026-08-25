# Release Notes — worker-firefox v0.5.29

## Reliable non-debug video recording

Camoufox v152 created Playwright video objects for ordinary virtual runs but
finalized each recording as a 4,133-byte header-only WebM with no visible
frames. The worker now starts a private Xvfb/Openbox display whenever normal
recording is enabled and captures that display through FFmpeg.

The browser remains non-debug from the operator's perspective: no noVNC,
x11vnc or websockify service is started. All navigation and newly opened tabs
are captured chronologically in one `videos/session.webm` file. Runs with
recording disabled continue to use the lightweight virtual browser mode.

## Exact orchestrated artifact ownership

When Controller supplies its run identifier, worker `summary.json` now records
it as `controller_run_id`. This prevents artifacts from sequential executions
of the same Identity and scenario from being associated with the wrong task.
Standalone behavior is unchanged.

## Controller-safe read-only noVNC

Controller-managed debug workers now receive `NOVNC_VIEW_ONLY=true`. The worker
translates it to x11vnc's server-side `-viewonly` mode, so keyboard and pointer
events are rejected even if a browser client removes noVNC's `view_only` URL
option. Port 6080 remains internal in orchestrated mode.

The option defaults to `false`, preserving the existing fully interactive
standalone `worker-firefox-debug` workflow.

## Reliable random mouse behavior

`mouse_move_random` now uses bounded DOM mouse events by default. This avoids the
Camoufox v152 native IPC stall while preserving observable cursor movement for
page scripts and recordings. Native Camoufox movement remains available through
the explicit `"method": "native"` action option. `count` is validated in the
range 1–100.

## Readable action failures

Action failures now have a stable structured shape for operators and the
Controller. Instead of exposing raw Python exceptions, normal output includes a
short reason, action number and relevant context; technical tracebacks remain in
debug logs.

`click_link_by_index` distinguishes:

- `selector_no_matches` when the selector finds no links;
- `link_index_out_of_range` when the requested index exceeds the match count.

## Immutable UBO layer

The runtime uses `worker-firefox-base:152.0.4-beta.28-ubo1`, with UBlock Origin
1.73.0 installed in the Camoufox addon cache and verified by SHA-256 during the
image build. Ephemeral workers no longer download and extract UBO on every run.

## Verification

This release is covered by 66 unit tests. Controller run
`6e10076a-d435-42a5-baa9-a77ce2f81d60` executed active database scenario
`example:2` without debug mode, passed all 24 actions and produced four
screenshots plus one 39.53-second, 1.88 MB VP9 `session.webm`. Frames from the
Wikipedia and YouTube phases were visually verified.
