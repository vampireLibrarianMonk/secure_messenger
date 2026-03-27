# 06 — Audit: Group Remove and Access-Loss Test (`documentation/06-group-remove-and-access-loss-test.md`)

## Audit Verdict
**Verdict: VERIFIED as synthetic policy/access-loss simulation; not verified as cryptographic post-removal forward secrecy proof.**

## What the Document Claims
This test claims removed members lose access after membership change and rekey.

## Code Evidence

### A) Scenario steps align with doc
- `frontend/src/lib/scenarioCatalog.ts`
  - `id: "group-remove-access-loss"`
  - ordered steps include `membership-change`, `rekey`, `post-removal-access-check`.

### B) Group evidence classifications exist
- `frontend/src/lib/resultModel.ts`
  - group evidence includes post-removal access denial field.
  - PASS requires evidence completeness and no warnings/failure branch.

### C) Group simulations run through Admin Test Lab
- `frontend/src/components/AdminTestLabPanel.vue`
  - executes group scenario steps and logs synthetic outputs.

## Important Limitation
No implemented group cryptographic key schedule with formal member removal rekey proofs is visible in repository runtime code.

So this test demonstrates **simulation-level evidence policy**, not direct cryptographic assurance that a removed endpoint cannot derive future group message keys under a formally specified protocol.

## Additional Observations
- Backend websocket membership checks (`backend/messenger/consumers.py`) enforce conversation membership for signaling/chat channel access, which supports authorization boundaries.
- This is access-control evidence, but distinct from cryptographic rekey proof.

## Required Codebase Changes to Close Security Gaps
1. **Implement post-removal cryptographic isolation**
   - Add group key epoch rotation on member removal with immediate invalidation of removed member key material.
   - Ensure removed members cannot fetch new key envelopes or decrypt post-removal ciphertexts.

2. **Harden authorization for artifact/resource access**
   - Add strict backend checks that removed participants cannot access new attachments/messages in removed conversations (including websocket and REST race conditions).
   - Add explicit audit events for removal, rekey completion, and denial verification.

3. **Add removal-focused cryptographic tests**
   - Add integration tests that simulate remove -> rekey -> send and confirm removed account decrypt failure for future content.
   - Add replay tests to ensure stale tokens/sessions cannot rejoin and regain key material.

4. **Tie synthetic access-loss PASS to concrete denial artifacts**
   - Update Admin Test Lab evidence model to require real denial logs/test artifacts before returning `PASS — E2EE VERIFIED` for remove/access-loss scenarios.
