# 05 — Audit: Group Join and Rekey Test (`documentation/05-group-join-and-rekey-test.md`)

## Audit Verdict
**Verdict: VERIFIED as synthetic group-security simulation; not verified as real cryptographic group rekey protocol execution.**

## What the Document Claims
The document claims group init, membership change, rekey, redistribution, and access check, with evidence-based classification.

## Code Evidence

### A) Scenario contract matches document
- `frontend/src/lib/scenarioCatalog.ts`
  - `id: "group-join-rekey"`
  - ordered steps: `group-init`, `membership-change`, `rekey`, `redistribute`, `access-check`
  - feature flag requirement: `group_testing_enabled`

### B) Group scenario gating exists
- `frontend/src/components/AdminTestLabPanel.vue`
  - scenario list is filtered by feature flags from bootstrap response.
- `backend/messenger/views.py` (`TestLabBootstrapView`)
  - exposes `feature_flags` including group testing controls.

### C) Evidence fields for group assertions exist
- `frontend/src/lib/resultModel.ts`
  - includes:
    - `groupMembershipRekeyConfirmed`
    - `groupPostRemovalAccessDeniedConfirmed`
  - group scenario can resolve to PASS/UNKNOWN/FAIL based on evidence flags.

## Critical Gap / Limitation
No concrete group cryptographic ratchet/rekey protocol implementation is present in backend/frontend messaging flows for actual group payload cryptography in this test harness.

The test validates **simulation logic and policy-state sequencing**, not mathematical correctness of a real sender-key distribution protocol.

## Standards/Framework Traceability
- No MLS/Signal-group-protocol implementation references are present in this repository for this test path.
- No ISO compliance assertion evidence for group rekey subsystem.

## Required Codebase Changes to Close Security Gaps
1. **Implement concrete group key management protocol**
   - Add group key state model (epoch/version, sender keys, membership-bound keysets) in backend models and frontend state.
   - Implement rekey on join with deterministic sequencing and distribution acknowledgements.

2. **Bind group membership changes to cryptographic state transitions**
   - In conversation membership endpoints (`backend/messenger/views.py`), trigger explicit group rekey events and persist auditable rekey metadata.
   - Ensure all active participants receive new key envelopes; block protected sends until rekey completion.

3. **Add group rekey correctness tests**
   - Add integration tests proving new participant can decrypt only post-join epoch messages and cannot decrypt prior protected history unless policy permits.
   - Add failure-path tests for partial redistribution and rollback handling.

4. **Align synthetic group PASS with real cryptographic events**
   - Update Admin Test Lab/result model so group PASS requires real rekey event artifacts (epoch increment, distribution success records), not only warning-free simulation.

## Implementation Progress Update (Current Phase)
### Completed in this phase
- Backend now records and enforces **group key epoch lifecycle**:
  - Initial epoch event on group creation.
  - Epoch increment on membership add/leave.
  - Group message send now requires `aad.group_epoch` to match current epoch.
- Added `GET /api/conversations/{id}/key-epoch/` so clients can synchronize to current server epoch.
- Frontend send flows now include epoch-aware AAD for group messages/attachment markers and retry once using server-indicated expected epoch.

### Security impact
- Converts prior soft/synthetic rekey notion into enforced **server-validated epoch gating** for group protected sends.
- Reduces stale-key send risk after membership transitions.

### Remaining gaps
- No cryptographic sender-key distribution protocol implemented yet.
- No per-member key envelope acknowledgements.
- PASS criteria in synthetic test-lab still not fully bound to cryptographic proof artifacts.
