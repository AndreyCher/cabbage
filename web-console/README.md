# web-console 0.1.0-dev

Early control-plane web interface built with React, TypeScript and Google Material Design through Material UI. The visual direction follows modern infrastructure dashboards: persistent navigation, compact operational cards, clear health states and responsive layouts.

Current scope:

- overview dashboard;
- live `data-provider` and `worker-firefox` health checks;
- responsive desktop/mobile navigation;
- collapsible desktop navigation with icon-only mode;
- system, light and dark themes with the preference stored in the browser;
- module registry for contributed pages, menu entries and settings sections;
- placeholders for workers, data sources, scenarios and run creation.

## Console modules

Modules are registered in `src/modules/registry.tsx` and implement the contracts from `src/modules/types.ts`. A module may contribute one or more pages (automatically added to the side menu) and settings sections (automatically added to Settings). This keeps the application shell independent from component-specific features.

Start from the repository root:

```bash
docker compose --profile data-provider --profile web-console up -d --build data-provider web-console
```

Open `http://localhost:3000`.

The worker card becomes healthy when `worker-firefox` is running in the same root Compose project.

The dashboard discovers enabled API components from the read-only global registry at `../config/components.json`. Nginx remains the temporary browser-facing proxy; once Controller exists, the UI will consume the Controller component API instead.
