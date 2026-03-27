# Stage 7 — Universal Admin Menu Backend Foundation (Run Lifecycle + Dashboard)

This stage introduces backend primitives for the universal admin security menu and report execution lifecycle.

## Implemented

1. `SecurityAnalysisRun` model for run lifecycle tracking:
   - flow type (`dm`, `video`, `both`)
   - status (`queued`, `running`, `completed`, `failed`)
   - requested checks
   - run summary and failure reason
2. API and serialization:
   - `GET /api/admin/security/runs/`
   - enhanced `POST /api/admin/security/run/` with run creation + completion metadata
3. Dashboard endpoint:
   - `GET /api/admin/security/dashboard/`
   - supports optional `?report=<id>` filtering
4. `auth/me` now includes `is_security_admin` to drive UI role gating.

## Verification

1. Create admin report.
2. Trigger run via `/api/admin/security/run/`.
3. Confirm run appears in `/api/admin/security/runs/?report=<id>`.
4. Confirm summary values in `/api/admin/security/dashboard/?report=<id>`.
5. Confirm non-admin requests are denied (403).

## Notes

- Run processing is currently synchronous summary generation.
- This stage provides lifecycle structure for async queue workers in later hardening.
