# web-console changelog

## 0.1.25-dev

- Fixed Workers data rows at a consistent 44-pixel height across all run statuses.
- Compacted the queued-run Priority editor to fit inside the row without changing table density.

## 0.1.24-dev

- Started recorded videos automatically when their media dialog opens or a different recording is selected.
- Used muted inline autoplay so browser autoplay policies do not block playback; controls remain available for manual unmuting.

## 0.1.23-dev

- Persisted the selected page size independently for Workers, Identities and Scenarios tables.
- Restored valid 25/50/100/150 selections after page reload and used 50 only when no preference exists.

## 0.1.22-dev

- Expanded Workers, Identities and Scenarios tables across the complete available content width.
- Reduced table-page edge spacing to 12 pixels while preserving the constrained layout for non-table pages and dialogs.

## 0.1.21-dev

- Added consistent client-side pagination to Workers, Identities and Scenarios tables.
- Defaulted every table to 50 items per page with dropdown options for 25, 50, 100 and 150.
- Added first/previous/next/last page controls without dynamic or incremental loading.
- Paginated scenario trees by scenario group so immutable versions stay together.

## 0.1.20-dev

- Added a debug indicator immediately to the left of the scenario name for every debug run.
- Showed recorded-video playback only when Controller verifies a non-empty WebM owned by that exact run.

## 0.1.19-dev

- Removed horizontal and vertical scrollbars from live-stream and recorded-video dialogs.
- Kept noVNC and WebM content contained inside the viewport without cropping or aspect-ratio distortion.
- Added a compact recording selector when a run contains multiple WebM files instead of stacking videos vertically.

## 0.1.18-dev

- Sized live-stream and recorded-video dialogs from the actual media aspect ratio.
- Recalculated the dialog against the current Web UI viewport on every browser resize.
- Kept media fully visible within desktop, tablet and mobile viewport bounds without distortion.

## 0.1.17-dev

- Added a read-only live-stream icon for active debug runs beside Logs and Stop.
- Added a modal noVNC viewer whose HTTP and WebSocket traffic is proxied through Controller.
- Replaced live streaming with recorded-video playback after a run finishes and a WebM artifact exists.
- Converted the Stop action to the same compact tooltip-icon pattern as neighboring row actions.

## 0.1.16-dev

- Added ascending and descending sorting to every Workers data column, with numeric priority/version and timestamp-aware ordering.

## 0.1.15-dev

- Prevented Identity profile names from wrapping and added a stable minimum Workers table width with horizontal overflow.

## 0.1.14-dev

- Replaced the Workers Logs text action with a tooltip icon.
- Grouped run status and actions in one compact right-aligned table column.

## 0.1.13-dev

- Moved Workers status immediately before run actions.
- Displayed the immutable task creation timestamp with seconds and the browser's local timezone, with exact ISO time on hover.

## 0.1.12-dev

- Replaced the ambiguous Actions column with separate Steps and Runs counts for every scenario version.

## 0.1.11-dev

- Persisted the selected console section in the URL hash across reloads and browser back/forward navigation.

## 0.1.10-dev

- Displayed scenario names together with their exact versions as `name:version` in Create Run and run history.

## 0.1.9-dev

- Added Clone to active scenario versions and replaced scenario-row action labels with accessible tooltip icons.

## 0.1.8-dev

- Replaced Open with Clone for archived scenario versions and added confirmation plus unique-name dialogs.

## 0.1.7-dev

- Fixed scenario-tree ordering so the active version is always the root row.
- Moved the previous active version into the archived children after activation.
- Displayed latest and active version numbers separately for trees of any size.

## 0.1.6-dev

- Grouped scenarios into collapsible version trees.
- Showed the active version while collapsed and all immutable versions when expanded.
- Added Activate for archived versions without creating or renumbering versions.

## 0.1.5-dev

- Added confirmed deletion of a scenario and all catalog versions.
- Kept historical run data intact through Controller logical deletion.

## 0.1.4-dev

- Added guarded Identity profile deletion and explicit permanent account-data deletion.
- Added Default Identity profile JSON settings with revision tracking.
- Loaded server defaults into New Identity and merged them again server-side.

## 0.1.3-dev

- Added nested Workers → Identities and Workers → Scenarios pages.
- Added Identity profile creation, JSON viewing/editing, revision and usage state.
- Added scenario viewing, archived versions, JSON editing and file import.
- Updated Create Run to select an available persisted Identity.

## 0.1.2-dev

- Connected Workers and the overview Create Run action to Controller.
- Added queue/history, priority, current stage and Stop/Cancel controls.
- Added authenticated Create Run modal and Controller token setting.

## 0.1.1-dev

- Synchronized the console documentation and root deployment workflow with the modular `workers/` layout.
- Kept runtime component discovery based on the global `config/components.json` registry.
- Revalidated the production frontend image against the updated root Compose application.

## 0.1.0-dev

- Added the first React 19 and TypeScript control-plane interface using Material UI.
- Added a responsive infrastructure overview with runtime component discovery and live health cards.
- Added temporary Nginx API proxies for `data-provider` and `worker-firefox`.
- Added responsive navigation with a persistent icon-only collapsed desktop mode.
- Added system, light and dark appearance modes with browser-persisted preferences.
- Added a neutral Visual Studio Code-inspired dark palette.
- Added a frontend module registry through which modules contribute pages, navigation entries and settings sections.
- Added a production multi-stage Docker image served by Nginx.
