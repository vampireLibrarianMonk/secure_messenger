# Stage 8 — Universal Admin Menu Frontend Workspace (Organized UI)

This stage adds a single admin workspace UI surface inside the frontend app for triggering analysis and reviewing results.

## Implemented

1. Admin UI role gating based on `auth/me`:
   - requires `is_security_admin=true`
   - blocked if `must_reset_password=true`
2. Universal menu/tab-driven workspace with required sections:
   - Overview / Dashboard
   - Run Analysis
   - DM Journey
   - Video Journey
   - Verification Matrix
   - Scope Coverage
   - Logging Design
   - Threat Model
   - Top Gaps & Next Tests
   - Reality Check
   - Evidence & Snapshots
   - Audit Trail
3. Organized report controls:
   - create report
   - select report
   - trigger run with flow/check selections
4. Snapshot actions surfaced in UI:
   - create snapshot
   - verify snapshot integrity

## Verification

1. Login as security admin and confirm workspace renders.
2. Create/select report and trigger run from UI (no direct API tooling).
3. Navigate all sections and confirm report context is preserved.
4. Verify non-admin users do not see/admin-access this workspace.

## Notes

- UI currently renders normalized list/detail style views and raw overview payload for speed.
- Further UX polish can be layered without changing backend contract.
