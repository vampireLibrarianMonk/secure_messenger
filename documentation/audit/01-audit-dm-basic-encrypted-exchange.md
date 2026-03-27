# 01 — Audit: DM Basic Encrypted Exchange (`documentation/01-dm-basic-encrypted-exchange.md`)

## Audit Verdict
**Verdict: PARTIALLY VERIFIED (synthetic test behavior is accurate; cryptographic proof depth is limited).**

## What the Document Claims
The document claims a DM flow with ordered stages (`session -> encrypt -> route -> fetch -> decrypt`), ciphertext-oriented routing semantics, and evidence-based PASS/FAIL/UNKNOWN classification.

## Code Evidence

### A) Scenario definition and ordered steps are correct
- `frontend/src/lib/scenarioCatalog.ts`
  - `id: "dm-basic"`
  - `category: "dm"`
  - `orderedSteps: ["session", "encrypt", "route", "fetch", "decrypt"]`

### B) Simulation engine executes those ordered steps
- `frontend/src/components/AdminTestLabPanel.vue`
  - `runSimulation()` creates events from `scenario.orderedSteps`
  - step interval marks each prior step `completed` and current step `active`
  - final state set to `completed`/`unknown`/`failed` based on toggles and warnings

### C) Synthetic ciphertext log semantics exist
- `frontend/src/lib/fauxData.ts`
  - DM category uses log format `[dm ciphertext #N]`

### D) Evidence classification logic exists
- `frontend/src/lib/resultModel.ts`
  - DM evidence checks:
    - `dmClientEncryptConfirmed`
    - `dmCiphertextOnlyRoutingConfirmed`
    - `dmRecipientDecryptConfirmed`
  - Result classes include `PASS — E2EE VERIFIED`, `FAIL`, `UNKNOWN / UNVERIFIED`

## Cryptographic Reality (Real App Path, Outside Synthetic Simulation)
- `frontend/src/lib/crypto.ts` uses:
  - AES-GCM for text encryption/decryption (`encryptText`, `decryptText`)
  - 12-byte nonce/IV via `crypto.getRandomValues`
- `frontend/src/App.vue` sends encrypted message envelopes:
  - `/messages/` body includes `ciphertext`, `nonce`, `aad`
- `backend/messenger/models.py` stores `ciphertext`, `nonce`, `aad` in `MessageEnvelope`
- `backend/messenger/views.py` `MessageEnvelopeViewSet.create` persists and fans out envelopes; server does not decrypt message bodies.

## What Is NOT Verified by this Test
1. It does not cryptographically inspect payload bytes during simulation; it evaluates synthetic evidence flags.
2. It does not prove key exchange protocol properties (forward secrecy / PCS) for DM sessions.
3. `backend/messenger/tests.py` only includes a basic ciphertext-posting test (`test_send_ciphertext_message`), not full DM cryptographic validation.

## Standards/Framework Traceability
- AES-GCM usage aligns conceptually with NIST SP 800-38D style authenticated encryption.
- No repository evidence of formal ISO certification or validated cryptographic module operation mode.

## Required Codebase Changes to Close Security Gaps
1. **Implement real DM key agreement and key lifecycle hardening**
   - Replace `aad.shared_key` plaintext-style key sharing in `frontend/src/App.vue` / `frontend/src/stores/chat.ts` with per-recipient wrapped session keys using device public keys from `Device.identity_key`.
   - Add key rotation and message-key derivation (ratchet-like behavior) instead of static per-conversation key reuse in `frontend/src/stores/security.ts`.

2. **Enforce server-side envelope integrity constraints**
   - In `backend/messenger/views.py` / serializers, validate ciphertext/nonce format and expected lengths.
   - Reject malformed AAD payloads and add explicit schema validation for encrypted envelope metadata.

3. **Expand DM security test coverage**
   - Extend `backend/messenger/tests.py` with tests for membership denial, malformed nonce rejection, ciphertext tamper behavior, and no-plaintext persistence assertions.
   - Add frontend tests for `encryptText/decryptText` round-trip and failure-on-wrong-key behavior.

4. **Align synthetic PASS criteria with concrete checks**
   - Update `frontend/src/lib/resultModel.ts` and Admin Test Lab logic so `PASS — E2EE VERIFIED` for DM requires concrete runtime check artifacts, not only synthetic warning-free state.
