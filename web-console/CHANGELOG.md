# web-console changelog

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
