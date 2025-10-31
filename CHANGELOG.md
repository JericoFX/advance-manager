# Changelog

## Unreleased
- Add review notes outlining permission handling, cache safety, and UI validation gaps.
- Honor granular permission flags while caching matrices per business and cloning employee cache exports for safety.
- Expose job grade metadata and wage limits to clients with dynamic Lua dialogs and synchronized NUI hire flows.
- Derive employee wages from QBCore grade payments for hires and grade changes while reflecting fixed wages in hiring dialogs.
- Align ox_lib command usage by registering business commands server-side and triggering client menus through events.
- Harden business creation flows by validating permissions and inputs before serving ox_lib dialogs or persisting server data.
