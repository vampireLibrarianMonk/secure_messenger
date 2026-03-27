# 07 — Audit: Group Call Membership-Change Test (`documentation/07-group-call-membership-change-test.md`)

## Audit Verdict
**Verdict: VERIFIED for synthetic scenario sequencing and classification; not verified as implemented secure group-call sender-key cryptosystem.**

## What the Document Claims
The document claims group-call init, membership change, rekey, sender-key distribution, and access checks.

## Code Evidence

### A) Scenario catalog alignment
- `frontend/src/lib/scenarioCatalog.ts`
  - `id: "group-call-membership-change"`
  - ordered steps match document labels:
    - `group-call-init`
    - `membership-change`
    - `rekey`
    - `sender-key-distribute`
    - `access-check`
    - `result`

### B) Synthetic execution behavior exists
- `frontend/src/components/AdminTestLabPanel.vue`
  - run engine executes ordered events with status progression.
  - synthetic logs generated from category + participant set.
  - warnings/failure/unknown branches supported.

### C) Video signaling authorization infrastructure exists
- `backend/messenger/consumers.py` `VideoSignalingConsumer`
  - user auth + conversation membership enforcement before call signaling access.

## Security Gap Relative to Claimed Semantics
No explicit implementation of:
- group-call sender-key ratchet
- participant-set-driven media key redistribution
- cryptographic proof of post-change media confidentiality

Current repository supports WebRTC signaling transport and synthetic group-call test state modeling, but not a concrete implemented group-call E2EE key management protocol in code.

## Standards/Framework Traceability
- ICE/WebRTC signaling concepts are represented.
- No MLS/SFrame-style concrete protocol implementation evidence found.
- No ISO certification evidence found for this subsystem.

## Required Codebase Changes to Close Security Gaps
1. **Implement group-call media key architecture**
   - Add sender-key or equivalent group-call media key mechanism with membership-bound distribution and epoch rotation.
   - Integrate with `frontend/src/stores/video.ts` media pipeline (insertable streams or equivalent) for real app-layer media confidentiality.

2. **Bind membership events to immediate call rekey**
   - On join/leave, trigger forced key update and require confirmation before continuing protected media transmission.
   - Persist rekey metadata/events server-side for auditability.

3. **Enforce membership-aware signaling and key update semantics**
   - Extend `backend/messenger/consumers.py` signaling schema to carry signed/validated rekey control events.
   - Reject stale/unauthorized key update or signaling messages.

4. **Add group-call security tests and pass criteria tightening**
   - Add tests for join/leave rekey correctness, removed participant media access denial, and late-join key bootstrap.
   - Update synthetic result logic so `PASS — E2EE VERIFIED` for group-call scenarios requires concrete group-call key lifecycle evidence.

## Implementation Progress Update (Current Phase)
### Completed in this phase
- `VideoSignalingConsumer` now supports validated `rekey_update` control events with:
  - payload schema checks (`epoch`, `control_nonce`),
  - anti-replay monotonic nonce enforcement,
  - per-connection signaling session binding (`signaling_session_id`) plus message sequencing,
  - rejection for non-group conversations,
  - server-side epoch update persistence for accepted forward epoch changes.
- Added unit coverage for rekey control validation error paths.

### Security impact
- Hardens signaling control plane against malformed/stale replayed rekey control messages.
- Adds auditable epoch transitions tied to group-call control events.

### Remaining gaps
- Media-frame app-layer runtime transforms exist in frontend but currently use experimental XOR obfuscation, not standards-based E2EE cryptography.
- No cryptographic proof that removed participants cannot decrypt ongoing media.
- Test-lab “PASS — E2EE VERIFIED” still exceeds what is cryptographically proven by implementation.
