# Advance Manager Contribution Guide

## Resource Overview
- **Purpose**: Advanced business management system for FiveM servers running QBCore. Provides server/client Lua logic and a browser-based UI for managing businesses, employees, and finances.
- **Core Dependencies**: `qb-core`, `ox_lib`, `oxmysql`, and the NUI assets under `ui/`.
- **Key Features**:
  - Dynamic business discovery from `QBCore.Shared.Jobs` with automatic boss-grade permissions.
  - Server-side employee cache for high-performance lookups and exports documented in `README.md`.
  - Optional `rs.py` desktop helper for working with RS texture packages from the Asura engine.

## Repository Structure
- `fxmanifest.lua`: Declares FiveM metadata and the canonical version number (used by release automation).
- `client/`: Front-end Lua scripts that interact with the player, NUI, and `ox_lib` contexts.
- `server/`: Initialization logic plus modularized business and employee management (`server/modules`).
- `shared/`: Configuration defaults (`config.lua`) and shared type helpers (`types.lua`).
- `ui/`: Static HTML/CSS/JS served via NUI. JavaScript relies on jQuery and should be run/tested with Bun when tooling is required.
- `rs.py` & `requirements.txt`: Stand-alone Python utility for RS texture workflows.
- `.github/workflows/`: CI definitions. Releases are orchestrated from `fxmanifest.lua`.

## Coding Guidelines
- **Lua**: Prefer 4-space indentation, `local` scoping by default, and descriptive function names. Keep shared constants in `shared/`.
- **JavaScript**: Stick to ES6+ syntax, keep logic modular in `ui/js/`, and rely on Bun (`bun install`, `bun run lint`, etc.) for future tooling scripts.
- **Python** (`rs.py`): Follow PEP 8 and keep GUI logic encapsulated in classes or namespaced functions.
- Document new exports, commands, or configuration flags in `README.md` whenever you add them.

## Testing & QA
- Validate Lua changes in a QBCore-enabled FiveM test server. Focus on the employee cache refresh flow and permission checks.
- Exercise NUI screens directly in the browser (the UI auto-opens when `FiveMCallbacks` is undefined) and inside FiveM to validate callback wiring.
- Run Python packaging checks with `python -m pip install -r requirements.txt` followed by `pyinstaller --onefile rs.py` if you change `rs.py`.

## Release Process
- The version declared in `fxmanifest.lua` is the single source of truth.
- Pushing to `main` triggers the automated release workflow, which tags `v<version>` and creates/updates a GitHub release if one does not already exist.
- Update `fxmanifest.lua` with semantic versioning whenever you prepare a release.

## Areas to Improve Before a Public Release
1. **Security hardening**: add server-side rate limiting for hire/fire endpoints and audit logging for financial operations.
2. **Documentation**: provide SQL migration snippets, permission matrix tables, and UI screenshots in `README.md`.
3. **Localization**: extract hard-coded English strings in Lua and UI JavaScript into a translation layer to support multi-language servers.
4. **Automated testing**: introduce Lua unit/integration tests (e.g., via `busted`) for the business/employee modules and linting for UI assets.
5. **Configuration flexibility**: expose customizable wage caps, boss-grade overrides, and UI theme toggles through `shared/config.lua`.

Keep this file updated as the resource evolves.
