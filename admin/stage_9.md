# Stage 9 — Evidence Integrity + UX Support Endpoints

This stage extends evidence handling and menu bootstrap APIs required by the universal admin journey workspace.

## Implemented

1. Snapshot verification endpoint:
   - `GET /api/admin/security/snapshots/{id}/verify/`
   - recomputes SHA-256 digest over stored payload
   - returns `stored_sha256`, `recomputed_sha256`, and `match`
2. Universal menu endpoint:
   - `GET /api/admin/security/menu/`
   - returns canonical section definitions for admin UI navigation
3. Additional tests:
   - snapshot verify success path
   - menu endpoint availability and section count

## Verification

1. Create snapshot for a report.
2. Call `/verify/` and confirm `match=true`.
3. Call `/menu/` and confirm required section keys are present.
4. Confirm both endpoints remain admin-role protected.

## Notes

- This stage provides integrity attestation checks in-app without exposing message/media plaintext.
- Menu endpoint keeps UI and backend requirements aligned on section naming/order.
