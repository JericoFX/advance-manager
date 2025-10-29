# Code Review Findings

## 1. `Business.HasPermission` ignores requested permission flags
- **Location:** `server/modules/business.lua` lines 103-138.
- **Issue:** The `permission` argument is never used, so every permission check effectively devolves into a simple boss check. Downstream consumers expecting granular permissions (for example, to differentiate finance access from hiring access) cannot rely on this export.
- **Suggestion:** Accept a permission map (e.g., from `business.metadata` or `Config`) and honor the requested flag before defaulting to the `isboss` gate. Consider caching resolved permissions alongside the employee cache to avoid repeated table walks.

## 2. `getAllEmployeesCache` exposes mutable cache state
- **Location:** `server/init.lua` lines 173-175.
- **Issue:** The export returns the backing `EmployeeCache` table by reference. Any external resource that calls this export can mutate or clear the cache, bypassing your safety guarantees.
- **Suggestion:** Return a deep clone (e.g., `deepClone(EmployeeCache)`) or provide read-only accessors so that the cache can only be mutated through the controlled functions defined in `Employees`.

## 3. Client wage/grade inputs drift from authoritative job data
- **Locations:** `client/init.lua` lines 185-186 and 224-254; `ui/js/main.js` lines 158-198; `server/modules/employees.lua` lines 9-48.
- **Issue:** The UI hardcodes grades `0-4` and wage ranges `10-100`, but the server clamps wages between `0-10000` and validates grades against the actual job definition. Jobs with more (or fewer) grades—or custom wage scales—will not render correctly and will frustrate admins.
- **Suggestion:** Fetch grade definitions from the server (e.g., extend `advance-manager:getPlayerBusiness` to return `Business.GetJobInfo`) and populate the dialogs dynamically. Mirror the server’s wage limits in the client to keep validation consistent.
