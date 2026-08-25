# web-console 0.1.19-dev

Early control-plane web interface built with React, TypeScript and Google Material Design through Material UI. The visual direction follows modern infrastructure dashboards: persistent navigation, compact operational cards, clear health states and responsive layouts.

Current scope:

- overview dashboard;
- live `data-provider` and `worker-firefox` health checks;
- responsive desktop/mobile navigation;
- collapsible desktop navigation with icon-only mode;
- system, light and dark themes with the preference stored in the browser;
- module registry for contributed pages, menu entries and settings sections;
- Controller-backed Workers view with queue/history, Create Run, priority and stop;
- nested Workers navigation for editable Identity profiles and versioned scenarios;
- JSON scenario import and save-as-new-version workflow without redeploy;
- profile-only and permanent persistent account-data deletion with confirmation;
- editable Default Identity profile under Settings, used by New Identity;
- confirmed scenario deletion that preserves historical run references;
- collapsible scenario version trees and activation of any archived version;
- active scenario version pinned as the tree root, with archived versions below;
- cloning active or archived versions into uniquely named independent scenarios;
- separate scenario Steps and per-version Runs statistics;
- Workers scenario labels in `name:version` format and precise creation timestamps;
- sortable Workers columns, non-wrapping Identity names and compact right-aligned status/log controls;
- read-only live noVNC modal for running debug tasks, proxied exclusively through Controller;
- recorded-video icons and in-console WebM playback after artifact finalization;
- scrollbar-free media dialogs sized from the actual noVNC canvas or WebM aspect ratio and constrained by the current browser viewport;
- a compact selector for runs with multiple recordings, keeping only one fitted video visible at a time;
- current section persisted in URL hash with reload and browser back/forward support;
- Controller Bearer token setting stored in the operator's browser;
- placeholder for data sources and a JSON-based scenario editor ready for a future structured editor.

## Console modules

Modules are registered in `src/modules/registry.tsx` and implement the contracts from `src/modules/types.ts`. A module may contribute one or more pages (automatically added to the side menu) and settings sections (automatically added to Settings). This keeps the application shell independent from component-specific features.

Start from the repository root:

```bash
docker compose --profile data-provider --profile web-console up -d --build data-provider web-console
```

Open `http://localhost:3000`.

The worker card becomes healthy when `worker-firefox` is running in the same root Compose project.

The dashboard discovers enabled API components from the read-only global registry at `config/components.json`. Nginx is the browser-facing same-origin proxy, and all worker operations use the Controller API.
